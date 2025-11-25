# Check for Administrator privileges
if (!([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Warning "This script requires Administrator privileges. Please run PowerShell as Administrator."
    exit 1
}

Write-Host "Setting up Times of Chaos development environment..." -ForegroundColor Cyan

# 1. Install Chocolatey (Package Manager)
if (!(Get-Command choco -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Chocolatey..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
} else {
    Write-Host "Chocolatey is already installed." -ForegroundColor Green
}

# Refresh env vars
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

# 2. Install Git
if (!(Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Git..." -ForegroundColor Yellow
    choco install git -y
} else {
    Write-Host "Git is already installed." -ForegroundColor Green
}

# 3. Install Docker Desktop
if (!(Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Docker Desktop..." -ForegroundColor Yellow
    choco install docker-desktop -y
    Write-Host "Docker Desktop installed. You MUST restart your computer and launch Docker Desktop manually after reboot." -ForegroundColor Red
} else {
    Write-Host "Docker is already installed." -ForegroundColor Green
}

# 4. Install VS Code
if (!(Get-Command code -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Visual Studio Code..." -ForegroundColor Yellow
    choco install vscode -y
} else {
    Write-Host "VS Code is already installed." -ForegroundColor Green
}

Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Cyan
Write-Host "1. If Docker was just installed, RESTART YOUR COMPUTER."
Write-Host "2. After restart, launch 'Docker Desktop' from the Start Menu."
Write-Host "3. Open PowerShell and navigate to this folder."
Write-Host "4. Run: docker build -t toc ."
Write-Host "5. Run: docker run -it -p 9000:9000 -p 9001:9001 -v ${PWD}/player:/app/player -v ${PWD}/log:/app/log toc"
Write-Host "----------------------------------------------------------------" -ForegroundColor Cyan
