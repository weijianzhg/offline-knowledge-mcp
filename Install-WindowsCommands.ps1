param(
    [string]$InstallDirectory = (Join-Path $env:USERPROFILE '.local\bin'),
    [switch]$SkipPathUpdate
)
$ErrorActionPreference = 'Stop'
$InstallDirectory = [IO.Path]::GetFullPath($InstallDirectory)
$launchers = @()
foreach ($action in @('start', 'stop')) {
    $scriptName = if ($action -eq 'start') { 'Start-KnowledgeMCP.ps1' } else { 'Stop-KnowledgeMCP.ps1' }
    $scriptPath = Join-Path $PSScriptRoot $scriptName
    if (-not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) { throw "Missing launcher: $scriptPath" }
    # Encode the PowerShell invocation so spaces, Unicode and shell metacharacters in paths are safe.
    $invocation = "& '" + $scriptPath.Replace("'", "''") + "'; exit " + '$LASTEXITCODE'
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($invocation))
    $target = Join-Path $InstallDirectory "knowledge-$action.cmd"
    $marker = 'rem Offline Knowledge MCP command launcher'
    if (Test-Path -LiteralPath $target) {
        $existing = [IO.File]::ReadAllText($target)
        $legacy = $existing.Contains('-File "' + $scriptPath + '"')
        if (-not $existing.Contains($marker) -and -not $legacy) { throw "Refusing to replace an unrelated command: $target" }
    }
    $body = @(
        '@echo off',
        $marker,
        ('"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -OutputFormat Text -ExecutionPolicy Bypass -EncodedCommand ' + $encoded),
        'exit /b %errorlevel%'
    ) -join "`r`n"
    $launchers += @{ Path = $target; Content = $body + "`r`n" }
}
New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null
foreach ($launcher in $launchers) {
    [IO.File]::WriteAllText($launcher.Path, $launcher.Content, [Text.Encoding]::ASCII)
}
if (-not $SkipPathUpdate) {
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $entries = @($userPath -split ';' | Where-Object { $_ })
    $normalized = @($entries | ForEach-Object { [Environment]::ExpandEnvironmentVariables($_).TrimEnd('\') })
    if ($InstallDirectory.TrimEnd('\') -notin $normalized) {
        [Environment]::SetEnvironmentVariable('Path', (($entries + $InstallDirectory) -join ';'), 'User')
    }
    if ($InstallDirectory.TrimEnd('\') -notin @($env:Path -split ';' | ForEach-Object { $_.TrimEnd('\') })) {
        $env:Path += ';' + $InstallDirectory
    }
}
Write-Output "Installed knowledge-start and knowledge-stop in $InstallDirectory"
Write-Output 'Open a new PowerShell window, then run knowledge-start or knowledge-stop.'