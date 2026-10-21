# Shared installer and launcher helpers. Dot-source this file; do not run it.

$script:TocRepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$script:TocEnvFile = Join-Path $script:TocRepoRoot '.env'
$script:TocDockerWaitSeconds = 300
$script:TocGameWaitSeconds = 180

function Get-TocEnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [string]$Default = ''
    )

    if (-not (Test-Path -LiteralPath $script:TocEnvFile)) {
        return $Default
    }

    $match = Get-Content -LiteralPath $script:TocEnvFile |
        Where-Object { $_ -match "^$([regex]::Escape($Name))=" } |
        Select-Object -First 1
    if ($null -eq $match) {
        return $Default
    }

    $value = ($match -split '=', 2)[1]
    if ([string]::IsNullOrEmpty($value)) {
        return $Default
    }
    return $value
}

function Set-TocEnvValue {
    param(
        [Parameter(Mandatory)]
        [string]$Name,
        [Parameter(Mandatory)]
        [string]$Value
    )

    $lines = if (Test-Path -LiteralPath $script:TocEnvFile) {
        @(Get-Content -LiteralPath $script:TocEnvFile)
    } else {
        @()
    }

    $output = [Collections.Generic.List[string]]::new()
    $found = $false
    $pattern = "^$([regex]::Escape($Name))="
    foreach ($line in $lines) {
        if ($line -match $pattern) {
            if (-not $found) {
                $output.Add("$Name=$Value")
                $found = $true
            }
            continue
        }
        $output.Add($line)
    }
    if (-not $found) {
        $output.Add("$Name=$Value")
    }

    [IO.File]::WriteAllLines(
        $script:TocEnvFile,
        $output,
        [Text.UTF8Encoding]::new($false)
    )
}

