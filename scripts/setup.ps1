param(
    [string]$Python = "python",
    [switch]$NoVenv
)

# Ensure we run from the project root (parent of scripts folder)
$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $projectRoot

Write-Host "Setting up virtual environment and installing dependencies..." -ForegroundColor Cyan

if (-not $NoVenv) {
  if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
  }
  $activate = Join-Path ".venv" "Scripts/Activate.ps1"
  if (Test-Path $activate) { . $activate } else { throw ".venv activation script not found" }
}

& python -m pip install --upgrade pip
& pip install -r requirements.txt

Write-Host "Creating local data directory..." -ForegroundColor Cyan
$newDataDir = ".\.data"
if (-not (Test-Path $newDataDir)) { New-Item -ItemType Directory -Path $newDataDir | Out-Null }

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Write-Host ".env created from example. Update values as needed." -ForegroundColor Yellow
}

Write-Host "Setup complete." -ForegroundColor Green

