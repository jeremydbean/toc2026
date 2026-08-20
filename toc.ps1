[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'build', 'stop', 'restart', 'status', 'logs', 'doctor', 'update', 'open', 'help')]
    [string]$Action = 'start'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'scripts\toc_common.ps1')

function Invoke-Compose {
    param(
        [Parameter(Mandatory)]
        [string[]]$ArgumentList,
        [switch]$AllowFailure
    )

    $arguments = @('compose', '--project-directory', $script:TocRepoRoot) + $ArgumentList
    Invoke-TocDocker -ArgumentList $arguments -AllowFailure:$AllowFailure
}

function Start-TocGame {
    param([switch]$Build)

    Initialize-TocInstance
    if (-not (Get-TocDockerExecutable)) {
        throw 'Docker was not found. Run .\install.ps1 first.'
    }
    Invoke-TocDocker -ArgumentList @('compose', 'version') -Quiet
    Start-TocDocker
    $arguments = @('up', '-d')
    if ($Build) {
        $arguments = @('up', '--build', '-d')
    }
    Invoke-Compose -ArgumentList $arguments
    Wait-TocGame
    Write-TocEndpoints
}

switch ($Action) {
    'start' { Start-TocGame }
    'build' { Start-TocGame -Build }
    'stop' {
        Start-TocDocker
        Invoke-Compose -ArgumentList @('stop')
        Write-Host 'Times of Chaos is stopped. Runtime data was preserved.' `
            -ForegroundColor Green
    }
    'restart' {
        Start-TocDocker
        Invoke-Compose -ArgumentList @('restart', 'game')
        Wait-TocGame
        Write-TocEndpoints
    }
    'status' {
        if (-not (Test-TocDockerReady)) {
            throw 'Docker is installed but is not running.'
        }
        Invoke-Compose -ArgumentList @('ps')
        Write-TocEndpoints
    }
    'logs' {
        Start-TocDocker
        Invoke-Compose -ArgumentList @('logs', '-f', '--tail', '200', 'game')
    }
    'doctor' {
        $failures = 0
        Write-Host 'Times of Chaos installation check' -ForegroundColor Cyan
        Write-Host "Repository: $script:TocRepoRoot"
        $docker = Get-TocDockerExecutable
        if ($docker) {
            Write-Host "[ok] Docker CLI: $docker" -ForegroundColor Green
            Invoke-TocDocker -ArgumentList @('--version')
        } else {
            Write-Host '[missing] Docker CLI' -ForegroundColor Red
            $failures++
        }
        if ($docker) {
            $composeExit = Invoke-TocDocker -ArgumentList @('compose', 'version') `
                -AllowFailure -Quiet
            if ($composeExit -eq 0) {
                Write-Host '[ok] Docker Compose v2' -ForegroundColor Green
            } else {
                Write-Host '[missing] Docker Compose v2' -ForegroundColor Red
                $failures++
            }
        }
        if ((Test-Path -LiteralPath $script:TocEnvFile) -and
            (Get-TocEnvValue -Name 'WEB_ADMIN_TOKEN')) {
            Write-Host '[ok] Private runtime configuration' -ForegroundColor Green
        } else {
            Write-Host '[missing] .env with WEB_ADMIN_TOKEN' -ForegroundColor Red
            $failures++
        }
        if ($docker -and (Test-TocDockerReady)) {
            Write-Host '[ok] Docker engine is running' -ForegroundColor Green
            $configExit = Invoke-Compose -ArgumentList @('config', '--quiet') `
                -AllowFailure
            if ($configExit -ne 0) {
                $failures++
            }
        } else {
            Write-Host '[stopped] Docker engine' -ForegroundColor Yellow
            $failures++
        }
        if ($failures -ne 0) {
            throw "Doctor found $failures issue(s). Run .\install.ps1 to repair setup."
        }
        Write-Host 'Everything needed to launch ToC is ready.' -ForegroundColor Green
    }
    'update' {
        if (-not (Test-Path -LiteralPath (Join-Path $script:TocRepoRoot '.git'))) {
            throw 'This copy is not a Git checkout; download a current release before updating.'
        }
        $changes = git -C $script:TocRepoRoot status --porcelain
        if ($LASTEXITCODE -ne 0) {
            throw 'Could not inspect the Git working tree.'
        }
        if ($changes) {
            throw 'Update stopped because the repository has local changes. Commit, stash, or remove them first.'
        }
        git -C $script:TocRepoRoot pull --ff-only
        if ($LASTEXITCODE -ne 0) {
            throw 'Git could not fast-forward this installation.'
        }
        Start-TocGame -Build
    }
    'open' { Open-TocDashboard }
    'help' {
        @'
Usage: .\toc.ps1 [command]

  start      Start an existing installation (default)
  build      Build/rebuild the image and start ToC
  stop       Stop ToC while preserving all data
  restart    Restart the running container
  status     Show container health and connection addresses
  logs       Follow the latest game and dashboard logs
  doctor     Check the local installation without changing it
  update     Fast-forward from GitHub, rebuild, and restart
  open       Open the local web dashboard
  help       Show this command list
'@ | Write-Host
    }
}
