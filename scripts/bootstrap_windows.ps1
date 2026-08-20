# Fresh-machine bootstrap: install Git, clone ToC, and run the full installer.

[CmdletBinding()]
param(
    [string]$InstallDirectory = (Join-Path $env:USERPROFILE 'TimesOfChaos'),
    [switch]$Public
)

$ErrorActionPreference = 'Stop'
$repository = 'https://github.com/jeremydbean/toc2026.git'

function Refresh-Path {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

function Find-Git {
    $command = Get-Command git.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    foreach ($candidate in @(
        (Join-Path $env:ProgramFiles 'Git\cmd\git.exe')
        (Join-Path $env:LOCALAPPDATA 'Programs\Git\cmd\git.exe')
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

Write-Host 'Times of Chaos fresh-machine setup' -ForegroundColor Cyan

$git = Find-Git
if (-not $git) {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'Windows Package Manager (winget) is required. Install Microsoft App Installer and rerun this bootstrap.'
    }
    Write-Host 'Installing Git...' -ForegroundColor Cyan
    & winget.exe install --exact --id Git.Git --source winget `
        --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "Git installation failed with exit code $LASTEXITCODE."
    }
    Refresh-Path
    $git = Find-Git
    if (-not $git) {
        throw 'Git was installed but was not found. Restart PowerShell and rerun the bootstrap.'
    }
}

$installParent = Split-Path -Parent $InstallDirectory
if ($installParent) {
    New-Item -ItemType Directory -Path $installParent -Force | Out-Null
}

$gitDirectory = Join-Path $InstallDirectory '.git'
if (Test-Path -LiteralPath $gitDirectory) {
    Write-Host "Using existing checkout: $InstallDirectory" -ForegroundColor Green
    $changes = & $git -C $InstallDirectory status --porcelain
    if (-not $changes) {
        & $git -C $InstallDirectory pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            throw 'The existing checkout could not be fast-forwarded.'
        }
    } else {
        Write-Warning 'The existing checkout has local changes; setup will preserve them without pulling.'
    }
} else {
    if ((Test-Path -LiteralPath $InstallDirectory) -and
        (Get-ChildItem -LiteralPath $InstallDirectory -Force | Select-Object -First 1)) {
        throw "Install directory is not empty and is not a Git checkout: $InstallDirectory"
    }
    Write-Host "Downloading Times of Chaos to $InstallDirectory..." -ForegroundColor Cyan
    & $git clone $repository $InstallDirectory
    if ($LASTEXITCODE -ne 0) {
        throw 'The Times of Chaos repository could not be cloned.'
    }
}

$network = if ($Public) { 'Public' } else { 'Local' }
& (Join-Path $InstallDirectory 'install.ps1') -Network $network
