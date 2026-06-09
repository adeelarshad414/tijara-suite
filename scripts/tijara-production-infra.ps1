<#
.SYNOPSIS
Generates Tijara production DNS, TLS, backup, and restore-drill automation wrappers.

.DESCRIPTION
This wrapper calls scripts/run_production_infra_automation.py from Windows
PowerShell or PowerShell Core. It keeps all configuration in the central .env
and secrets/.env.secrets contract while allowing operator-supplied templates.

.EXAMPLE
pwsh -File scripts/tijara-production-infra.ps1 --tenant-artifact deploy/runtime/tenants/tijara_customer_001

.EXAMPLE
pwsh -File scripts/tijara-production-infra.ps1 --mode apply --execute --confirm YES --tenant-artifact deploy/runtime/tenants/tijara_customer_001
#>
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
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

$ArgsList = @((Join-Path $Root "scripts/run_production_infra_automation.py"))
if ($RemainingArgs) {
    $ArgsList += $RemainingArgs
}

$InvocationArgs = @()
$InvocationArgs += $PythonPrefix
$InvocationArgs += $ArgsList
& $PythonExe @InvocationArgs
exit $LASTEXITCODE
