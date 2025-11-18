[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Write-Status {
    param([string]$Message)
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Message"
}

function Require-Admin {
    $current = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $current.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)) {
        Write-Error 'Run this script from an elevated PowerShell session (Run as Administrator).'
        exit 1
    }
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)] [string] $FilePath,
        [string[]] $Arguments = @()
    )

    Write-Status "Running: $FilePath $($Arguments -join ' ')"
    & $FilePath @Arguments
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "$FilePath exited with code $code"
    }
}

function Ensure-Feature {
    param(
        [Parameter(Mandatory = $true)] [string] $Name
    )

    $feature = Get-WindowsOptionalFeature -Online -FeatureName $Name
    if ($feature.State -ne 'Enabled') {
        Write-Status "Enabling Windows feature: $Name"
        Enable-WindowsOptionalFeature -Online -FeatureName $Name -NoRestart | Out-Null
    } else {
        Write-Status "Windows feature already enabled: $Name"
    }
}

function Ensure-WslDefaultVersion2 {
    Write-Status 'Setting WSL default version to 2'
    & wsl --set-default-version 2
    $code = $LASTEXITCODE
    if ($code -ne 0) {
        throw "Failed to set WSL default version to 2 (exit $code)."
    }
}

function Restart-LxssManager {
    Write-Status 'Restarting LxssManager service'
    $service = Get-Service -Name LxssManager -ErrorAction SilentlyContinue
    if (-not $service) {
        throw 'LxssManager service is missing. Reboot Windows to complete WSL installation, then rerun this script.'
    }

    Restart-Service -Name LxssManager -Force -ErrorAction Stop
    Start-Sleep -Seconds 3
}

function Restart-DockerDesktop {
    param([string]$DockerDesktopExe)

    Write-Status 'Restarting Docker Desktop'
    Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Get-Process -Name 'Docker' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

    if (Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue) {
        Restart-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue | Out-Null
    }

    Start-Process -FilePath $DockerDesktopExe -ErrorAction Stop | Out-Null

    $service = $null
    $deadline = (Get-Date).AddMinutes(3)
    do {
        Start-Sleep -Seconds 3
        $service = Get-Service -Name 'com.docker.service' -ErrorAction SilentlyContinue
        if ($service -and $service.Status -ne 'Running') {
            try {
                Start-Service -Name 'com.docker.service' -ErrorAction Stop
            } catch {
                # service might still be starting; keep waiting
            }
        }
    } while ((!$service -or $service.Status -ne 'Running') -and (Get-Date) -lt $deadline)

    if (-not $service -or $service.Status -ne 'Running') {
        throw 'com.docker.service did not reach the Running state within the timeout.'
    }

    Write-Status 'Docker Desktop engine is running.'
}

function Validate-Docker {
    Write-Status 'Validating Docker CLI availability'
    Invoke-External -FilePath 'docker' -Arguments @('version')
    Invoke-External -FilePath 'docker' -Arguments @('info')
    Invoke-External -FilePath 'docker' -Arguments @('run', '--rm', 'hello-world')
}

try {
    Require-Admin

    $dockerDesktopExe = Join-Path $Env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $dockerDesktopExe)) {
        $alt = Join-Path ${Env:ProgramFiles(x86)} 'Docker\Docker\Docker Desktop.exe'
        if (Test-Path $alt) { $dockerDesktopExe = $alt }
    }

    if (-not (Test-Path $dockerDesktopExe)) {
        Write-Error 'Docker Desktop is not installed. Install it from https://www.docker.com/products/docker-desktop and rerun this script.'
        exit 1
    }

    Ensure-Feature -Name 'Microsoft-Windows-Subsystem-Linux'
    Ensure-Feature -Name 'VirtualMachinePlatform'

    Write-Status 'Updating WSL kernel'
    Invoke-External -FilePath 'wsl' -Arguments @('--update')
    Ensure-WslDefaultVersion2

    Restart-LxssManager
    Restart-DockerDesktop -DockerDesktopExe $dockerDesktopExe
    Validate-Docker

    Write-Status 'Docker Desktop (Linux engine) is healthy.'
    exit 0
} catch {
    Write-Error $_
    exit 1
}
