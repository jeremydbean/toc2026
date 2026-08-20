# Install ToC prerequisites on Windows 11 with winget.
# Review wiki/hosting-guide.md and SECURITY.md before running a public server.

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdministrator = $principal.IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $isAdministrator) {
    throw 'Run this setup helper from an Administrator PowerShell session.'
}

if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    throw 'winget is required. Install or update Microsoft App Installer first.'
}

Write-Host 'Setting up Times of Chaos prerequisites...' -ForegroundColor Cyan

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    winget install --exact --id Git.Git --source winget `
        --accept-package-agreements --accept-source-agreements
} else {
    Write-Host 'Git is already installed.' -ForegroundColor Green
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    winget install --exact --id Docker.DockerDesktop --source winget `
        --accept-package-agreements --accept-source-agreements
    Write-Warning 'Restart Windows if requested, then open Docker Desktop and finish setup.'
} else {
    Write-Host 'Docker is already installed.' -ForegroundColor Green
}

if (Get-Command wsl -ErrorAction SilentlyContinue) {
    & wsl --status | Out-Null
}

if (-not (Get-Command wsl -ErrorAction SilentlyContinue) -or $LASTEXITCODE -ne 0) {
    Write-Warning 'WSL is not ready. Run "wsl --install -d Ubuntu" and restart Windows.'
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $repoRoot

foreach ($directory in 'player', 'log', 'backups', 'gods', 'heroes') {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

if (-not (Test-Path -LiteralPath '.env')) {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $token = [Convert]::ToHexString($bytes)
    Set-Content -LiteralPath '.env' -Value "WEB_ADMIN_TOKEN=$token" -Encoding ascii
    Write-Host 'Created .env with a random WEB_ADMIN_TOKEN.' -ForegroundColor Green
} else {
    Write-Host 'Kept the existing .env unchanged.' -ForegroundColor Green
}

Write-Host ''
Write-Host 'Prerequisite setup complete.' -ForegroundColor Cyan
Write-Host '1. Restart Windows if an installer requested it.'
Write-Host '2. Start Docker Desktop and wait for the engine to become ready.'
Write-Host '3. Return to this repository and run: docker compose up --build -d'
Write-Host '4. Connect to localhost:9000.'
Write-Host '5. Before production, bind dashboard port 9001 to loopback as documented.'
