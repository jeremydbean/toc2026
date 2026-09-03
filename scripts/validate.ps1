param(
    [string]$Distro = "Ubuntu",
    [int]$SmokePort = 9999,
    [switch]$RunSmoke
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Script
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Script
}

function Assert-NativeSuccess {
    param([string]$Label)

    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Wsl {
    param(
        [string]$Command,
        [int[]]$AllowedExitCodes = @(0)
    )

    wsl -d $Distro -- bash -lc $Command
    $ExitCode = $LASTEXITCODE
    if ($ExitCode -notin $AllowedExitCodes) {
        throw "WSL command failed with exit code $ExitCode"
    }
}

if ($RepoRoot -notmatch '^[A-Za-z]:\\') {
    throw "Expected a Windows drive path, got: $RepoRoot"
}
$Drive = $RepoRoot.Substring(0, 1).ToLowerInvariant()
$PathRemainder = $RepoRoot.Substring(2).Replace('\', '/')
$WslRepo = "/mnt/$Drive$PathRemainder"

$StrictWarnings = "-Wall -Wextra -Wshadow -Wsign-compare -Wformat-overflow=2 -Wunused-parameter -Wstrict-prototypes -Wold-style-definition -Wmissing-prototypes -Wcast-qual"

Invoke-Step "C clean build" {
    Invoke-Wsl "cd '$WslRepo' && make clean && make"
}

Invoke-Step "C strict warning build" {
    Invoke-Wsl "cd '$WslRepo' && make clean && make `"WARNFLAGS=$StrictWarnings`""
}

Invoke-Step "C area validation mode" {
    Invoke-Wsl "cd '$WslRepo/area' && ../merc --check-area"
}

Invoke-Step "C list iterator sanitizer test" {
    # Guards the deferred-free contract in src/list.c: extract_char() removes
    # the element a FOR_EACH_CHARACTER loop is standing on, so freeing nodes
    # eagerly left the iterator cursor dangling.
    Invoke-Wsl "cd '$WslRepo' && bin=\$(mktemp) && gcc -g -fsanitize=address,undefined -Isrc -o \$bin tests/test_list_iterator.c src/list.c && ASAN_OPTIONS=detect_leaks=1 \$bin; rc=\$?; rm -f \$bin; exit \$rc"
}

if ($RunSmoke) {
    Invoke-Step "C startup smoke on port $SmokePort" {
        Invoke-Wsl "cd '$WslRepo/area' && timeout 25s ../merc $SmokePort" @(0, 124, 143)
    }
}

Invoke-Step "Python syntax" {
    & $Python -m py_compile `
        (Join-Path $RepoRoot "webadmin\server.py") `
        (Join-Path $RepoRoot "webadmin\area_parser.py") `
        (Join-Path $RepoRoot "webadmin\area_health.py") `
        (Join-Path $RepoRoot "scripts\player_watcher.py") `
        (Join-Path $RepoRoot "scripts\web_server.py") `
        (Join-Path $RepoRoot "scripts\area_lint.py") `
        (Join-Path $RepoRoot "scripts\extract_zelda_reference.py") `
        (Join-Path $RepoRoot "scripts\extract_zelda_entities.py") `
        (Join-Path $RepoRoot "scripts\extract_zelda_doors.py") `
        (Join-Path $RepoRoot "scripts\build_hyrule_manifest.py") `
        (Join-Path $RepoRoot "scripts\build_hyrule_area.py")
    Assert-NativeSuccess "Python syntax"
}

Invoke-Step "Area data checks" {
    Push-Location $RepoRoot
    try {
        & $Python check_parser.py
        Assert-NativeSuccess "Area parser check"
        & $Python check_exits.py
        Assert-NativeSuccess "Exit check"
        & $Python check_resets.py
        Assert-NativeSuccess "Reset check"
        & $Python check_shops.py
        Assert-NativeSuccess "Shop check"
        & $Python scripts\area_lint.py --fail-on critical --limit 20
        Assert-NativeSuccess "Area health check"
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Unit tests" {
    Push-Location $RepoRoot
    try {
        & $Python -m unittest discover -s tests
        Assert-NativeSuccess "Unit tests"
    }
    finally {
        Pop-Location
    }
}

Invoke-Step "Git whitespace check" {
    Push-Location $RepoRoot
    try {
        git diff --check
        Assert-NativeSuccess "Git whitespace check"
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Validation complete." -ForegroundColor Green