function New-TocToken {
    $bytes = New-Object byte[] 32
    $generator = [Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}

# An installation is this checkout (code), a private .env (settings and
# the dashboard token) and the state folder (TOC_STATE, .\state by
# default): everything the game writes. The game never writes into the
# checkout, so update can always fast-forward it, and a backup is .env
# plus the state folder. See scripts/toc_common.sh, which this mirrors.
$script:TocDefaultImage = 'ghcr.io/jeremydbean/toc2026:latest'
$script:TocLegacyDirs = @('player', 'gods', 'heroes', 'corpse', 'backups', 'log')
$script:TocStateDirs = @('area', 'player', 'gods', 'heroes', 'corpse', 'backups', 'log')

function Get-TocStateDir {
    $configured = Get-TocEnvValue -Name 'TOC_STATE' -Default './state'
    if ([IO.Path]::IsPathRooted($configured)) {
        return $configured
    }
    $relative = $configured -replace '^\.[\\/]', ''
    return (Join-Path $script:TocRepoRoot $relative)
}

# Whether toc2026_game is a container from before the state folder: one
# whose world is not a bind mount, and so holds the only copy of its
# notes, reports and max-load counts.
function Test-TocLegacyContainer {
    if ((Get-TocEnvValue -Name 'TOC_MODE' -Default 'docker') -ne 'docker') { return $false }
    $docker = Get-TocDockerExecutable
    if (-not $docker -or -not (Test-TocDockerReady)) { return $false }
    & $docker container inspect toc2026_game *> $null
    if ($LASTEXITCODE -ne 0) { return $false }
    $mountType = & $docker container inspect -f `
        '{{range .Mounts}}{{if eq .Destination "/app/area"}}{{.Type}}{{end}}{{end}}' toc2026_game 2>$null
    return ($mountType -notmatch 'bind')
}

function Add-TocMigrationMark {
    param([Parameter(Mandatory)][string]$State)
    Add-Content -LiteralPath (Join-Path $State '.migrated-from-checkout') `
        -Value "migrated $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') from the checkout"
}

function Invoke-TocCheckoutMigration {
    param([Parameter(Mandatory)][string]$State)

    $moved = $false
    foreach ($directory in $script:TocLegacyDirs) {
        $source = Join-Path $script:TocRepoRoot $directory
        if ((Test-Path -LiteralPath $source) -and (Get-ChildItem -LiteralPath $source -Force | Select-Object -First 1)) {
            $target = Join-Path $State $directory
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
            $moved = $true
        }
    }
    if ($moved) {
        Add-TocMigrationMark -State $State
        Write-Host "Moved this installation's data into $State." -ForegroundColor Green
        Write-Host 'Back up that folder and .env from now on; the checkout holds code only.'
    }
}

function Invoke-TocContainerMigration {
    param([Parameter(Mandatory)][string]$State)

    $areaTarget = Join-Path $State 'area'
    New-Item -ItemType Directory -Path $areaTarget -Force | Out-Null
    $exit = Invoke-TocDocker -ArgumentList @('cp', 'toc2026_game:/app/area/.', $areaTarget) -AllowFailure -Quiet
    if ($exit -eq 0) {
        Write-Host "Copied the world's runtime files out of the old container." -ForegroundColor Green
        Invoke-TocDocker -ArgumentList @('rm', 'toc2026_game') -AllowFailure -Quiet | Out-Null
        Add-TocMigrationMark -State $State
    } else {
        Write-Warning 'Could not copy the world out of the old container; it was left in place.'
    }
}

function Import-TocRepositoryPlayers {
    param([Parameter(Mandatory)][string]$State)

    if (Get-ChildItem -LiteralPath (Join-Path $State 'player') -Force | Select-Object -First 1) {
        Write-Host 'The state folder already has characters; nothing was imported.'
        return
    }
    foreach ($directory in 'player', 'gods', 'heroes') {
        $source = Join-Path $script:TocRepoRoot $directory
        if (Test-Path -LiteralPath $source) {
            $target = Join-Path $State $directory
            New-Item -ItemType Directory -Path $target -Force | Out-Null
            Copy-Item -Path (Join-Path $source '*') -Destination $target -Recurse -Force
        }
    }
    Write-Host "Imported the repository's characters into $State." -ForegroundColor Green
}

function Initialize-TocInstance {
    param(
        [ValidateSet('Preserve', 'Local', 'Public')]
        [string]$Network = 'Preserve',
        [switch]$ImportPlayers
    )

    # An installation from before the state folder: a .env the old
    # installers wrote, which never had TOC_MODE. (A .env copied from
    # .env.example has it, and is a new install.)
    $existed = (Test-Path -LiteralPath $script:TocEnvFile) -and
        [string]::IsNullOrEmpty((Get-TocEnvValue -Name 'TOC_MODE'))
    if (-not (Test-Path -LiteralPath $script:TocEnvFile)) {
        $lines = @(
            '# Generated by the Times of Chaos installer. Do not commit this file.'
            '# Rerunning the installer keeps every value here, the token included.'
            'TOC_MODE=docker'
            'TOC_STATE=./state'
            "TOC_IMAGE=$script:TocDefaultImage"
            'MUD_BIND=127.0.0.1'
            'MUD_PORT=9000'
            'WEB_ADMIN_BIND=127.0.0.1'
            'WEB_ADMIN_PORT=9001'
            'WEB_ADMIN_ENABLED=1'
            'WEB_ADMIN_LOCAL_UNLOCK=1'
            'TOC_UID=1000'
            'TOC_GID=1000'
            "WEB_ADMIN_TOKEN=$(New-TocToken)"
        )
        [IO.File]::WriteAllLines(
            $script:TocEnvFile,
            $lines,
            [Text.UTF8Encoding]::new($false)
        )
        Write-Host 'Created private runtime configuration in .env.' -ForegroundColor Green
    } else {
        $defaults = [ordered]@{
            TOC_MODE = 'docker'
            TOC_STATE = './state'
            TOC_IMAGE = $script:TocDefaultImage
            MUD_BIND = '127.0.0.1'
            MUD_PORT = '9000'
            WEB_ADMIN_BIND = '127.0.0.1'
            WEB_ADMIN_PORT = '9001'
            WEB_ADMIN_ENABLED = '1'
            WEB_ADMIN_LOCAL_UNLOCK = '1'
            TOC_UID = '1000'
            TOC_GID = '1000'
        }
        foreach ($entry in $defaults.GetEnumerator()) {
            if ([string]::IsNullOrEmpty((Get-TocEnvValue -Name $entry.Key))) {
                Set-TocEnvValue -Name $entry.Key -Value $entry.Value
            }
        }
        if ([string]::IsNullOrEmpty((Get-TocEnvValue -Name 'WEB_ADMIN_TOKEN'))) {
            Set-TocEnvValue -Name 'WEB_ADMIN_TOKEN' -Value (New-TocToken)
            Write-Host 'Added a random dashboard token to the existing .env file.' `
                -ForegroundColor Green
        }
    }

    switch ($Network) {
        'Local' { Set-TocEnvValue -Name 'MUD_BIND' -Value '127.0.0.1' }
        'Public' { Set-TocEnvValue -Name 'MUD_BIND' -Value '0.0.0.0' }
    }

    $state = Get-TocStateDir
    $legacyContainer = Test-TocLegacyContainer
    if ($legacyContainer) {
        # Its players save into the checkout's player folder as it stops,
        # so stop it before anything is copied.
        Invoke-TocDocker -ArgumentList @('stop', '-t', '60', 'toc2026_game') -AllowFailure -Quiet | Out-Null
    }
    if (-not (Test-Path -LiteralPath (Join-Path $state '.layout'))) {
        New-Item -ItemType Directory -Path $state -Force | Out-Null
        if ($existed) {
            Invoke-TocCheckoutMigration -State $state
        }
        Set-Content -LiteralPath (Join-Path $state '.layout') -Value '1'
    }
    if ($legacyContainer) {
        Invoke-TocContainerMigration -State $state
    }
    foreach ($directory in $script:TocStateDirs) {
        New-Item -ItemType Directory -Path (Join-Path $state $directory) -Force | Out-Null
    }
    if ($ImportPlayers) {
        Import-TocRepositoryPlayers -State $state
    }
}

# After a move out of the checkout its player, gods, heroes and log
# folders are no longer live: put git's copies back so a pull can
# fast-forward. The data is in the state folder.
function Restore-TocCheckoutState {
    $state = Get-TocStateDir
    if (-not (Test-Path -LiteralPath (Join-Path $state '.migrated-from-checkout'))) { return }
    if (-not (Test-Path -LiteralPath (Join-Path $script:TocRepoRoot '.git'))) { return }
    $restored = $false
    foreach ($directory in 'player', 'gods', 'heroes', 'log') {
        # One at a time: a directory git does not track would fail the
        # whole checkout.
        git -C $script:TocRepoRoot ls-files --error-unmatch $directory *> $null
        if ($LASTEXITCODE -ne 0) { continue }
        git -C $script:TocRepoRoot diff --quiet -- $directory 2>$null
        if ($LASTEXITCODE -ne 0) {
            git -C $script:TocRepoRoot checkout -- $directory
            if ($LASTEXITCODE -eq 0) { $restored = $true }
        }
    }
    if ($restored) {
        Write-Host "Restored the checkout's copies of player, gods, heroes and log (your data is in $state)."
    }
}

function Get-TocCodeChanges {
    git -C $script:TocRepoRoot status --porcelain -- . `
        ':(exclude)player' ':(exclude)gods' ':(exclude)heroes' `
        ':(exclude)log' ':(exclude)corpse' ':(exclude)backups' ':(exclude)state'
}

# Have an image to run: the published one unless TOC_BUILD=local or a
# build is forced; a pull that fails falls back to building this checkout.
function Install-TocImage {
    param([switch]$Build)

    $arguments = @('compose', '--project-directory', $script:TocRepoRoot)
    if ($Build -or (Get-TocEnvValue -Name 'TOC_BUILD') -eq 'local') {
        Write-Host 'Building the Times of Chaos image from this checkout...' -ForegroundColor Cyan
        Invoke-TocDocker -ArgumentList ($arguments + @('build', 'game')) | Out-Null
        return
    }
    $image = Get-TocEnvValue -Name 'TOC_IMAGE' -Default $script:TocDefaultImage
    Write-Host "Fetching the prebuilt Times of Chaos image ($image)..." -ForegroundColor Cyan
    $exit = Invoke-TocDocker -ArgumentList ($arguments + @('pull', '--quiet', 'game')) -AllowFailure -Quiet
    if ($exit -ne 0) {
        Write-Host 'No prebuilt image could be fetched; building from this checkout instead (a few minutes).' -ForegroundColor Yellow
        Invoke-TocDocker -ArgumentList ($arguments + @('build', 'game')) | Out-Null
    }
}

# Make a character the implementor from its file. Log it out first: the
# game writes its own copy over the file on quit.
function Invoke-TocPromote {
    param(
        [string]$Name,
        [int]$Level = 70
    )

    if ($Name -notmatch '^[A-Za-z]+$') { throw 'A character name is letters only.' }
    if ($Level -lt 1 -or $Level -gt 70) { throw 'The level is 1 to 70 (70 is the implementor).' }
    $capitalized = $Name.Substring(0, 1).ToUpperInvariant() + $Name.Substring(1).ToLowerInvariant()
    $state = Get-TocStateDir
    $file = Join-Path (Join-Path $state 'player') $capitalized
    if (-not (Test-Path -LiteralPath $file)) {
        throw "No saved character named $capitalized. Create it in the game, QUIT, and run this again."
    }
    $lines = [IO.File]::ReadAllLines($file, [Text.Encoding]::GetEncoding(28591))
    $index = [Array]::FindIndex($lines, [Predicate[string]]{ param($l) $l.StartsWith('Levl ') })
    if ($index -lt 0) { throw "$file does not look like a character file." }
    $backups = Join-Path $state 'backups'
    New-Item -ItemType Directory -Path $backups -Force | Out-Null
    Copy-Item -LiteralPath $file -Destination (Join-Path $backups "$capitalized.before-promote-$(Get-Date -Format yyyyMMdd-HHmmss)")
    $lines[$index] = "Levl $Level"
    # The game writes LF; keep it.
    [IO.File]::WriteAllText($file, (($lines -join "`n") + "`n"), [Text.Encoding]::GetEncoding(28591))
    Write-Host "$capitalized is now level $Level. Log in to use it." -ForegroundColor Green
    if ($Level -ge 60) { Write-Host 'Type WIZHELP in the game for the staff commands.' }
}

function New-TocBackup {
    param([string]$Folder = (Join-Path $script:TocRepoRoot 'toc-backups'))

    $state = Get-TocStateDir
    New-Item -ItemType Directory -Path $Folder -Force | Out-Null
    $archive = Join-Path $Folder "toc-backup-$(Get-Date -Format yyyyMMdd-HHmmss).tar.gz"
    $queue = Join-Path (Join-Path $state 'area') 'webadmin.queue'
    if (Test-Path -LiteralPath $queue) {
        # Ask the running game to save everyone first.
        Add-Content -LiteralPath $queue -Value 'command|fsave' -NoNewline:$false
        Start-Sleep -Seconds 3
    }
    $stateName = Split-Path -Leaf $state
    & tar -czf $archive -C $script:TocRepoRoot .env -C (Split-Path -Parent $state) `
        --exclude "$stateName/venv" --exclude "$stateName/run" $stateName
    if ($LASTEXITCODE -ne 0) { throw 'The backup archive could not be written.' }
    return $archive
}

function Get-TocDockerExecutable {
    $command = Get-Command docker -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\resources\bin\docker.exe')
        (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\resources\bin\docker.exe')
        (Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }
    return $null
}

function Invoke-TocDocker {
    param(
        [Parameter(Mandatory)]
        [string[]]$ArgumentList,
        [switch]$AllowFailure,
        [switch]$Quiet
    )

    $docker = Get-TocDockerExecutable
    if (-not $docker) {
        throw 'Docker was not found. Run .\install.ps1 first.'
    }

    # Docker's own output goes to the console, so the function returns
    # only the exit code.
    if ($Quiet) {
        & $docker @ArgumentList *> $null
    } else {
        & $docker @ArgumentList | Out-Host
    }
    $exitCode = $LASTEXITCODE
    if (-not $AllowFailure -and $exitCode -ne 0) {
        throw "docker $($ArgumentList -join ' ') failed with exit code $exitCode"
    }
    return $exitCode
}

function Test-TocDockerReady {
    $docker = Get-TocDockerExecutable
    if (-not $docker) {
        return $false
    }
    & $docker info *> $null
    return $LASTEXITCODE -eq 0
}

function Start-TocDocker {
    param([int]$WaitSeconds = $script:TocDockerWaitSeconds)

    if (Test-TocDockerReady) {
        return
    }

    Write-Host 'Starting Docker Desktop...' -ForegroundColor Cyan
    $docker = Get-TocDockerExecutable
    if ($docker) {
        & $docker desktop start --detach --timeout $WaitSeconds *> $null
    }

    if (-not (Test-TocDockerReady)) {
        $desktopCandidates = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe')
            (Join-Path $env:LOCALAPPDATA 'Programs\Docker\Docker\Docker Desktop.exe')
            (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
        )
        foreach ($desktop in $desktopCandidates) {
            if (Test-Path -LiteralPath $desktop) {
                # First launch can require an interactive Docker agreement.
                Start-Process -FilePath $desktop
                break
            }
        }
    }

    $deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
    while (-not (Test-TocDockerReady)) {
        if ([DateTime]::UtcNow -ge $deadline) {
            throw "Docker did not become ready within $WaitSeconds seconds. Open Docker Desktop, complete any first-run prompts, and rerun the command."
        }
        Start-Sleep -Seconds 3
    }
}

function Wait-TocGame {
    param([int]$WaitSeconds = $script:TocGameWaitSeconds)

    $docker = Get-TocDockerExecutable
    $containerId = & $docker compose --project-directory $script:TocRepoRoot `
        ps -q game | Select-Object -First 1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($containerId)) {
        throw 'The ToC container was not created.'
    }

    Write-Host -NoNewline 'Waiting for Times of Chaos'
    $deadline = [DateTime]::UtcNow.AddSeconds($WaitSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $health = & $docker inspect --format `
            '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' `
            $containerId 2>$null
        switch ($health) {
            'healthy' {
                Write-Host ' ready.' -ForegroundColor Green
                return
            }
            { $_ -in 'unhealthy', 'exited', 'dead' } {
                Write-Host ' failed.' -ForegroundColor Red
                & $docker compose --project-directory $script:TocRepoRoot `
                    logs --tail 80 game
                throw "The ToC container entered the '$health' state."
            }
        }
        Write-Host -NoNewline '.'
        Start-Sleep -Seconds 3
    }

    Write-Host ' timed out.' -ForegroundColor Red
    & $docker compose --project-directory $script:TocRepoRoot logs --tail 80 game
    throw "Times of Chaos did not become healthy within $WaitSeconds seconds."
}

function Write-TocEndpoints {
    $mudBind = Get-TocEnvValue -Name 'MUD_BIND' -Default '127.0.0.1'
    $mudPort = Get-TocEnvValue -Name 'MUD_PORT' -Default '9000'
    $webPort = Get-TocEnvValue -Name 'WEB_ADMIN_PORT' -Default '9001'
    if ($mudBind -eq '0.0.0.0') {
        $mudBind = 'every address of this computer'
    }

    Write-Host ''
    Write-Host 'Times of Chaos is running.' -ForegroundColor Green
    Write-Host "Play in a browser: http://127.0.0.1:$webPort/client"
    Write-Host "MUD client:        localhost port $mudPort ($mudBind)"
    Write-Host "Administration:    http://127.0.0.1:$webPort"
    Write-Host "Your data:         $(Get-TocStateDir)"
    Write-Host 'Commands:          .\toc.ps1 play | admin | status | logs | stop | update | promote <name> | backup'
}

function Open-TocClient {
    $webPort = Get-TocEnvValue -Name 'WEB_ADMIN_PORT' -Default '9001'
    Start-Process "http://127.0.0.1:$webPort/client"
}

function Open-TocDashboard {
    $webPort = Get-TocEnvValue -Name 'WEB_ADMIN_PORT' -Default '9001'
    Start-Process "http://127.0.0.1:$webPort"
}
