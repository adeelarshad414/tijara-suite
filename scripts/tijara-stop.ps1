<#
.SYNOPSIS
Stops Tijara Suite services from Windows PowerShell or PowerShell Core.

.DESCRIPTION
This wrapper calls scripts/tijara_services.py stop and can also free the known
local Tijara ports when a workstation or server has stale processes.

.EXAMPLE
powershell -File scripts/tijara-stop.ps1 -ForceKillPorts
#>
param(
    [switch]$ForceKillPorts,
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

$ArgsList = @((Join-Path $Root "scripts/tijara_services.py"), "--root", $Root, "stop")
if ($ForceKillPorts) { $ArgsList += "--force-kill-ports" }
if ($DryRun) { $ArgsList += "--dry-run" }

$InvocationArgs = @()
$InvocationArgs += $PythonPrefix
$InvocationArgs += $ArgsList
& $PythonExe @InvocationArgs
exit $LASTEXITCODE
