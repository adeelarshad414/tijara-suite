<#
.SYNOPSIS
Starts Tijara Suite services from Windows PowerShell or PowerShell Core.

.DESCRIPTION
This wrapper calls scripts/tijara_services.py with the repository root and the
same central .env plus secrets/.env.secrets runtime contract used by Docker
Compose, Make, and the Bash wrappers.

.EXAMPLE
powershell -File scripts/tijara-start.ps1 -AllProfiles -InstallSuite -SeedDemo

.EXAMPLE
pwsh -File scripts/tijara-start.ps1 -Hardware -Monitoring -NoWait
#>
param(
    [Alias("All")]
    [switch]$AllProfiles,
    [switch]$Hardware,
    [switch]$Monitoring,
    [switch]$InstallSuite,
    [switch]$SeedDemo,
    [string]$Db = "tijara_dev",
    [switch]$NoWait,
    [int]$Timeout = 90,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-PythonInvocation {
    if (Get-Command python3 -ErrorAction SilentlyContinue) { return @("python3") }
    if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
    if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
    throw "python3, python, or py launcher is required."
}

$Python = @(Get-PythonInvocation)
$PythonExe = $Python[0]
$PythonPrefix = @()
if ($Python.Count -gt 1) {
    $PythonPrefix = $Python[1..($Python.Count - 1)]
}

$ArgsList = @((Join-Path $Root "scripts/tijara_services.py"), "--root", $Root, "start", "--db", $Db, "--timeout", "$Timeout")
if ($AllProfiles) { $ArgsList += "--all-profiles" }
if ($Hardware) { $ArgsList += "--with-hardware" }
if ($Monitoring) { $ArgsList += "--with-monitoring" }
if ($InstallSuite) { $ArgsList += "--install-suite" }
if ($SeedDemo) { $ArgsList += "--seed-demo" }
if ($NoWait) { $ArgsList += "--no-wait" }
if ($DryRun) { $ArgsList += "--dry-run" }

$InvocationArgs = @()
$InvocationArgs += $PythonPrefix
$InvocationArgs += $ArgsList
& $PythonExe @InvocationArgs
exit $LASTEXITCODE
