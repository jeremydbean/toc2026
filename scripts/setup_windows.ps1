# Idempotent Windows installer for the Docker-based Times of Chaos runtime.

[CmdletBinding()]
param(
    [ValidateSet('Preserve', 'Local', 'Public')]
    [string]$Network = 'Preserve',
    [switch]$NoStart,
    [switch]$NoBrowser,
    [switch]$SkipPrerequisites,
    [switch]$ElevatedPrerequisitesOnly
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'toc_common.ps1')

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Test-WslReady {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        return $false
    }
    & wsl.exe --status *> $null
    return $LASTEXITCODE -eq 0
}

function Install-WingetPackage {
    param(
        [Parameter(Mandatory)]
        [string]$Id,
        [Parameter(Mandatory)]
        [string]$Name
    )

    Write-Host "Installing or checking $Name..." -ForegroundColor Cyan
    & winget.exe install --exact --id $Id --source winget `
        --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "winget could not install $Name (exit code $LASTEXITCODE)."
    }
}

function Install-WindowsPrerequisites {
    if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
        throw 'Windows Package Manager (winget) is required. Install or update Microsoft App Installer, then rerun Install-ToC.cmd.'
    }

    Install-WingetPackage -Id 'Git.Git' -Name 'Git'
    Install-WingetPackage -Id 'Docker.DockerDesktop' -Name 'Docker Desktop'

    $restartNeeded = $false
    if (Test-WslReady) {
        Write-Host 'Updating WSL...' -ForegroundColor Cyan
        & wsl.exe --update
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'WSL could not be updated automatically. Docker Desktop may request an update.'
        }
    } else {
        Write-Host 'Enabling the WSL 2 platform used by Docker Desktop...' `
            -ForegroundColor Cyan
        & wsl.exe --install --no-distribution
        if ($LASTEXITCODE -ne 0) {
            throw "WSL setup failed with exit code $LASTEXITCODE."
        }
        $restartNeeded = $true
    }

    return $restartNeeded
}

function Invoke-ElevatedPrerequisitePass {
    $powerShell = (Get-Process -Id $PID).Path
    $arguments = @(
        '-NoLogo'
        '-NoProfile'
        '-ExecutionPolicy'
        'Bypass'
        '-File'
        "`"$PSCommandPath`""
        '-ElevatedPrerequisitesOnly'
    ) -join ' '

    Write-Host 'Windows will ask for permission to install prerequisites.' `
        -ForegroundColor Cyan
    $process = Start-Process -FilePath $powerShell -Verb RunAs `
        -ArgumentList $arguments -Wait -PassThru
    if ($process.ExitCode -notin 0, 10) {
        throw "The elevated prerequisite installer failed with exit code $($process.ExitCode)."
    }
    return $process.ExitCode -eq 10
}

function Refresh-ProcessPath {
    $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machinePath;$userPath"
}

if ($ElevatedPrerequisitesOnly) {
    if (-not (Test-IsAdministrator)) {
        throw 'The prerequisite pass must run with administrator rights.'
    }
    $restartNeeded = Install-WindowsPrerequisites
    if ($restartNeeded) {
        exit 10
    }
    exit 0
}

Write-Host 'Setting up Times of Chaos for Windows...' -ForegroundColor Cyan
$restartRequired = $false

if (-not $SkipPrerequisites) {
    $prerequisitesNeeded =
        -not (Get-Command git.exe -ErrorAction SilentlyContinue) -or
        -not (Get-TocDockerExecutable) -or
        -not (Test-WslReady)

    if ($prerequisitesNeeded) {
        if (-not (Test-IsAdministrator)) {
            $restartRequired = Invoke-ElevatedPrerequisitePass
        } else {
            $restartRequired = Install-WindowsPrerequisites
        }
    } else {
        Write-Host 'Git, WSL 2, and Docker Desktop are already installed.' `
            -ForegroundColor Green
    }
}

Refresh-ProcessPath
Initialize-TocInstance -Network $Network

if ($restartRequired) {
    Write-Host ''
    Write-Warning 'Windows must restart to finish enabling WSL 2.'
    Write-Host 'After restarting, double-click Install-ToC.cmd again.'
    Write-Host 'Your downloaded files and private configuration are already preserved.'
    return
}

if ($NoStart) {
    Write-Host ''
    Write-Host 'Installation and configuration are complete.' -ForegroundColor Green
    Write-Host 'Run .\toc.ps1 build when you are ready to start.'
    return
}

if (-not (Get-TocDockerExecutable)) {
    throw 'Docker Desktop was installed but its command-line tools were not found. Restart Windows and rerun Install-ToC.cmd.'
}

Write-Host ''
Write-Host 'Docker Desktop may display its license or first-run setup once.' `
    -ForegroundColor Yellow
Write-Host 'Complete that prompt if it appears; this installer will wait for Docker.'
Start-TocDocker

& (Join-Path $script:TocRepoRoot 'toc.ps1') build

if (-not $NoBrowser) {
    Open-TocDashboard
}

Write-Host ''
Write-Host 'Future starts: double-click Start-ToC.cmd or run .\toc.ps1 start' `
    -ForegroundColor Green
