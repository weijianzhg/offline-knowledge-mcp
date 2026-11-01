$ErrorActionPreference = 'Stop'
$pidFile = Join-Path $PSScriptRoot 'logs\server.pid'
if (-not (Test-Path -LiteralPath $pidFile)) { Write-Output 'No server PID recorded.'; exit 0 }
$serverPid = [int](Get-Content -LiteralPath $pidFile)
$worker = Get-CimInstance Win32_Process -Filter "ProcessId=$serverPid"
if (-not $worker) { Write-Output 'Server is already stopped.'; exit 0 }
$expectedPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if ($worker.ExecutablePath -ne $expectedPython -or $worker.CommandLine -notlike '*knowledge_mcp.server*') {
    throw 'PID belongs to another process; refusing to stop it.'
}
# Windows venv launches a child interpreter. Stop only children of the verified launcher.
$children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$serverPid"
foreach ($child in $children) {
    if ($child.CommandLine -like '*-m knowledge_mcp.server*') { Stop-Process -Id $child.ProcessId }
}
Stop-Process -Id $serverPid -ErrorAction SilentlyContinue
Write-Output 'Knowledge MCP stopped.'
