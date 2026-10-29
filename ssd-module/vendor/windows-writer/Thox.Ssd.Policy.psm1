# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 THOX.ai LLC.
# Side-effect-free policy. Importing this module never enumerates or writes disks.
Set-StrictMode -Version 2.0

function Get-ThoxValue {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { throw "Required object is absent ($Name)." }
    if ($Object -is [System.Collections.IDictionary]) {
        if (-not $Object.Contains($Name)) { throw "Required field is absent: $Name." }
        return $Object[$Name]
    }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { throw "Required field is absent: $Name." }
    return $property.Value
}

function Get-ThoxText {
    param([object]$Object, [string]$Name)
    $value = Get-ThoxValue $Object $Name
    if ($value -isnot [string] -or [string]::IsNullOrWhiteSpace($value)) {
        throw "Required nonempty string is absent: $Name."
    }
    if ($value -match '[\x00-\x1f\x7f]') { throw "Control character in $Name." }
    return $value.Trim()
}

function Get-ThoxInteger {
    param([object]$Object, [string]$Name, [long]$Minimum = 0)
    $value = Get-ThoxValue $Object $Name
    if ($value -is [bool] -or $value -is [string] -or $null -eq $value) {
        throw "$Name must be a JSON integer."
    }
    [decimal]$number = 0
    try { $number = [decimal]$value } catch { throw "$Name must be a JSON integer." }
    if ($number -ne [decimal]::Truncate($number) -or $number -lt $Minimum -or $number -gt [long]::MaxValue) {
        throw "$Name is outside its permitted integer range."
    }
    return [long]$number
}

function Assert-ThoxBoolean {
    param([object]$Object, [string]$Name, [bool]$Expected)
    $value = Get-ThoxValue $Object $Name
    if ($value -isnot [bool] -or $value -ne $Expected) {
        throw "$Name must be the boolean $Expected."
    }
}

function Assert-ThoxIdentityText {
    param([string]$Value, [string]$Label)
    if ([string]::IsNullOrWhiteSpace($Value) -or $Value.Trim().Length -lt 3) { throw "$Label is missing or too short." }
    if ($Value -match '[\x00-\x1f\x7f]' -or $Value.Trim() -match '^(?i:unknown|none|null|n/?a|default|to be filled.*|0+|f+|x+|-+)$') {
        throw "$Label is a placeholder and cannot identify a destructive target."
    }
}

function Assert-ThoxHash {
    param([string]$Value, [int]$Length = 64)
    if ($null -eq $Value -or $Value -cnotmatch ('^[0-9a-f]{' + $Length + '}$') -or $Value -match '^(0+|f+)$') {
        throw "Expected a concrete lowercase $Length-character hexadecimal digest."
    }
}

function Test-ThoxManifest {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Manifest)
    $exact = @{
        schema = 'thox.external-ssd.raw-gpt.v1'
        payloadClass = 'installed-system'
        architecture = 'x86_64'
        firmware = 'uefi'
        partitionTable = 'gpt'
        bootPath = 'EFI/BOOT/BOOTX64.EFI'
        growthPolicy = 'explicit-linux-first-boot'
    }
    foreach ($key in $exact.Keys) {
        if ((Get-ThoxText $Manifest $key) -cne $exact[$key]) { throw "Unsupported manifest $key." }
    }
    if ((Get-ThoxInteger $Manifest 'logicalSectorBytes' 1) -ne 512) { throw 'Only 512-byte logical-sector images are supported.' }
    Assert-ThoxBoolean $Manifest 'persistentRoot' $true
    $image = Get-ThoxValue $Manifest 'image'
    $file = Get-ThoxText $image 'file'
    if ($file -cnotmatch '^[A-Za-z0-9][A-Za-z0-9._-]*\.img$' -or $file.Contains('..')) {
        throw 'image.file must be a single .img basename beside the manifest; paths and compressed input are rejected.'
    }
    $bytes = Get-ThoxInteger $image 'bytes' 8388608
    if (($bytes % 512) -ne 0) { throw 'Image size must be an exact multiple of 512 bytes.' }
    $hash = Get-ThoxText $image 'sha256'
    Assert-ThoxHash $hash
    $minimum = Get-ThoxInteger $Manifest 'minimumTargetBytes' $bytes
    if (($minimum % 512) -ne 0) { throw 'minimumTargetBytes must be a multiple of 512 bytes.' }
    $source = Get-ThoxValue $Manifest 'source'
    $repository = Get-ThoxText $source 'repository'
    if ($repository -notmatch '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$') { throw 'source.repository must be an owner/repository reference.' }
    $commit = Get-ThoxText $source 'commit'
    Assert-ThoxHash $commit 40
    return [pscustomobject]@{
        Schema = $exact.schema; ImageFile = $file; ImageBytes = $bytes; ImageSha256 = $hash
        MinimumTargetBytes = $minimum; LogicalSectorBytes = 512
        SourceRepository = $repository; SourceCommit = $commit
    }
}

