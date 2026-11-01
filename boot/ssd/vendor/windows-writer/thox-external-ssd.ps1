#requires -Version 5.1
<#
.SYNOPSIS
Read-only by default: inspect, plan, and provision a pinned THOX raw image to a specifically confirmed external USB SSD.
.DESCRIPTION
No image write occurs without command write, -Apply, an exact fresh plan, and local interactive typed confirmation.
Run in a 64-bit Windows PowerShell console. Native commands require administrator access.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'None')]
param(
    [Parameter(Position = 0)]
    [ValidateSet('inventory', 'preflight', 'plan', 'write', 'verify', 'status')]
    [string]$Command = 'inventory',
    [string]$ManifestPath,
    [string]$ExpectedManifestSha256,
    [string]$DiskUniqueId,
    [string]$DiskSerial,
    [long]$ExpectedDiskBytes,
    [string]$PlanPath,
    [string]$ReceiptDirectory,
    [string]$ReceiptPath,
    [switch]$Apply,
    [switch]$Json
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot 'Thox.ExternalSsd.psm1') -Force -DisableNameChecking

try {
    if ($Apply -and $Command -cne 'write') { throw '-Apply is supported only with write.' }
    $result = $null
    switch ($Command) {
        'inventory' { $result = [pscustomobject]@{ Host = Get-ThoxHostSnapshot; Disks = @(Get-ThoxDiskInventory -IncludeEligibility); State = 'read-only-inventory-no-disk-write' } }
        'preflight' { $result = Get-ThoxPreflight -ManifestPath $ManifestPath -ExpectedManifestSha256 $ExpectedManifestSha256 }
        'plan' {
            $parameters = @{
                ManifestPath = $ManifestPath; ExpectedManifestSha256 = $ExpectedManifestSha256
                DiskUniqueId = $DiskUniqueId; DiskSerial = $DiskSerial; ExpectedDiskBytes = $ExpectedDiskBytes
                PlanPath = $PlanPath; ReceiptDirectory = $ReceiptDirectory
            }
            $result = New-ThoxDiskPlan @parameters -WhatIf:$WhatIfPreference
        }
        'write' { $result = Invoke-ThoxDiskWrite -PlanPath $PlanPath -Apply:$Apply -WhatIf:$WhatIfPreference }
        'verify' { $result = Test-ThoxWrittenDisk -PlanPath $PlanPath }
        'status' { $result = Get-ThoxReceipt -ReceiptPath $ReceiptPath }
    }
    if ($Json) { ConvertTo-Json -InputObject $result -Depth 14 }
    elseif ($Command -ceq 'inventory') {
        $result.Host | Format-List
        $result.Disks | Format-List Number, FriendlyName, BusType, SerialNumber, UniqueId, Size, LogicalSectorSize, PhysicalSectorSize, IsBoot, IsSystem, IsOffline, IsReadOnly, HealthStatus, EligibleForPlanning, EligibilityReason, Volumes, HandleProbeError, MediaTypeNote
        Write-Host 'Inventory only. No disk has been selected or written. Use -Json for the complete identity/volume record.'
    } else { $result | Format-List }
} catch {
    Write-Error -ErrorRecord $_
    exit 1
}
