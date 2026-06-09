<#
.SYNOPSIS
Deploys or hosts Tijara Suite from Windows PowerShell or PowerShell Core.

.DESCRIPTION
This wrapper calls scripts/tijara_host.py deploy with the repository root and
keeps all runtime configuration in the central .env and secrets/.env.secrets
files. Use -DryRun to print the full action plan without changing files or
starting services.

.EXAMPLE
powershell -File scripts/tijara-deploy.ps1 -Environment staging -GenerateSecrets -Monitoring -InstallSuite

.EXAMPLE
pwsh -File scripts/tijara-deploy.ps1 -Production -Domain tijara.example.com -Monitoring -Db tijara_prod
#>
param(
    [ValidateSet("development", "staging", "production")]
    [string]$Environment,
    [string]$PublicUrl,
    [string]$Domain,
    [switch]$Production,
    [switch]$GenerateSecrets,
    [switch]$AllowPlaceholders,
    [Alias("All")]
    [switch]$AllProfiles,
    [switch]$Hardware,
    [switch]$Monitoring,
    [switch]$Pull,
    [switch]$NoPull,
    [switch]$Build,
    [switch]$InstallSuite,
    [switch]$SeedDemo,
    [string]$Db = "tijara_dev",
    [string]$HostLabel = "localhost",
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

$ArgsList = @((Join-Path $Root "scripts/tijara_host.py"), "--root", $Root, "deploy", "--db", $Db, "--host-label", $HostLabel)
if ($Environment) { $ArgsList += @("--environment", $Environment) }
if ($PublicUrl) { $ArgsList += @("--public-url", $PublicUrl) }
if ($Domain) { $ArgsList += @("--domain", $Domain) }
if ($Production) { $ArgsList += "--production" }
if ($GenerateSecrets) { $ArgsList += "--generate-secrets" }
if ($AllowPlaceholders) { $ArgsList += "--allow-placeholders" }
if ($AllProfiles) { $ArgsList += "--all-profiles" }
if ($Hardware) { $ArgsList += "--with-hardware" }
if ($Monitoring) { $ArgsList += "--with-monitoring" }
if ($Pull) { $ArgsList += "--pull" }
if ($NoPull) { $ArgsList += "--no-pull" }
if ($Build) { $ArgsList += "--build" }
if ($InstallSuite) { $ArgsList += "--install-suite" }
if ($SeedDemo) { $ArgsList += "--seed-demo" }
if ($DryRun) { $ArgsList += "--dry-run" }

$InvocationArgs = @()
$InvocationArgs += $PythonPrefix
$InvocationArgs += $ArgsList
& $PythonExe @InvocationArgs
exit $LASTEXITCODE
