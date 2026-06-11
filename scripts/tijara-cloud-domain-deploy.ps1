<#
.SYNOPSIS
Configures and deploys Tijara Suite for a public domain from Windows PowerShell
or PowerShell Core.

.DESCRIPTION
This cross-platform wrapper calls scripts/tijara_host.py for application
deployment and can optionally call scripts/run_production_infra_automation.py
to generate DNS, TLS, backup, restore-drill, and rollback evidence plans. It
uses the central .env and secrets/.env.secrets files only.

.EXAMPLE
pwsh -File scripts/tijara-cloud-domain-deploy.ps1 -Domain pos.example.com -Monitoring -InstallSuite

.EXAMPLE
pwsh -File scripts/tijara-cloud-domain-deploy.ps1 -Domain staging.example.com -Environment staging -GenerateSecrets -Monitoring -InstallSuite

.EXAMPLE
pwsh -File scripts/tijara-cloud-domain-deploy.ps1 -Domain pos.example.com -ProviderTemplate cloudflare-cert-manager-postgres -TenantArtifact deploy/runtime/tenants/tijara_customer_001
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$Domain,
    [ValidateSet("development", "staging", "production")]
    [string]$Environment = "production",
    [string]$Database = "tijara_prod",
    [string]$ProviderTemplate,
    [string]$TenantArtifact,
    [ValidateSet("plan", "apply")]
    [string]$InfraMode = "plan",
    [string]$Confirm = "NO",
    [switch]$ExecuteInfra,
    [switch]$SkipInfraPlan,
    [switch]$Monitoring,
    [switch]$Hardware,
    [Alias("All")]
    [switch]$AllProfiles,
    [switch]$Build,
    [switch]$Pull,
    [switch]$NoPull,
    [switch]$InstallSuite,
    [switch]$SeedDemo,
    [switch]$GenerateSecrets,
    [switch]$AllowPlaceholders,
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

$HostArgs = @(
    (Join-Path $Root "scripts/tijara_host.py"),
    "--root", $Root,
    "deploy",
    "--environment", $Environment,
    "--domain", $Domain,
    "--host-label", $Domain,
    "--db", $Database
)

if ($Environment -eq "production") { $HostArgs += "--production" }
if ($Monitoring) { $HostArgs += "--with-monitoring" }
if ($Hardware) { $HostArgs += "--with-hardware" }
if ($AllProfiles) { $HostArgs += "--all-profiles" }
if ($Build) { $HostArgs += "--build" }
if ($Pull) { $HostArgs += "--pull" }
if ($NoPull) { $HostArgs += "--no-pull" }
if ($InstallSuite) { $HostArgs += "--install-suite" }
if ($SeedDemo) { $HostArgs += "--seed-demo" }
if ($GenerateSecrets) { $HostArgs += "--generate-secrets" }
if ($AllowPlaceholders) { $HostArgs += "--allow-placeholders" }
if ($DryRun) { $HostArgs += "--dry-run" }

Write-Host "Deploying Tijara Suite for domain: $Domain"
$InvocationArgs = @()
$InvocationArgs += $PythonPrefix
$InvocationArgs += $HostArgs
& $PythonExe @InvocationArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($SkipInfraPlan) {
    Write-Host "Skipped DNS/TLS/backup infra plan generation."
    exit 0
}

if (-not $ProviderTemplate -and -not $TenantArtifact) {
    Write-Host ""
    Write-Host "App deployment finished. DNS/TLS/backup planning was not generated because no -ProviderTemplate or -TenantArtifact was supplied."
    Write-Host "Next example:"
    Write-Host "  pwsh -File scripts/tijara-cloud-domain-deploy.ps1 -Domain $Domain -ProviderTemplate cloudflare-cert-manager-postgres -TenantArtifact deploy/runtime/tenants/tijara_customer_001"
    exit 0
}

if ($DryRun) {
    Write-Host "Dry-run enabled; skipping infra automation output generation."
    exit 0
}

$InfraArgs = @(
    (Join-Path $Root "scripts/run_production_infra_automation.py"),
    "--target-environment", $Environment,
    "--mode", $InfraMode,
    "--confirm", $Confirm,
    "--strict"
)
if ($ProviderTemplate) { $InfraArgs += @("--provider-template", $ProviderTemplate) }
if ($TenantArtifact) { $InfraArgs += @("--tenant-artifact", $TenantArtifact) }
if ($ExecuteInfra) { $InfraArgs += "--execute" }

Write-Host "Generating DNS/TLS/backup infra evidence plan..."
$InfraInvocationArgs = @()
$InfraInvocationArgs += $PythonPrefix
$InfraInvocationArgs += $InfraArgs
& $PythonExe @InfraInvocationArgs
exit $LASTEXITCODE