function Test-ThoxHost {
    param([Parameter(Mandatory = $true)][object]$HostSnapshot, [switch]$RequireAdministrator)
    if ((Get-ThoxText $HostSnapshot 'Platform') -cne 'Windows') { throw 'This operation requires Windows.' }
    if ((Get-ThoxText $HostSnapshot 'Architecture') -cne 'x64') { throw 'An x86-64 Windows PC is required; ARM64 and x86 are unsupported.' }
    Assert-ThoxBoolean $HostSnapshot 'Is64BitProcess' $true
    if ((Get-ThoxText $HostSnapshot 'Firmware') -cne 'UEFI') { throw 'A confirmed UEFI boot environment is required.' }
    if ($RequireAdministrator) { Assert-ThoxBoolean $HostSnapshot 'IsAdministrator' $true }
    Assert-ThoxIdentityText (Get-ThoxText $HostSnapshot 'HostId') 'HostId'
    $null = [DateTimeOffset]::Parse((Get-ThoxText $HostSnapshot 'BootUtc'))
}

function Test-ThoxTarget {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Disk,
        [Parameter(Mandatory = $true)][object[]]$AllDisks,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][int[]]$ProtectedDiskNumbers,
        [Parameter(Mandatory = $true)][long]$ImageBytes,
        [Parameter(Mandatory = $true)][long]$MinimumTargetBytes,
        [switch]$ReadOnlyVerification
    )
    if ($ImageBytes -le 0 -or $MinimumTargetBytes -lt $ImageBytes -or ($ImageBytes % 512) -ne 0 -or ($MinimumTargetBytes % 512) -ne 0) {
        throw 'Target validation requires positive, aligned image bytes and a minimum capacity at least that large.'
    }
    $serial = Get-ThoxText $Disk 'SerialNumber'
    $unique = Get-ThoxText $Disk 'UniqueId'
    Assert-ThoxIdentityText $serial 'Disk serial'
    Assert-ThoxIdentityText $unique 'Disk unique ID'
    if ($serial.IndexOf('VY2EJ04M', [StringComparison]::OrdinalIgnoreCase) -ge 0) {
        throw 'This serial is protected by the THOX never-write policy.'
    }
    if ((Get-ThoxText $Disk 'BusType') -cne 'USB') { throw 'Only USB-bus targets are permitted; internal, virtual, network and ambiguous buses are rejected.' }
    foreach ($field in @('IsBoot', 'IsSystem', 'IsReadOnly', 'IsClustered')) { Assert-ThoxBoolean $Disk $field $false }
    if (-not $ReadOnlyVerification) { Assert-ThoxBoolean $Disk 'IsOffline' $false }
    if ((Get-ThoxText $Disk 'HealthStatus') -cne 'Healthy') { throw 'Disk health is not confirmed Healthy.' }
    $number = Get-ThoxInteger $Disk 'Number' 0
    if ($ProtectedDiskNumbers -contains $number) { throw 'Target contains Windows, a page file, the kit, image, manifest, plan or receipt location.' }
    $bytes = Get-ThoxInteger $Disk 'Size' 1
    if ($bytes -lt $ImageBytes -or $bytes -lt $MinimumTargetBytes -or ($bytes % 512) -ne 0) {
        throw 'Target capacity is too small or is not 512-byte aligned.'
    }
    if ((Get-ThoxInteger $Disk 'LogicalSectorSize' 1) -ne 512) { throw '4Kn and unknown logical-sector targets are not supported.' }
    $physical = Get-ThoxInteger $Disk 'PhysicalSectorSize' 512
    if ($physical -gt 65536 -or (($physical -band ($physical - 1)) -ne 0)) { throw 'Unsupported physical-sector alignment.' }
    $path = Get-ThoxText $Disk 'Path'
    if (-not $path.StartsWith('\\?\', [StringComparison]::Ordinal) -or $path -match '(?i)physicaldrive\d+$') {
        throw 'A stable Windows device-interface path is required; a disk-number alias is insufficient.'
    }
    $null = Get-ThoxText $Disk 'PnpDeviceId'
    $matches = @($AllDisks | Where-Object {
        [string]::Equals([string](Get-ThoxValue $_ 'UniqueId'), $unique, [StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals(([string](Get-ThoxValue $_ 'SerialNumber')).Trim(), $serial, [StringComparison]::OrdinalIgnoreCase)
    })
    if ($matches.Count -ne 1 -or (Get-ThoxInteger $matches[0] 'Number' 0) -ne $number) {
        throw 'Serial or unique ID is duplicated or inventory is ambiguous.'
    }
    $null = Get-ThoxValue $Disk 'Volumes'
    if ($Disk -is [System.Collections.IDictionary]) { $volumes = $Disk['Volumes'] }
    else { $volumes = $Disk.PSObject.Properties['Volumes'].Value }
    if ($null -eq $volumes -or $volumes -isnot [array]) { throw 'Volume inventory must be a known array; null does not mean an empty disk.' }
    foreach ($volume in $volumes) {
        if ($null -eq $volume) { throw 'Unknown volume entry.' }
        Assert-ThoxBoolean $volume 'ExtentsKnown' $true
        $extentNumbers = @(Get-ThoxValue $volume 'DiskNumbers')
        if ($extentNumbers.Count -ne 1 -or [int]$extentNumbers[0] -ne $number) { throw 'Spanned or ambiguous target volume is rejected.' }
        if (-not $ReadOnlyVerification) { Assert-ThoxBoolean $volume 'LabelKnown' $true }
        $strings = @([string](Get-ThoxValue $volume 'Label')) + @(Get-ThoxValue $volume 'MountPaths')
        foreach ($text in $strings) {
            foreach ($protected in @('VibeStore', 'THOXSTORE', 'THOXKEY', 'WD Game Drive')) {
                if (([string]$text).IndexOf($protected, [StringComparison]::OrdinalIgnoreCase) -ge 0) {
                    throw "Volume label or mount path is protected by the THOX never-write policy: $protected."
                }
            }
        }
    }
    if (-not $ReadOnlyVerification) { Assert-ThoxBoolean $Disk 'VolumeInventoryComplete' $true }
    elseif ((Get-ThoxValue $Disk 'VolumeInventoryComplete') -isnot [bool]) { throw 'Volume inventory state is missing.' }
    if (-not $ReadOnlyVerification) {
        Assert-ThoxBoolean $Disk 'PartitionInventoryComplete' $true
        Assert-ThoxHash (Get-ThoxText $Disk 'PartitionFingerprint')
    }
    return $Disk
}

function Get-ThoxTailPlan {
    param([long]$ImageBytes, [long]$DiskBytes)
    if ($ImageBytes -le 0 -or $DiskBytes -lt $ImageBytes) { throw 'Invalid image/target lengths.' }
    $tailBytes = 1048576L
    if (($DiskBytes - $ImageBytes) -ge $tailBytes) {
        return [pscustomobject]@{ Offset = $DiskBytes - $tailBytes; Bytes = $tailBytes; Purpose = 'Remove stale backup GPT outside image; not secure erase' }
    }
    if ($DiskBytes -ne $ImageBytes) {
        throw 'Target has less than 1 MiB spare space; cannot safely separate stale-GPT clearing from the image. Use an exact-size or larger target.'
    }
    return [pscustomobject]@{ Offset = 0L; Bytes = 0L; Purpose = 'Exact-size target; image backup GPT retained' }
}

function Get-ThoxConfirmation {
    param([Parameter(Mandatory = $true)][object]$Plan)
    $disk = Get-ThoxValue $Plan 'Target'
    $serial = Get-ThoxText $disk 'SerialNumber'
    $bytes = Get-ThoxInteger $disk 'Size' 1
    $id = Get-ThoxText $Plan 'PlanId'
    if ($id -cnotmatch '^[0-9a-f]{12}$') { throw 'Invalid plan ID.' }
    return "ERASE USB SSD $serial $bytes BYTES PLAN $id"
}

function Assert-ThoxConfirmation {
    param([object]$Plan, [string]$TypedText)
    if (-not [string]::Equals((Get-ThoxConfirmation $Plan), $TypedText, [StringComparison]::Ordinal)) {
        throw 'Typed confirmation does not match exactly. No image write is authorized.'
    }
}

function Test-ThoxPlanFresh {
    param([object]$Plan, [object]$CurrentHost, [object]$CurrentDisk, [DateTimeOffset]$Now = [DateTimeOffset]::UtcNow, [switch]$ReadOnlyVerification)
    if ((Get-ThoxText $Plan 'Schema') -cne 'thox.external-ssd.plan.v1') { throw 'Unsupported plan schema.' }
    $created = [DateTimeOffset]::Parse((Get-ThoxText $Plan 'CreatedUtc'))
    $expires = [DateTimeOffset]::Parse((Get-ThoxText $Plan 'ExpiresUtc'))
    if ($created -gt $Now.AddMinutes(2) -or $expires -le $Now -or $expires -le $created -or ($expires - $created).TotalHours -gt 24) { throw 'Plan is expired or its timestamps are invalid. Create a new plan.' }
    $plannedHost = Get-ThoxValue $Plan 'Host'
    foreach ($field in @('HostId', 'BootUtc')) {
        if ((Get-ThoxText $plannedHost $field) -cne (Get-ThoxText $CurrentHost $field)) { throw "Plan host/session changed: $field." }
    }
    $planned = Get-ThoxValue $Plan 'Target'
    foreach ($field in @('SerialNumber', 'UniqueId', 'Path', 'PnpDeviceId', 'BusType')) {
        if (-not [string]::Equals((Get-ThoxText $planned $field), (Get-ThoxText $CurrentDisk $field), [StringComparison]::Ordinal)) {
            throw "Target identity changed after planning: $field."
        }
    }
    if (-not $ReadOnlyVerification) {
        $plannedPartitions = Get-ThoxText $planned 'PartitionFingerprint'
        $currentPartitions = Get-ThoxText $CurrentDisk 'PartitionFingerprint'
        Assert-ThoxHash $plannedPartitions; Assert-ThoxHash $currentPartitions
        if ($plannedPartitions -cne $currentPartitions) { throw 'Partition/mount geometry changed after planning.' }
    }
    foreach ($field in @('Number', 'Size', 'LogicalSectorSize', 'PhysicalSectorSize')) {
        if ((Get-ThoxInteger $planned $field 0) -ne (Get-ThoxInteger $CurrentDisk $field 0)) { throw "Target geometry/enumeration changed: $field. Re-plan; no disk-number retargeting occurs." }
    }
    $handle = Get-ThoxValue $CurrentDisk 'HandleIdentity'
    $plannedHandle = Get-ThoxValue $planned 'HandleIdentity'
    foreach ($field in @('DescriptorSha256', 'DeviceIdSha256')) {
        if ((Get-ThoxText $handle $field) -cne (Get-ThoxText $plannedHandle $field)) { throw "Opened-device identity changed: $field." }
    }
    $null = Get-ThoxConfirmation $Plan
}

Export-ModuleMember -Function Get-ThoxValue, Get-ThoxText, Get-ThoxInteger, Assert-ThoxBoolean, Assert-ThoxHash, Test-ThoxManifest, Test-ThoxHost, Test-ThoxTarget, Get-ThoxTailPlan, Get-ThoxConfirmation, Assert-ThoxConfirmation, Test-ThoxPlanFresh
