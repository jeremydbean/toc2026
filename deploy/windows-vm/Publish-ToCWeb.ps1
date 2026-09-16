<#
.SYNOPSIS
    Publish (or withdraw) the Times of Chaos web interface on TCP 9001.

.DESCRIPTION
    The VM sits behind the TOC-NAT Hyper-V NAT, so reaching a guest port from
    outside takes three things, and this script owns the two that live on this
    host:

      1. a NAT static mapping, external 9001 -> 172.28.90.2:9001
      2. an inbound Windows Firewall rule for TCP 9001
      3. a port forward on the router  <- not this script; do it yourself

    Written to match the shape of the existing TOC-Public-Game rule for 9000.
    Run it from an elevated PowerShell.

.PARAMETER Remove
    Withdraw the mapping and the rule instead of creating them. The web
    interface goes private again; the game on 9000 is untouched either way.

.EXAMPLE
    .\Publish-ToCWeb.ps1
    .\Publish-ToCWeb.ps1 -Remove
#>
[CmdletBinding()]
param(
    [switch]$Remove,
    [string]$NatName = 'TOC-NAT',
    [string]$VmAddress = '172.28.90.2',
    [int]$Port = 9001,
    [string]$RuleName = 'TOC-Public-Web'
)

$ErrorActionPreference = 'Stop'

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this from an elevated PowerShell: it changes NAT and firewall state.'
}

function Test-Port {
    param([string]$Address, [int]$TcpPort, [int]$TimeoutMs = 3000)
    $client = New-Object Net.Sockets.TcpClient
    try {
        $handle = $client.BeginConnect($Address, $TcpPort, $null, $null)
        return $handle.AsyncWaitHandle.WaitOne($TimeoutMs) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Get-Mapping {
    Get-NetNatStaticMapping -NatName $NatName -ErrorAction SilentlyContinue |
        Where-Object { $_.Protocol -eq 'TCP' -and $_.ExternalPort -eq $Port }
}

if ($Remove) {
    $mapping = Get-Mapping
    if ($mapping) {
        # Address it by id rather than relying on pipeline binding.
        Remove-NetNatStaticMapping -NatName $NatName `
            -StaticMappingID $mapping.StaticMappingID -Confirm:$false
        Write-Host "Removed NAT mapping for TCP $Port."
    } else {
        Write-Host "No NAT mapping for TCP $Port."
    }

    $rule = Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue
    if ($rule) {
        $rule | Remove-NetFirewallRule
        Write-Host "Removed firewall rule $RuleName."
    } else {
        Write-Host "No firewall rule named $RuleName."
    }

    Write-Host ''
    Write-Host 'The web interface is private again. Remove the router forward too.'
    return
}

if (Get-Mapping) {
    Write-Host "NAT mapping for TCP $Port already exists."
} else {
    # Add-, not New-: the NetNat module has no New-NetNatStaticMapping.
    Add-NetNatStaticMapping -NatName $NatName -Protocol TCP `
        -ExternalIPAddress '0.0.0.0' -ExternalPort $Port `
        -InternalIPAddress $VmAddress -InternalPort $Port | Out-Null
    Write-Host "Added NAT mapping: external TCP $Port -> ${VmAddress}:$Port."
}

if (Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue) {
    Write-Host "Firewall rule $RuleName already exists."
} else {
    New-NetFirewallRule -Name $RuleName `
        -DisplayName "TOC public web TCP $Port" `
        -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port `
        -Profile Any | Out-Null
    Write-Host "Added firewall rule $RuleName for TCP $Port."
}

# A recorded mapping is not a working one. WinNAT keeps serving the set it had
# when it started, so a mapping added afterwards reads back Active while
# nothing is translated. Prove the path rather than trust the object.
Write-Host ''
if (-not (Test-Port -Address $VmAddress -TcpPort $Port)) {
    Write-Warning "The VM is not answering on ${VmAddress}:$Port. Check toc-web inside the guest; nothing on this host can help until it does."
    return
}

if (Test-Port -Address '127.0.0.1' -TcpPort $Port) {
    Write-Host "Verified: this host forwards TCP $Port into the VM."
} else {
    Write-Warning "The mapping is recorded but WinNAT is not forwarding TCP $Port yet."
    Write-Host ''
    Write-Host '  WinNAT only applies static mappings that existed when it started.'
    Write-Host '  Restart it to pick this one up:'
    Write-Host ''
    Write-Host '      net stop winnat; net start winnat'
    Write-Host ''
    Write-Host '  That interrupts the game on 9000 as well, briefly, so do it when'
    Write-Host '  nobody is connected. Then re-run this script to verify.'
    return
}

Write-Host ''
Write-Host 'Host side done. Still required:'
Write-Host "  - forward TCP $Port on the router to this machine"
Write-Host ''
Write-Host 'Then check from outside the network (a phone on cellular works):'
Write-Host "  http://toc.jeremybean.com:$Port/client"
Write-Host ''
Write-Host 'The admin console at / and every /api admin route stay behind the'
Write-Host 'token. Keep WEB_ADMIN_LOCAL_UNLOCK=0 in /etc/toc/web.env.'
