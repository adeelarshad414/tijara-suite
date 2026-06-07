param(
    [switch]$ForceKillPorts
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$LogDir = Join-Path $Root "logs"
$PidFile = Join-Path $LogDir "dev-pids.txt"

Set-Location $Root
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

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

function Stop-Port {
    param([string]$Port)
    if (-not $ForceKillPorts) {
        return
    }
    $Rows = netstat -ano | Select-String ":$Port"
    foreach ($Row in $Rows) {
        $Parts = ($Row.ToString() -split "\s+") | Where-Object { $_ }
        $Pid = $Parts[-1]
        if ($Pid -match "^\d+$") {
            Stop-Process -Id ([int]$Pid) -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Stopping Tijara Suite Compose services..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    $Base = Compose-Args
    & docker @Base @("--profile", "hardware", "--profile", "monitoring", "down")
}

if (Test-Path $PidFile) {
    foreach ($Line in Get-Content $PidFile) {
        $Pid = ($Line -split "\s+")[0]
        if ($Pid -match "^\d+$") {
            Stop-Process -Id ([int]$Pid) -ErrorAction SilentlyContinue
        }
    }
    Set-Content -Path $PidFile -Value ""
}

$Ports = @(
    (Read-EnvValue "HTTP_PORT" "8069"),
    (Read-EnvValue "LONGPOLLING_PORT" "8072"),
    "5432",
    (Read-EnvValue "TIJARA_BRIDGE_PORT" "9109"),
    (Read-EnvValue "PROMETHEUS_PORT" "9090"),
    (Read-EnvValue "BLACKBOX_PORT" "9115"),
    (Read-EnvValue "ALERTMANAGER_PORT" "9093"),
    (Read-EnvValue "LOKI_PORT" "3100"),
    (Read-EnvValue "GRAFANA_PORT" "3000")
)

foreach ($Port in $Ports) {
    Stop-Port $Port
}

foreach ($Port in $Ports) {
    $Rows = netstat -ano | Select-String ":$Port"
    if ($Rows) {
        Write-Host "Port $Port still in use"
    } else {
        Write-Host "Port $Port is free"
    }
}

Write-Host "All Tijara Suite Compose services stopped."
