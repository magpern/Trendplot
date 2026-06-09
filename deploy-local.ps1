param(
    [switch]$NoCache,
    [switch]$ForceRecreate,
    [switch]$SkipHealthCheck,
    [switch]$Reset
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $ProjectRoot "docker-compose.yml"
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExampleFile = Join-Path $ProjectRoot ".env.example"
$ServiceName = "seo-content-worker"
$PostgresServiceName = "postgres"
$HealthUrl = "http://localhost:8000/health"
$DashboardUrl = "http://localhost:8000"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-WarningMessage {
    param([string]$Message)
    Write-Host "WARNING: $Message" -ForegroundColor Yellow
}

function Assert-Command {
    param([string]$CommandName)

    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "Required command '$CommandName' was not found on PATH."
    }
}

function Invoke-DockerCompose {
    param([string[]]$Arguments)

    & docker compose @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose $($Arguments -join ' ') failed with exit code $LASTEXITCODE."
    }
}

function Wait-ForComposeServiceHealthy {
    param(
        [string]$Name,
        [int]$TimeoutSeconds = 90
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        $containerId = (& docker compose ps -q $Name).Trim()
        if ($containerId) {
            $health = (& docker inspect --format "{{.State.Health.Status}}" $containerId 2>$null).Trim()
            if ($health -eq "healthy") {
                return
            }
            if ($health -eq "unhealthy") {
                throw "Service '$Name' became unhealthy."
            }
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    throw "Service '$Name' did not become healthy within $TimeoutSeconds seconds."
}

function Wait-ForHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 3
            if ($response.status -eq "ok") {
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
    } while ((Get-Date) -lt $deadline)

    throw "Service did not become healthy at $Url within $TimeoutSeconds seconds."
}

Set-Location $ProjectRoot

Write-Step "Checking Docker prerequisites"
Assert-Command "docker"

& docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker is not running or is not reachable. Start Docker Desktop and try again."
}

& docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 is not available. Install or update Docker Desktop and try again."
}

if (-not (Test-Path $ComposeFile)) {
    throw "Cannot find docker-compose.yml at $ComposeFile."
}

if (-not (Test-Path $EnvFile)) {
    if (-not (Test-Path $EnvExampleFile)) {
        throw "Cannot find .env or .env.example. Create .env before deploying."
    }

    Write-WarningMessage ".env was missing; creating it from .env.example."
    Copy-Item -Path $EnvExampleFile -Destination $EnvFile
    Write-WarningMessage "Update .env with real OpenAI, WordPress, and YouTube credentials before generating articles."
}

if ($Reset) {
    Write-Step "Resetting local Docker containers and volumes"
    Invoke-DockerCompose @("down", "-v", "--remove-orphans")
}

Write-Step "Building latest $ServiceName image"
$buildArgs = @("build")
if ($NoCache) {
    $buildArgs += "--no-cache"
}
$buildArgs += $ServiceName
Invoke-DockerCompose $buildArgs

Write-Step "Starting PostgreSQL"
$postgresUpArgs = @("up", "-d")
if ($ForceRecreate) {
    $postgresUpArgs += "--force-recreate"
}
$postgresUpArgs += $PostgresServiceName
Invoke-DockerCompose $postgresUpArgs

Write-Step "Waiting for PostgreSQL health check"
Wait-ForComposeServiceHealthy -Name $PostgresServiceName

Write-Step "Starting $ServiceName"
$appUpArgs = @("up", "-d", "--remove-orphans")
if ($ForceRecreate) {
    $appUpArgs += "--force-recreate"
}
$appUpArgs += $ServiceName
Invoke-DockerCompose $appUpArgs

Write-Step "Running Alembic migrations"
Invoke-DockerCompose @("exec", "-T", $ServiceName, "alembic", "upgrade", "head")

if (-not $SkipHealthCheck) {
    Write-Step "Waiting for service health check"
    Wait-ForHealth -Url $HealthUrl
}

Write-Step "Deployment complete"
docker compose ps

Write-Host ""
Write-Host "Dashboard: $DashboardUrl" -ForegroundColor Green
Write-Host "Health: $HealthUrl" -ForegroundColor Green
