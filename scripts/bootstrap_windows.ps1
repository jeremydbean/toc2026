# Fresh-machine bootstrap for Windows: install Git, fetch Times of Chaos,
# and run the full installer (Docker Desktop on WSL 2). From PowerShell:
#
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/jeremydbean/toc2026/main/scripts/bootstrap_windows.ps1)))
#
# Add -Public to accept game connections from other computers, and
# -ImportPlayers to start with the repository's characters.

[CmdletBinding()]
param(
    [string]$InstallDirectory = (Join-Path $env:USERPROFILE 'TimesOfChaos'),
    [switch]$Public,
    [switch]$ImportPlayers
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
    # Game data an older install kept in the checkout is not a code change.
    $changes = & $git -C $InstallDirectory status --porcelain -- . ':(exclude)player' `
        ':(exclude)gods' ':(exclude)heroes' ':(exclude)log'
    if (-not $changes) {
        & $git -C $InstallDirectory pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'The existing checkout could not be updated; continuing with the version it has.'
        }
    } else {
        Write-Warning 'The existing checkout has local code changes; setup will preserve them without pulling.'
    }
} else {
    if ((Test-Path -LiteralPath $InstallDirectory) -and
        (Get-ChildItem -LiteralPath $InstallDirectory -Force | Select-Object -First 1)) {
        throw "Install directory is not empty and is not a Git checkout: $InstallDirectory"
    }
    Write-Host "Downloading Times of Chaos to $InstallDirectory..." -ForegroundColor Cyan
    # The latest commit only (the history carries years of player saves),
    # and files byte for byte as committed: Git for Windows' default CRLF
    # conversion would otherwise rewrite the area files a local image
    # build copies in.
    & $git clone --depth 1 -c core.autocrlf=false $repository $InstallDirectory
    if ($LASTEXITCODE -ne 0) {
        throw 'The Times of Chaos repository could not be cloned.'
    }
}

$network = if ($Public) { 'Public' } else { 'Local' }
& (Join-Path $InstallDirectory 'install.ps1') -Network $network -ImportPlayers:$ImportPlayers
