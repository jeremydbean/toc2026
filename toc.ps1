[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('start', 'build', 'stop', 'restart', 'status', 'logs', 'doctor', 'update',
        'open', 'play', 'admin', 'promote', 'backup', 'restore', 'uninstall', 'help')]
    [string]$Action = 'start',
    [Parameter(Position = 1)]
    [string]$Target = '',
    [int]$Level = 70,
    [switch]$Purge,
    [switch]$Yes
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

function Assert-TocInstalled {
    if (-not (Test-Path -LiteralPath $script:TocEnvFile)) {
        throw 'This folder is not installed yet. Run Install-ToC.cmd or .\install.ps1 first.'
    }
    if ((Get-TocEnvValue -Name 'TOC_MODE' -Default 'docker') -eq 'native') {
        throw 'This installation runs natively; use ./toc.sh from WSL or Linux to manage it.'
    }
}

# .env and the state folder. The engine has to be up first: an
# installation from before the state folder keeps its world in the old
# container, which is copied out before anything replaces it.
function Initialize-TocRun {
    Assert-TocInstalled
    if (-not (Get-TocDockerExecutable)) {
        throw 'Docker was not found. Run .\install.ps1 first.'
    }
    Invoke-TocDocker -ArgumentList @('compose', 'version') -Quiet | Out-Null
    Start-TocDocker
    Initialize-TocInstance
}

function Start-TocGame {
    param([switch]$Build)

    Initialize-TocRun
    if ($Build) {
        Install-TocImage -Build
    } else {
        $image = Get-TocEnvValue -Name 'TOC_IMAGE' -Default $script:TocDefaultImage
        $exit = Invoke-TocDocker -ArgumentList @('image', 'inspect', $image) -AllowFailure -Quiet
        if ($exit -ne 0) {
            Install-TocImage
        }
    }
    Invoke-Compose -ArgumentList @('up', '-d', '--no-build', 'game') | Out-Null
    Wait-TocGame
    Write-TocEndpoints
}

# Whether the game container is still running after a stop.
function Test-TocGameRunning {
    if (-not (Get-TocDockerExecutable) -or -not (Test-TocDockerReady)) {
        return $false
    }
    $ids = & (Get-TocDockerExecutable) compose --project-directory $script:TocRepoRoot `
        ps --status running -q game 2>$null
    return [bool]$ids
}

function Stop-TocGame {
    Assert-TocInstalled
    Start-TocDocker
    Invoke-Compose -ArgumentList @('stop', 'game') | Out-Null
    Write-Host 'Times of Chaos is stopped. Every player was saved and all data kept.' `
        -ForegroundColor Green
}

