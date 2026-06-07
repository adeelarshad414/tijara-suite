param(
    [switch]$Hardware,
    [switch]$Monitoring,
    [switch]$InstallSuite,
    [switch]$SeedPosDemo
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $Root "logs"
$PidFile = Join-Path $LogDir "dev-pids.txt"
$ContainerFile = Join-Path $LogDir "dev-containers.txt"

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Content -Path $PidFile -Value ""
Set-Content -Path $ContainerFile -Value ""

function Require-Command {
    param([string]$Name, [string]$InstallHint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Host "Missing required command: $Name"
        Write-Host "Install: $InstallHint"
        exit 1
    }
}

function Read-EnvValue {
    param([string]$Key, [string]$Fallback)
    $EnvFile = Join-Path $Root ".env"
    if (Test-Path $EnvFile) {
        $Line = Get-Content $EnvFile | Where-Object { $_ -match "^$Key=" } | Select-Object -Last 1
        if ($Line) {
            return ($Line -replace "^$Key=", "")
        }
    }
    return $Fallback
}

function Compose-Args {
    $Args = @("compose")
    $EnvFile = Join-Path $Root ".env"
    $SecretsFile = Join-Path $Root "secrets/.env.secrets"
    if (Test-Path $EnvFile) {
        $Args += @("--env-file", $EnvFile)
    }
    if (Test-Path $SecretsFile) {
        $Args += @("--env-file", $SecretsFile)
    }
    return $Args
}

function Run-Compose {
    param([string[]]$Args)
    $Base = Compose-Args
    & docker @Base @Args
}

function Wait-ForHttp {
    param([string]$Label, [string]$Url, [int]$MaxSeconds = 60)
    $Elapsed = 0
    while ($Elapsed -lt $MaxSeconds) {
        try {
            Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 4 | Out-Null
            return
        } catch {
            Start-Sleep -Seconds 2
            $Elapsed += 2
        }
    }
    Write-Host "$Label did not become healthy within ${MaxSeconds}s: $Url"
}

Require-Command "docker" "https://docs.docker.com/get-docker/"
Run-Compose @("version") | Out-Null

if ((Test-Path (Join-Path $Root "package.json")) -and -not (Test-Path (Join-Path $Root "node_modules"))) {
    Require-Command "npm" "https://nodejs.org/"
    npm install
}

if (-not (Test-Path (Join-Path $Root ".env")) -and (Test-Path (Join-Path $Root ".env.example"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
    Write-Host "Created .env from .env.example"
}

$SecretsDir = Join-Path $Root "secrets"
$SecretsFile = Join-Path $SecretsDir ".env.secrets"
$SecretsExample = Join-Path $SecretsDir ".env.secrets.example"
if (-not (Test-Path $SecretsFile) -and (Test-Path $SecretsExample)) {
    New-Item -ItemType Directory -Force -Path $SecretsDir | Out-Null
    Copy-Item $SecretsExample $SecretsFile
    Write-Host "Created secrets/.env.secrets from secrets/.env.secrets.example"
    Write-Host "Review placeholder secrets before production or shared staging use."
}

Write-Host "Validating Docker Compose configuration..."
Run-Compose @("config") | Out-Null

Write-Host "Starting Tijara Suite core services..."
Run-Compose @("up", "-d")
if ($Hardware) {
    Run-Compose @("--profile", "hardware", "up", "-d", "hardware_bridge")
}
if ($Monitoring) {
    Run-Compose @("--profile", "monitoring", "up", "-d", "prometheus", "blackbox", "alertmanager", "loki", "grafana")
}

Run-Compose @("ps", "-q") | Set-Content -Path $ContainerFile

$HttpPort = Read-EnvValue "HTTP_PORT" "8069"
Wait-ForHttp "Odoo web" "http://localhost:$HttpPort/web/login" 60

if ($InstallSuite) {
    make install-suite
}
if ($SeedPosDemo) {
    make seed-pos-demo
}

Write-Host ""
Write-Host "Service               URL                               Status"
Write-Host "Odoo web              http://localhost:$HttpPort          started"
Write-Host "PostgreSQL            localhost:5432                     started"
Write-Host ""
Write-Host "Stop everything with: powershell -File scripts/dev-stop.ps1"
