#requires -Version 5.1
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 THOX.ai LLC.
<#
.SYNOPSIS
Read-only inspection of the Windows volume D: and its backing disk.
.DESCRIPTION
Resolves D: through independent Windows storage associations, lists every
partition on the backing disk, then runs the kit's existing protection inventory.
No plan, disk mutation, automatic elevation or execution-policy change occurs.
A drive letter is a volume name, not proof of an external USB SSD.
#>
[CmdletBinding()]
param([switch]$Json)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# This guard precedes every Windows cmdlet, module import and native API call.
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or -not [Environment]::Is64BitProcess) {
    throw 'Inspect-D-Drive.ps1 requires 64-bit Windows. No storage inspection was attempted on this host.'
}
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open a 64-bit Windows PowerShell console as Administrator for the complete read-only protection assessment. This script does not elevate itself.'
}

function Get-ThoxDMapping {
    try { $psDrive = Get-PSDrive -Name D -PSProvider FileSystem -ErrorAction Stop }
    catch { throw 'D: is not present as a local filesystem drive in this console. No disk was selected.' }
    if ([string]$psDrive.Root -ine 'D:\' -or -not [string]::IsNullOrWhiteSpace([string]$psDrive.DisplayRoot)) {
        throw 'D: is a network or substituted PowerShell path. A unique local mounted volume is required; no disk was selected.'
    }
    $logical = @(Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='D:'" -ErrorAction Stop)
    if ($logical.Count -ne 1) {
        throw 'D: has no unique Windows logical-disk record. Missing drives and SUBST aliases are unsupported.'
    }
    if ($logical[0].DriveType -notin @(2,3) -or -not [string]::IsNullOrWhiteSpace([string]$logical[0].ProviderName)) {
        throw 'D: is a network, optical, unknown or unsupported logical drive. No local SSD mapping was established.'
    }
    $mounted = @(Get-CimInstance -ClassName Win32_Volume -Filter "DriveLetter='D:'" -ErrorAction Stop)
    if ($mounted.Count -ne 1 -or [string]$mounted[0].DeviceID -notmatch '^\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\$') {
        throw 'D: has no unique mounted volume GUID. Network/SUBST aliases or ambiguous mappings are refused.'
    }
    $volumeGuid = [string]$mounted[0].DeviceID
    try {
        $volumes = @(Get-Volume -DriveLetter D -ErrorAction Stop)
        $partitions = @(Get-Partition -DriveLetter D -ErrorAction Stop)
    } catch { throw ('Cannot resolve D: to a local basic-disk partition. SUBST, dynamic/spanned or missing mappings are unsupported. ' + $_.Exception.Message) }
    if ($volumes.Count -ne 1 -or [string]$volumes[0].Path -ine $volumeGuid -or [string]$volumes[0].DriveLetter -ine 'D') {
        throw 'Windows volume providers disagree about D:. No disk was selected.'
    }
    if ($partitions.Count -ne 1 -or [string]$partitions[0].DriveLetter -ine 'D' -or @($partitions[0].AccessPaths) -notcontains $volumeGuid) {
        throw 'D: does not map to exactly one matching partition. Spanned or ambiguous mappings are refused.'
    }
    $partition = $partitions[0]
    $associated = @(Get-CimAssociatedInstance -InputObject $logical[0] -Association Win32_LogicalDiskToPartition -ResultClassName Win32_DiskPartition -ErrorAction Stop)
    if ($associated.Count -ne 1 -or $null -eq $associated[0].DiskIndex -or $null -eq $associated[0].StartingOffset -or
        [long]$associated[0].DiskIndex -ne [long]$partition.DiskNumber -or [long]$associated[0].StartingOffset -ne [long]$partition.Offset) {
        throw 'D: lacks a unique, consistent physical-partition association. SUBST, spanned and ambiguous mappings are refused.'
    }
    $disks = @(Get-Disk -Number $partition.DiskNumber -ErrorAction Stop)
    if ($disks.Count -ne 1 -or $disks[0].Number -ne $partition.DiskNumber -or $null -eq $disks[0].Size -or [long]$disks[0].Size -le 0) {
        throw 'D: does not resolve to one current disk with known capacity.'
    }
    $disk = $disks[0]
    return [pscustomobject][ordered]@{
        DriveLetter = 'D:'
        VolumeGuid = $volumeGuid
        VolumeLabel = [string]$volumes[0].FileSystemLabel
        VolumeBytes = [long]$volumes[0].Size
        PartitionNumber = [int]$partition.PartitionNumber
        PartitionOffset = [long]$partition.Offset
        PartitionBytes = [long]$partition.Size
        Number = [int]$disk.Number
        FriendlyName = [string]$disk.FriendlyName
        UniqueId = ([string]$disk.UniqueId).Trim()
        SerialNumber = ([string]$disk.SerialNumber).Trim()
        Size = [long]$disk.Size
        BusType = [string]$disk.BusType
        IsBoot = $disk.IsBoot
        IsSystem = $disk.IsSystem
        IsOffline = $disk.IsOffline
        IsReadOnly = $disk.IsReadOnly
        NumberOfPartitions = $disk.NumberOfPartitions
    }
}

$mapping = Get-ThoxDMapping
$allPartitions = @(Get-Partition -DiskNumber $mapping.Number -ErrorAction Stop | Sort-Object Offset)
if ($null -eq $mapping.NumberOfPartitions -or $allPartitions.Count -ne [long]$mapping.NumberOfPartitions -or $allPartitions.Count -lt 1) {
    throw 'The backing disk partition inventory is incomplete or changed. Repeat this read-only inspection.'
}
$partitionRecords = @()
foreach ($partition in $allPartitions) {
    if ($partition.DiskNumber -ne $mapping.Number) { throw 'A partition moved to another disk during inspection. Repeat inventory.' }
    $volumeRecords = @(); $labelStatus = 'unknown'; $labelError = $null
    try {
        $observedVolumes = @(Get-Volume -Partition $partition -ErrorAction Stop)
        foreach ($volume in $observedVolumes) {
            $volumeRecords += [pscustomobject]@{
                VolumeGuid = [string]$volume.Path
                DriveLetter = [string]$volume.DriveLetter
                FileSystem = [string]$volume.FileSystem
                LabelKnown = ($volume.FileSystemLabel -is [string])
                Label = $volume.FileSystemLabel
                Bytes = $volume.Size
            }
        }
        if ($volumeRecords.Count -eq 1 -and $volumeRecords[0].LabelKnown) { $labelStatus = 'readable' }
        else { $labelError = 'No uniquely readable Windows filesystem label. This may be reserved space or a foreign filesystem; the protection inventory decides eligibility.' }
    } catch { $labelError = $_.Exception.Message }
    $partitionRecords += [pscustomobject]@{
        DiskNumber = $partition.DiskNumber
        PartitionNumber = $partition.PartitionNumber
        Offset = $partition.Offset
        Bytes = $partition.Size
        Type = [string]$partition.Type
        GptType = [string]$partition.GptType
        AccessPaths = [string[]]@($partition.AccessPaths)
        LabelStatus = $labelStatus
        LabelError = $labelError
        Volumes = [object[]]$volumeRecords
    }
}

# These existing exports perform read-only host/device/protection assessment.
Import-Module (Join-Path $PSScriptRoot 'Thox.ExternalSsd.psm1') -Force -DisableNameChecking
$hostSnapshot = Get-ThoxHostSnapshot
$inventory = @(Get-ThoxDiskInventory -IncludeEligibility)
$assessment = @($inventory | Where-Object { $_.Number -eq $mapping.Number })
if ($assessment.Count -ne 1 -or $assessment[0].UniqueId -cne $mapping.UniqueId -or
    $assessment[0].SerialNumber -cne $mapping.SerialNumber -or $assessment[0].Size -ne $mapping.Size) {
    throw 'D: backing-disk identity changed or disagrees with the protection inventory. Repeat inspection.'
}
$refreshed = Get-ThoxDMapping
if ((ConvertTo-Json -InputObject $mapping -Compress) -cne (ConvertTo-Json -InputObject $refreshed -Compress)) {
    throw 'D: mapping or backing-disk metadata changed during inspection. Repeat inspection; no disk was selected or written.'
}
$result = [pscustomobject]@{
    Schema = 'thox.external-ssd.drive-d-inspection.v1'
    ObservedUtc = [DateTimeOffset]::UtcNow.ToString('o')
    State = 'read-only-inspection-no-plan-no-disk-write'
    Mapping = $mapping
    AllBackingDiskPartitions = [object[]]$partitionRecords
    BackingDiskAssessment = $assessment[0]
    Host = $hostSnapshot
    AllDisks = [object[]]$inventory
    Meaning = 'D: identifies one volume. Provisioning, if separately planned and confirmed, erases the entire eligible backing disk, including every partition listed here. This snapshot does not authorize a write.'
}
if ($Json) { ConvertTo-Json -InputObject $result -Depth 16 }
else {
    Write-Host 'D: volume and backing disk reported by Windows'
    $mapping | Format-List
    Write-Host 'Every partition on that backing disk (unknown labels remain explicit)'
    foreach ($record in $partitionRecords) {
        $record | Format-List DiskNumber, PartitionNumber, Offset, Bytes, Type, GptType, AccessPaths, LabelStatus, LabelError
        $record.Volumes | Format-List
    }
    Write-Host 'Existing THOX protection assessment for the backing disk'
    $assessment[0] | Format-List EligibleForPlanning, EligibilityReason, PartitionInventoryComplete, PartitionInventoryError, VolumeInventoryComplete, HandleProbeError, MediaTypeNote
    Write-Host 'Host and full disk inventory'
    $hostSnapshot | Format-List
    $inventory | Format-List Number, FriendlyName, UniqueId, SerialNumber, Size, BusType, IsBoot, IsSystem, EligibleForPlanning, EligibilityReason
    Write-Host $result.Meaning
    Write-Host 'Read-only inspection finished. No plan was created and no disk was selected, formatted, offlined or written. Use -Json for the complete record.'
}