switch ($Action) {
    'start' { Start-TocGame }
    'build' { Start-TocGame -Build }
    'stop' { Stop-TocGame }
    'restart' {
        Stop-TocGame
        Start-TocGame
    }
    'status' {
        Assert-TocInstalled
        if (-not (Test-TocDockerReady)) {
            throw 'Docker is installed but is not running.'
        }
        Invoke-Compose -ArgumentList @('ps') | Out-Null  # printed by Invoke-TocDocker
        Write-TocEndpoints
    }
    'logs' {
        Assert-TocInstalled
        Start-TocDocker
        Invoke-Compose -ArgumentList @('logs', '-f', '--tail', '200', 'game') | Out-Null
    }
    'doctor' {
        $failures = 0
        Write-Host 'Times of Chaos installation check' -ForegroundColor Cyan
        Write-Host "Checkout: $script:TocRepoRoot"
        if ((Test-Path -LiteralPath $script:TocEnvFile) -and
            (Get-TocEnvValue -Name 'WEB_ADMIN_TOKEN')) {
            Write-Host '[ok] Private configuration (.env)' -ForegroundColor Green
        } else {
            Write-Host '[missing] .env with WEB_ADMIN_TOKEN' -ForegroundColor Red
            $failures++
        }
        $state = Get-TocStateDir
        if (Test-Path -LiteralPath (Join-Path $state 'player')) {
            $count = @(Get-ChildItem -LiteralPath (Join-Path $state 'player') -File).Count
            Write-Host "[ok] Data folder: $state ($count characters)" -ForegroundColor Green
        } else {
            Write-Host "[missing] Data folder $state" -ForegroundColor Red
            $failures++
        }
        $docker = Get-TocDockerExecutable
        if ($docker) {
            Write-Host "[ok] Docker CLI: $docker" -ForegroundColor Green
            $composeExit = Invoke-TocDocker -ArgumentList @('compose', 'version') `
                -AllowFailure -Quiet
            if ($composeExit -eq 0) {
                Write-Host '[ok] Docker Compose v2' -ForegroundColor Green
            } else {
                Write-Host '[missing] Docker Compose v2' -ForegroundColor Red
                $failures++
            }
        } else {
            Write-Host '[missing] Docker CLI' -ForegroundColor Red
            $failures++
        }
        if ($docker -and (Test-TocDockerReady)) {
            Write-Host '[ok] Docker engine is running' -ForegroundColor Green
            $configExit = Invoke-Compose -ArgumentList @('config', '--quiet') -AllowFailure
            if ($configExit -ne 0) {
                $failures++
            }
        } else {
            Write-Host '[stopped] Docker engine' -ForegroundColor Yellow
            $failures++
        }
        if ((Test-Path -LiteralPath (Join-Path $script:TocRepoRoot '.git')) -and (Get-TocCodeChanges)) {
            Write-Host '[warn] Local code changes will stop .\toc.ps1 update' -ForegroundColor Yellow
        }
        if ($failures -ne 0) {
            throw "Doctor found $failures issue(s). Run .\install.ps1 to repair setup."
        }
        Write-Host 'Everything needed to run Times of Chaos is ready.' -ForegroundColor Green
    }
    'update' {
        Initialize-TocRun
        if (Test-Path -LiteralPath (Join-Path $script:TocRepoRoot '.git')) {
            $changes = Get-TocCodeChanges
            if ($LASTEXITCODE -ne 0) {
                throw 'Could not inspect the Git working tree.'
            }
            if ($changes) {
                $changes | Write-Host
                throw 'Update stopped because this checkout has local code changes. Commit, stash, or remove them first.'
            }
            Restore-TocCheckoutState
            Write-Host 'Fetching the newest version...' -ForegroundColor Cyan
            git -C $script:TocRepoRoot pull --ff-only
            if ($LASTEXITCODE -ne 0) {
                throw 'Git could not fast-forward this installation.'
            }
        } else {
            Write-Host 'This copy is not a Git checkout; only the game image is updated.'
        }
        Install-TocImage
        Invoke-Compose -ArgumentList @('up', '-d', '--no-build', 'game') | Out-Null
        Wait-TocGame
        Write-TocEndpoints
    }
    'open' { Open-TocClient }
    'play' { Open-TocClient }
    'admin' { Open-TocDashboard }
    'promote' {
        Assert-TocInstalled
        Invoke-TocPromote -Name $Target -Level $Level
    }
    'backup' {
        Assert-TocInstalled
        $folder = if ($Target) { $Target } else { Join-Path $script:TocRepoRoot 'toc-backups' }
        $archive = New-TocBackup -Folder $folder
        Write-Host "Backed up to $archive" -ForegroundColor Green
        Write-Host 'It holds your dashboard token and every character: keep it private.'
    }
    'restore' {
        Assert-TocInstalled
        if (-not $Target -or -not (Test-Path -LiteralPath $Target)) {
            throw 'Usage: .\toc.ps1 restore <toc-backup-....tar.gz>'
        }
        $archive = (Resolve-Path -LiteralPath $Target).Path
        $work = Join-Path $script:TocRepoRoot ".restore.$(Get-Random)"
        New-Item -ItemType Directory -Path $work | Out-Null
        & tar -xzf $archive -C $work
        $restoredState = Get-ChildItem -LiteralPath $work -Directory |
            Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'player') } |
            Select-Object -First 1
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $work '.env')) -or -not $restoredState) {
            Remove-Item -LiteralPath $work -Recurse -Force
            throw "$archive is not a Times of Chaos backup (.env and a state folder)."
        }
        # Nothing moves until the game is stopped and seen to be stopped,
        # and the data goes where this installation's .env looks for it:
        # that .env stays, and the backup's is kept beside it to read
        # (review, 2026-10-22; toc.sh's restore_backup says why).
        $stopped = $true
        try {
            Stop-TocGame
        } catch {
            $stopped = $false
        }
        if (-not $stopped -or (Test-TocGameRunning)) {
            Remove-Item -LiteralPath $work -Recurse -Force
            throw ('The game could not be stopped, so nothing was restored: the data ' +
                'folder and .env are as they were. Check .\toc.ps1 status, then try again.')
        }
        $state = Get-TocStateDir
        $aside = "$state.before-restore-$(Get-Date -Format yyyyMMdd-HHmmss)"
        if (Test-Path -LiteralPath $state) {
            Move-Item -LiteralPath $state -Destination $aside
            Write-Host "The data that was here is kept in $aside."
        }
        $parent = Split-Path -Parent $state
        if ($parent -and -not (Test-Path -LiteralPath $parent)) {
            New-Item -ItemType Directory -Path $parent | Out-Null
        }
        Move-Item -LiteralPath $restoredState.FullName -Destination $state
        Copy-Item -LiteralPath (Join-Path $work '.env') -Destination "$script:TocEnvFile.from-backup" -Force
        Remove-Item -LiteralPath $work -Recurse -Force
        Write-Host "This installation's settings are unchanged; the backup's are in .env.from-backup."
        Start-TocGame
    }
    'uninstall' {
        $state = Get-TocStateDir
        if ((Get-TocDockerExecutable) -and (Test-TocDockerReady)) {
            Invoke-Compose -ArgumentList @('down', '--remove-orphans') -AllowFailure | Out-Null
            $image = Get-TocEnvValue -Name 'TOC_IMAGE' -Default $script:TocDefaultImage
            Invoke-TocDocker -ArgumentList @('image', 'rm', $image) -AllowFailure -Quiet | Out-Null
        }
        if ($Purge) {
            if (-not $Yes) {
                $answer = Read-Host "Delete $state and .env -- every character and the world state? Type DELETE"
                if ($answer -ne 'DELETE') {
                    Write-Host 'Kept the data.'
                    return
                }
            }
            Remove-Item -LiteralPath $state -Recurse -Force -ErrorAction SilentlyContinue
            Remove-Item -LiteralPath $script:TocEnvFile -Force -ErrorAction SilentlyContinue
            Write-Host 'Times of Chaos is removed, data included. Delete this folder to finish.'
        } else {
            Write-Host "Times of Chaos is removed. Your data is still in $state and .env;"
            Write-Host 'run Install-ToC.cmd to use it again, or .\toc.ps1 uninstall -Purge to delete it.'
        }
    }
    'help' {
        @'
Usage: .\toc.ps1 [command]

  start              Start Times of Chaos (default)
  stop               Stop it; every player is saved and all data kept
  restart            Stop and start again
  status             Show container health and connection addresses
  logs               Follow the game's log
  play | open        Open the web game client
  admin              Open the administration dashboard
  update             Update to the newest version and restart
  build              Rebuild from this checkout and restart
  promote <name>     Make a character the implementor (log it out first)
  backup [folder]    Save .env and all game data to a dated archive
  restore <archive>  Put a backup back (the current data is set aside)
  doctor             Check the installation without changing it
  uninstall          Remove the container and image; -Purge also deletes data
  help               Show this command list
'@ | Write-Host
    }
}
