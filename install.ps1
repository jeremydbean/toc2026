[CmdletBinding()]
param(
    [ValidateSet('Preserve', 'Local', 'Public')]
    [string]$Network = 'Preserve',
    [switch]$NoStart,
    [switch]$NoBrowser,
    [switch]$SkipPrerequisites
)

$ErrorActionPreference = 'Stop'
$setup = Join-Path $PSScriptRoot 'scripts\setup_windows.ps1'
& $setup @PSBoundParameters
