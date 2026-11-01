param([int]$Port = 8766)
$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId=$($listener[0].OwningProcess)"
    $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($owner.ParentProcessId)"
    $isOurLauncher = $owner.ExecutablePath -eq $python -or ($parent.ExecutablePath -eq $python -and $parent.CommandLine -like '*knowledge_mcp.server*')
    if ($owner.CommandLine -notlike '*knowledge_mcp.server*' -or -not $isOurLauncher) {
        throw "Port $Port is occupied by another process."
    }
    Write-Output "Knowledge MCP already running at http://127.0.0.1:$Port/mcp"
    exit 0
}
$worker = Start-Process -FilePath $python -ArgumentList '-m','knowledge_mcp.server','--port',"$Port" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logDir 'server.out.log') -RedirectStandardError (Join-Path $logDir 'server.err.log')
$worker.Id | Set-Content -LiteralPath (Join-Path $logDir 'server.pid')
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 500
    $worker.Refresh()
    if ($worker.HasExited) { throw "Knowledge MCP exited. See logs\server.err.log." }
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Output "Knowledge MCP started at http://127.0.0.1:$Port/mcp (PID $($worker.Id))"
        exit 0
    }
}
throw 'Startup timed out; inspect logs before retrying.'
