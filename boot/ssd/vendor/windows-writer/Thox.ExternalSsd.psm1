# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 THOX.ai LLC.
# Windows orchestration. Import has no disk side effects.
Set-StrictMode -Version 2.0
Import-Module (Join-Path $PSScriptRoot 'Thox.Ssd.Policy.psm1') -Force -DisableNameChecking

function Initialize-ThoxNative {
    if ($env:OS -cne 'Windows_NT') { throw 'Native inventory/write requires Windows. This module does not simulate Windows storage calls.' }
    if (-not [Environment]::Is64BitProcess) { throw 'Start 64-bit Windows PowerShell; 32-bit PowerShell is unsupported.' }
    if (-not ('Thox.ExternalSsd.DiskSession' -as [type])) {
        Add-Type -Path @((Join-Path $PSScriptRoot 'Thox.Image.cs'), (Join-Path $PSScriptRoot 'Thox.WindowsStorage.cs')) -ErrorAction Stop
    }
}

function New-ThoxProgress {
    return [System.Action[Thox.ExternalSsd.TransferProgress]]{
        param($Progress)
        $percent = 0
        if ($Progress.Total -gt 0) { $percent = [int][Math]::Min(100, (($Progress.Completed * 100.0) / $Progress.Total)) }
        Write-Progress -Id 71 -Activity ("THOX external SSD: " + $Progress.Phase) -Status ("{0:N0} / {1:N0} bytes; complete only after readback verification" -f $Progress.Completed, $Progress.Total) -PercentComplete $percent
    }
}

function Get-ThoxHostSnapshot {
    Initialize-ThoxNative
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    $administrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    $machine = (Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Cryptography' -Name MachineGuid -ErrorAction Stop).MachineGuid
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $hostId = [Thox.ExternalSsd.ImageChecks]::Sha256Bytes([Text.Encoding]::UTF8.GetBytes([string]$machine))
    $secureBoot = 'Unknown'
    try {
        if (Confirm-SecureBootUEFI -ErrorAction Stop) { $secureBoot = 'Enabled' } else { $secureBoot = 'Disabled' }
    } catch { $secureBoot = 'Unknown: ' + $_.Exception.Message }
    $bitLocker = 'Unknown'
    try {
        if ($env:SystemDrive -notmatch '^[A-Za-z]:$') { throw 'SystemDrive is not a local drive letter.' }
        $systemVolume = @(Get-CimInstance -Namespace 'Root/CIMV2/Security/MicrosoftVolumeEncryption' -ClassName Win32_EncryptableVolume -Filter ("DriveLetter='" + $env:SystemDrive + "'") -Property DeviceID, DriveLetter -ErrorAction Stop)
        if ($systemVolume.Count -ne 1) { throw 'System-volume encryption provider returned no unique volume.' }
        # Query only protection status. No key-protector/recovery-material enumeration is performed.
        $protection = Invoke-CimMethod -InputObject $systemVolume[0] -MethodName GetProtectionStatus -ErrorAction Stop
        if ($protection.ReturnValue -ne 0) { throw ('Protection-status provider returned ' + $protection.ReturnValue) }
        switch ([int]$protection.ProtectionStatus) {
            0 { $bitLocker = 'Protection off; this alone does not establish whether the volume is encrypted' }
            1 { $bitLocker = 'Protection on' }
            default { $bitLocker = 'Protection status unknown' }
        }
    } catch { $bitLocker = 'Unavailable or unknown: ' + $_.Exception.Message }
    return [pscustomobject]@{
        Platform = 'Windows'; Architecture = [Thox.ExternalSsd.WindowsStorage]::Architecture()
        Is64BitProcess = [Environment]::Is64BitProcess
        Firmware = [Thox.ExternalSsd.WindowsStorage]::Firmware()
        IsAdministrator = [bool]$administrator; HostId = $hostId
        BootUtc = ([datetime]$os.LastBootUpTime).ToUniversalTime().ToString('o')
        WindowsVersion = [string]$os.Version; PowerShellVersion = $PSVersionTable.PSVersion.ToString()
        SecureBoot = $secureBoot
        SystemVolumeEncryption = $bitLocker
        SecureBootAction = 'Read only. This kit does not change firmware policy, BitLocker or boot order; image signing/firmware boot acceptance is separate.'
    }
}

function Get-ThoxObservedProperty {
    param([object]$Object, [string]$Name)
    if ($null -eq $Object) { return $null }
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) { return $null }
    return $property.Value
}

function Get-ThoxPartitionObservation {
    param([object]$Disk, [object[]]$Partitions, [object[]]$Volumes)
    $records = @()
    try {
        $count = Get-ThoxInteger $Disk 'NumberOfPartitions' 0
        $diskBytes = Get-ThoxInteger $Disk 'Size' 1
        $diskNumber = Get-ThoxInteger $Disk 'Number' 0
        if ($count -gt 128 -or $Partitions.Count -ne $count) { throw 'Partition count is missing, changed or unsupported.' }
        if ($count -eq 0 -and $Volumes.Count -gt 0) { throw 'Volume and empty-partition observations disagree.' }
        $previousEnd = 512L
        $usedNumbers = New-Object 'System.Collections.Generic.HashSet[int]'
        $usedVolumes = New-Object 'System.Collections.Generic.HashSet[string]'
        foreach ($partition in @($Partitions | Sort-Object Offset)) {
            if ((Get-ThoxInteger $partition 'DiskNumber' 0) -ne $diskNumber) { throw 'Partition belongs to a different disk.' }
            $offset = Get-ThoxInteger $partition 'Offset' 512
            $size = Get-ThoxInteger $partition 'Size' 512
            $number = Get-ThoxInteger $partition 'PartitionNumber' 1
            if (-not $usedNumbers.Add([int]$number) -or $offset -lt $previousEnd -or $offset -gt $diskBytes - $size -or ($offset % 512) -ne 0 -or ($size % 512) -ne 0) { throw 'Partition extents/identities overlap or leave the target.' }
            $previousEnd = $offset + $size
            $access = @(Get-ThoxObservedProperty $partition 'AccessPaths' | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | ForEach-Object { ([string]$_).TrimEnd([char]92) } | Sort-Object)
            $mapped = @($Volumes | Where-Object { $access -contains $_.Name.TrimEnd([char]92) })
            $gptType = ([string](Get-ThoxObservedProperty $partition 'GptType')).Trim([char]123, [char]125)
            $kind = 'filesystem'
            $reserved = $gptType -ieq 'e3c9e316-0b5c-4db8-817d-f92df00215ae' -and $size -le 134217728 -and $access.Count -eq 0
            if ($reserved) { $kind = 'Windows MSR without filesystem' }
            else {
                if ($mapped.Count -ne 1) { throw ('Partition ' + $number + ' has no uniquely mapped Windows volume. Foreign/uninspectable filesystems require separate recovery review.') }
                Assert-ThoxBoolean $mapped[0] 'ExtentsKnown' $true
                Assert-ThoxBoolean $mapped[0] 'LabelKnown' $true
                if ($mapped[0].DiskNumbers.Count -ne 1 -or $mapped[0].DiskNumbers[0] -ne $diskNumber -or -not $usedVolumes.Add($mapped[0].Name.ToUpperInvariant())) { throw 'Partition maps to a duplicate or spanned volume.' }
            }
            $records += [pscustomobject]@{ Number = $number; Offset = $offset; Size = $size; GptType = $gptType; Kind = $kind; AccessPaths = [string[]]$access }
        }
        foreach ($volume in $Volumes) {
            if (-not $usedVolumes.Contains((Get-ThoxText $volume 'Name').ToUpperInvariant())) { throw 'A target volume is not accounted for by a mapped partition.' }
        }
        $text = ConvertTo-Json -InputObject ([object[]]$records) -Depth 5 -Compress
        $fingerprint = [Thox.ExternalSsd.ImageChecks]::Sha256Bytes([Text.Encoding]::UTF8.GetBytes($text))
        return [pscustomobject]@{ Complete = $true; Error = $null; Records = [object[]]$records; Fingerprint = $fingerprint }
    } catch { return [pscustomobject]@{ Complete = $false; Error = $_.Exception.Message; Records = [object[]]$records; Fingerprint = $null } }
}

function Get-ThoxDiskInventory {
    [CmdletBinding()]
    param([switch]$IncludeEligibility)
    Initialize-ThoxNative
    $nativeVolumes = @([Thox.ExternalSsd.WindowsStorage]::Volumes())
    $complete = @($nativeVolumes | Where-Object { -not $_.ExtentsKnown -or -not [string]::IsNullOrEmpty($_.Error) }).Count -eq 0
    $hardware = @(Get-CimInstance -ClassName Win32_DiskDrive -ErrorAction Stop)
    $disks = @(Get-Disk -ErrorAction Stop)
    $result = @()
    foreach ($disk in $disks) {
        $match = @($hardware | Where-Object { $_.Index -eq $disk.Number })
        $pnp = $null
        if ($match.Count -eq 1) { $pnp = [string]$match[0].PNPDeviceID }
        $volumes = @($nativeVolumes | Where-Object { $_.DiskNumbers -contains [int]$disk.Number })
        $partitions = @(); $partitionFailure = $null
        try {
            $count = Get-ThoxObservedProperty $disk 'NumberOfPartitions'
            if ($null -eq $count -or $count -is [bool] -or [long]$count -lt 0 -or [long]$count -gt 128) { throw 'Partition count is missing or unsupported.' }
            if ([long]$count -gt 0) { $partitions = @(Get-Partition -DiskNumber $disk.Number -ErrorAction Stop) }
        } catch { $partitionFailure = $_.Exception.Message }
        $partitionState = Get-ThoxPartitionObservation -Disk $disk -Partitions $partitions -Volumes $volumes
        if ($null -ne $partitionFailure) { $partitionState.Complete = $false; $partitionState.Error = $partitionFailure }
        $entry = [pscustomobject]@{
            Number = [int]$disk.Number; FriendlyName = [string]$disk.FriendlyName
            SerialNumber = ([string]$disk.SerialNumber).Trim(); UniqueId = ([string]$disk.UniqueId).Trim()
            Path = [string]$disk.Path; PnpDeviceId = $pnp; Size = [long]$disk.Size; BusType = [string]$disk.BusType
            LogicalSectorSize = Get-ThoxObservedProperty $disk 'LogicalSectorSize'
            PhysicalSectorSize = Get-ThoxObservedProperty $disk 'PhysicalSectorSize'
            IsBoot = Get-ThoxObservedProperty $disk 'IsBoot'; IsSystem = Get-ThoxObservedProperty $disk 'IsSystem'
            IsReadOnly = Get-ThoxObservedProperty $disk 'IsReadOnly'; IsOffline = Get-ThoxObservedProperty $disk 'IsOffline'
            IsClustered = Get-ThoxObservedProperty $disk 'IsClustered'; HealthStatus = [string]$disk.HealthStatus
            PartitionStyle = [string]$disk.PartitionStyle; Volumes = [object[]]$volumes
            VolumeInventoryComplete = [bool]$complete; HandleIdentity = $null; HandleProbeError = $null
            Partitions = [object[]]$partitionState.Records; PartitionInventoryComplete = [bool]$partitionState.Complete
            PartitionInventoryError = $partitionState.Error; PartitionFingerprint = $partitionState.Fingerprint
            MediaTypeNote = 'USB bridges may not report SSD/HDD type. Confirm the physical SSD label; bus type alone is not a media-type attestation.'
        }
        if ($entry.BusType -ceq 'USB') {
            try { $entry.HandleIdentity = [Thox.ExternalSsd.DiskSession]::Probe($entry.Path) }
            catch { $entry.HandleProbeError = $_.Exception.Message }
        }
        $result += $entry
    }
    if ($IncludeEligibility) {
        $guardError = $null; $guarded = @()
        try { $guarded = @(Get-ThoxProtectedDisks -Disks $result -Paths @() -Image $null) }
        catch { $guardError = $_.Exception.Message }
        foreach ($entry in $result) {
            $eligible = $false; $reason = ''
            try {
                if ($null -ne $guardError) { throw $guardError }
                if (-not $entry.PartitionInventoryComplete) { throw $entry.PartitionInventoryError }
                $null = Test-ThoxTarget -Disk $entry -AllDisks $result -ProtectedDiskNumbers $guarded -ImageBytes 512 -MinimumTargetBytes 512
                if ($null -eq $entry.HandleIdentity) { throw ('Retained-handle identity unavailable: ' + $entry.HandleProbeError) }
                $eligible = $true; $reason = 'Device policy passed; exact image fit and publisher hashes are still required during planning.'
            } catch { $reason = $_.Exception.Message }
            $entry | Add-Member -NotePropertyName EligibleForPlanning -NotePropertyValue $eligible
            $entry | Add-Member -NotePropertyName EligibilityReason -NotePropertyValue $reason
        }
    }
    return $result
}

function Get-ThoxExistingLocation {
    param([string]$Path)
    if ([string]::IsNullOrWhiteSpace($Path)) { throw 'A required protected location is absent.' }
    $current = [IO.Path]::GetFullPath($Path)
    while (-not [IO.File]::Exists($current) -and -not [IO.Directory]::Exists($current)) {
        $parent = [IO.Path]::GetDirectoryName($current)
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -ceq $current) { throw "Cannot resolve protected path: $Path." }
        $current = $parent
    }
    return $current
}

function Get-ThoxProtectedDisks {
    param([object[]]$Disks, [string[]]$Paths, [object]$Image)
    $numbers = New-Object 'System.Collections.Generic.HashSet[int]'
    foreach ($disk in $Disks) {
        if ($disk.IsBoot -eq $true -or $disk.IsSystem -eq $true) { $null = $numbers.Add([int]$disk.Number) }
    }
    $required = @($env:windir, $PSScriptRoot, [Diagnostics.Process]::GetCurrentProcess().MainModule.FileName) + $Paths
    foreach ($path in $required) {
        $existing = Get-ThoxExistingLocation $path
        foreach ($number in [Thox.ExternalSsd.WindowsStorage]::PathDiskNumbers($existing)) { $null = $numbers.Add($number) }
    }
    foreach ($pageFile in @(Get-CimInstance -ClassName Win32_PageFileUsage -ErrorAction Stop)) {
        $directory = [IO.Path]::GetDirectoryName([string]$pageFile.Name)
        foreach ($number in [Thox.ExternalSsd.WindowsStorage]::PathDiskNumbers((Get-ThoxExistingLocation $directory))) { $null = $numbers.Add($number) }
    }
    if ($null -ne $Image) {
        foreach ($number in [Thox.ExternalSsd.WindowsStorage]::HandleDiskNumbers($Image.Handle)) { $null = $numbers.Add($number) }
    }
    return @($numbers | Sort-Object)
}

function Select-ThoxDisk {
    param([object[]]$Disks, [string]$UniqueId, [string]$SerialNumber, [long]$ExpectedBytes)
    if ([string]::IsNullOrWhiteSpace($UniqueId) -or [string]::IsNullOrWhiteSpace($SerialNumber) -or $ExpectedBytes -le 0) {
        throw 'Concrete DiskUniqueId, DiskSerial and ExpectedDiskBytes are required; disk numbers alone cannot select a target.'
    }
    $matches = @($Disks | Where-Object {
        [string]::Equals($_.UniqueId, $UniqueId.Trim(), [StringComparison]::OrdinalIgnoreCase) -and
        [string]::Equals($_.SerialNumber, $SerialNumber.Trim(), [StringComparison]::OrdinalIgnoreCase)
    })
    if ($matches.Count -ne 1) { throw 'The serial and unique ID do not identify exactly one current disk.' }
    if ($matches[0].Size -ne $ExpectedBytes) { throw 'Target capacity differs from the exact expected byte count.' }
    if ($null -eq $matches[0].HandleIdentity) { throw ('Retained-handle identity could not be probed: ' + $matches[0].HandleProbeError) }
    $proof = $matches[0].HandleIdentity
    if ($proof.Number -ne $matches[0].Number -or $proof.Size -ne $matches[0].Size -or $proof.LogicalSectorSize -ne $matches[0].LogicalSectorSize -or $proof.PhysicalSectorSize -ne $matches[0].PhysicalSectorSize) {
        throw 'Storage-provider enumeration differs from the opened device handle. Re-plan after resolving the device change.'
    }
    return $matches[0]
}

function Read-ThoxJson {
    param([string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).ProviderPath
    if (-not [IO.File]::Exists($resolved)) { throw 'Expected a local JSON file.' }
    $stream = New-Object IO.FileStream($resolved, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($stream.Length -gt 1048576 -or $stream.Length -eq 0) { throw 'JSON file is empty or exceeds the 1 MiB limit.' }
        $bytes = New-Object byte[] ([int]$stream.Length)
        $offset = 0
        while ($offset -lt $bytes.Length) {
            $read = $stream.Read($bytes, $offset, $bytes.Length - $offset)
            if ($read -eq 0) { throw 'JSON file was truncated.' }
            $offset += $read
        }
        $utf8 = New-Object Text.UTF8Encoding($false, $true)
        $text = $utf8.GetString($bytes).TrimStart([char]0xfeff)
        if ((Get-Command ConvertFrom-Json).Parameters.ContainsKey('DateKind')) {
            $object = ConvertFrom-Json -InputObject $text -DateKind String -ErrorAction Stop
        } else {
            $object = ConvertFrom-Json -InputObject $text -ErrorAction Stop
            # Older engines may turn ISO dates into DateTime objects. Restore known receipt/plan fields.
            foreach ($field in @('CreatedUtc', 'ExpiresUtc', 'StartedUtc', 'FinishedUtc')) {
                $property = $object.PSObject.Properties[$field]
                if ($null -ne $property -and $property.Value -is [datetime]) { $property.Value = $property.Value.ToUniversalTime().ToString('o') }
            }
            $hostProperty = $object.PSObject.Properties['Host']
            if ($null -ne $hostProperty -and $null -ne $hostProperty.Value) {
                $bootProperty = $hostProperty.Value.PSObject.Properties['BootUtc']
                if ($null -ne $bootProperty -and $bootProperty.Value -is [datetime]) { $bootProperty.Value = $bootProperty.Value.ToUniversalTime().ToString('o') }
            }
        }
        return [pscustomobject]@{ Path = $resolved; Object = $object; Sha256 = [Thox.ExternalSsd.ImageChecks]::Sha256Bytes($bytes) }
    } finally { $stream.Dispose() }
}

function Read-ThoxManifest {
    param([string]$Path, [string]$ExpectedSha256)
    Assert-ThoxHash $ExpectedSha256
    $record = Read-ThoxJson $Path
    if ($record.Sha256 -cne $ExpectedSha256) { throw 'Manifest SHA-256 differs from the publisher/build receipt. Do not use a hash merely copied from an untrusted adjacent file.' }
    $values = Test-ThoxManifest $record.Object
    return [pscustomobject]@{
        Path = $record.Path; Sha256 = $record.Sha256; Values = $values
        ImagePath = Join-Path ([IO.Path]::GetDirectoryName($record.Path)) $values.ImageFile
    }
}

function Save-ThoxJson {
    param([object]$Value, [string]$Path, [switch]$NewOnly)
    $full = [IO.Path]::GetFullPath($Path); $parent = [IO.Path]::GetDirectoryName($full)
    $null = [IO.Directory]::CreateDirectory($parent)
    $text = (ConvertTo-Json -InputObject $Value -Depth 14) + [Environment]::NewLine
    $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($text)
    if ($NewOnly) {
        $output = New-Object IO.FileStream($full, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
        try { $output.Write($bytes, 0, $bytes.Length); $output.Flush($true) } finally { $output.Dispose() }
        return
    }
    $temporary = Join-Path $parent ('.thox-receipt-' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        $output = New-Object IO.FileStream($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None, 4096, [IO.FileOptions]::WriteThrough)
        try { $output.Write($bytes, 0, $bytes.Length); $output.Flush($true) } finally { $output.Dispose() }
        if ([IO.File]::Exists($full)) { [Thox.ExternalSsd.SafeFileOperations]::ReplaceExisting($temporary, $full) } else { [IO.File]::Move($temporary, $full) }
    } finally {
        if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
    }
}

function Get-ThoxPreflight {
    [CmdletBinding()]
    param([string]$ManifestPath, [string]$ExpectedManifestSha256)
    $hostSnapshot = Get-ThoxHostSnapshot
    Test-ThoxHost $hostSnapshot -RequireAdministrator
    $manifest = Read-ThoxManifest $ManifestPath $ExpectedManifestSha256
    $image = $null
    try {
        $image = [Thox.ExternalSsd.ImageFile]::Open($manifest.ImagePath, $manifest.Values.ImageBytes, $manifest.Values.ImageSha256, (New-ThoxProgress))
        return [pscustomobject]@{ State = 'source-verified-no-disk-write'; Host = $hostSnapshot; ManifestPath = $manifest.Path; ManifestSha256 = $manifest.Sha256; Image = $manifest.Values; Layout = $image.Layout; BootAcceptance = 'Not established by hashing or filesystem inspection.' }
    } finally {
        if ($null -ne $image) { $image.Dispose() }
        Write-Progress -Id 71 -Activity 'THOX external SSD' -Completed
    }
}

function New-ThoxDiskPlan {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'None')]
    param(
        [string]$ManifestPath, [string]$ExpectedManifestSha256,
        [string]$DiskUniqueId, [string]$DiskSerial, [long]$ExpectedDiskBytes,
        [string]$PlanPath, [string]$ReceiptDirectory
    )
    $hostSnapshot = Get-ThoxHostSnapshot
    Test-ThoxHost $hostSnapshot -RequireAdministrator
    $manifest = Read-ThoxManifest $ManifestPath $ExpectedManifestSha256
    if ([string]::IsNullOrWhiteSpace($PlanPath)) { throw 'PlanPath is required; choose a new file outside the target SSD.' }
    $planFull = [IO.Path]::GetFullPath($PlanPath)
    if ([IO.File]::Exists($planFull)) { throw 'Plan file already exists. Use a new filename; old review evidence is preserved.' }
    if ([string]::IsNullOrWhiteSpace($ReceiptDirectory)) { $ReceiptDirectory = Join-Path $env:LOCALAPPDATA 'THOX\ExternalSSD\receipts' }
    $id = [guid]::NewGuid().ToString('N').Substring(0, 12)
    $receiptPath = [IO.Path]::GetFullPath((Join-Path $ReceiptDirectory ($id + '.json')))
    $image = $null
    try {
        $image = [Thox.ExternalSsd.ImageFile]::Open($manifest.ImagePath, $manifest.Values.ImageBytes, $manifest.Values.ImageSha256, (New-ThoxProgress))
        $disks = @(Get-ThoxDiskInventory)
        $disk = Select-ThoxDisk $disks $DiskUniqueId $DiskSerial $ExpectedDiskBytes
        $protected = @(Get-ThoxProtectedDisks -Disks $disks -Paths @($manifest.Path, $manifest.ImagePath, $planFull, $receiptPath) -Image $image)
        $null = Test-ThoxTarget -Disk $disk -AllDisks $disks -ProtectedDiskNumbers $protected -ImageBytes $manifest.Values.ImageBytes -MinimumTargetBytes $manifest.Values.MinimumTargetBytes
        $tail = Get-ThoxTailPlan $manifest.Values.ImageBytes $disk.Size
        $now = [DateTimeOffset]::UtcNow
        $plan = [pscustomobject]@{
            Schema = 'thox.external-ssd.plan.v1'; PlanId = $id; CreatedUtc = $now.ToString('o'); ExpiresUtc = $now.AddHours(24).ToString('o')
            Host = $hostSnapshot; Target = $disk; ManifestPath = $manifest.Path; ManifestSha256 = $manifest.Sha256
            ImagePath = $manifest.ImagePath; Image = $manifest.Values; Layout = $image.Layout; Tail = $tail
            ProtectedDiskNumbers = [int[]]$protected; ReceiptPath = $receiptPath
            Actions = @('Lock and dismount every target volume, including volumes without letters', 'Leave this external target offline in Windows', 'Overwrite the exact image range from byte zero', 'Read back and SHA-256 verify the complete image range', 'Clear and independently verify the declared final 1 MiB only when wholly outside the image')
            DataLoss = 'Existing data on the selected external SSD will be destroyed. This is not secure erase, a backup, or a reversible operation.'
            Preserved = 'Internal Windows disks, NVRAM, boot order, Secure Boot and BitLocker configuration are not modified.'
            Confirmation = ''
        }
        $plan.Confirmation = Get-ThoxConfirmation $plan
        if ($PSCmdlet.ShouldProcess($planFull, 'Save the read-only target plan')) { Save-ThoxJson -Value $plan -Path $planFull -NewOnly }
        return $plan
    } finally {
        if ($null -ne $image) { $image.Dispose() }
        Write-Progress -Id 71 -Activity 'THOX external SSD' -Completed
    }
}

function Open-ThoxPlanContext {
    param([string]$PlanPath, [switch]$ReadOnlyVerification)
    $hostSnapshot = Get-ThoxHostSnapshot
    Test-ThoxHost $hostSnapshot -RequireAdministrator
    $planRecord = Read-ThoxJson $PlanPath
    $plan = $planRecord.Object
    $manifest = Read-ThoxManifest (Get-ThoxText $plan 'ManifestPath') (Get-ThoxText $plan 'ManifestSha256')
    if (-not [string]::Equals($manifest.ImagePath, (Get-ThoxText $plan 'ImagePath'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Plan image path differs from its pinned manifest.' }
    foreach ($field in @('ImageBytes', 'ImageSha256', 'MinimumTargetBytes', 'LogicalSectorBytes', 'SourceCommit')) {
        if ((Get-ThoxValue $plan.Image $field) -cne (Get-ThoxValue $manifest.Values $field)) { throw "Plan payload changed: $field." }
    }
    $image = $null
    try {
        $image = [Thox.ExternalSsd.ImageFile]::Open($manifest.ImagePath, $manifest.Values.ImageBytes, $manifest.Values.ImageSha256, (New-ThoxProgress))
        $disks = @(Get-ThoxDiskInventory)
        $disk = Select-ThoxDisk $disks (Get-ThoxText $plan.Target 'UniqueId') (Get-ThoxText $plan.Target 'SerialNumber') (Get-ThoxInteger $plan.Target 'Size' 1)
        $protected = @(Get-ThoxProtectedDisks -Disks $disks -Paths @($manifest.Path, $manifest.ImagePath, $planRecord.Path, (Get-ThoxText $plan 'ReceiptPath')) -Image $image)
        $null = Test-ThoxTarget -Disk $disk -AllDisks $disks -ProtectedDiskNumbers $protected -ImageBytes $manifest.Values.ImageBytes -MinimumTargetBytes $manifest.Values.MinimumTargetBytes -ReadOnlyVerification:$ReadOnlyVerification
        Test-ThoxPlanFresh -Plan $plan -CurrentHost $hostSnapshot -CurrentDisk $disk -ReadOnlyVerification:$ReadOnlyVerification
        $tail = Get-ThoxTailPlan $manifest.Values.ImageBytes $disk.Size
        if ($tail.Offset -ne (Get-ThoxInteger $plan.Tail 'Offset' 0) -or $tail.Bytes -ne (Get-ThoxInteger $plan.Tail 'Bytes' 0)) { throw 'Tail plan differs from independently recomputed safe bounds.' }
        if ((Get-ThoxText $plan 'Confirmation') -cne (Get-ThoxConfirmation $plan)) { throw 'Stored confirmation differs from the target-specific phrase.' }
        return [pscustomobject]@{ Plan = $plan; PlanPath = $planRecord.Path; Manifest = $manifest; Image = $image; Host = $hostSnapshot; Disk = $disk; Disks = $disks; Protected = [int[]]$protected }
    } catch { if ($null -ne $image) { $image.Dispose() }; throw }
}

function Assert-ThoxSessionIdentity {
    param([object]$Session, [object]$Target)
    $proof = $Target.HandleIdentity
    $Session.AssertIdentity([int]$Target.Number, [long]$Target.Size, [int]$Target.LogicalSectorSize, [int]$Target.PhysicalSectorSize, [string]$proof.DescriptorSha256, [string]$proof.DeviceIdSha256)
}

function Invoke-ThoxDiskWrite {
    [CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'None')]
    param([Parameter(Mandatory = $true)][string]$PlanPath, [switch]$Apply)
    $context = $null; $session = $null; $mutex = $null; $owned = $false; $receipt = $null; $receiptOwned = $false
    try {
        $context = Open-ThoxPlanContext $PlanPath
        $plan = $context.Plan
        if (-not $Apply -or -not $PSCmdlet.ShouldProcess(("USB serial {0}, unique ID {1}, {2} bytes" -f $plan.Target.SerialNumber, $plan.Target.UniqueId, $plan.Target.Size), 'Destroy existing SSD contents and write/verify the pinned installed-system image')) {
            return [pscustomobject]@{ State = 'dry-run-no-disk-write'; Plan = $plan; Next = 'Review the target and image, then rerun write with -Apply. Interactive typed confirmation remains mandatory.' }
        }
        if ([Console]::IsInputRedirected -or $Host.Name -cne 'ConsoleHost') { throw 'Destructive provisioning requires an interactive local ConsoleHost; redirected/noninteractive confirmation is refused.' }
        $mutex = New-Object Threading.Mutex($false, 'Global\THOX.ExternalSSD.Provisioning')
        try { $owned = $mutex.WaitOne(0) }
        catch [Threading.AbandonedMutexException] { $owned = $true; throw 'An earlier provisioning process ended without releasing its lock. Inspect its receipt and create a new plan before retrying.' }
        if (-not $owned) { throw 'Another THOX external-SSD write is active. No concurrent write is permitted.' }
        Write-Host ''
        Write-Host 'DESTRUCTIVE EXTERNAL SSD PLAN'
        Write-Host ("Model: {0}" -f $plan.Target.FriendlyName)
        Write-Host ("Current disk number: {0} (not used as the write address)" -f $plan.Target.Number)
        Write-Host ("Serial: {0}" -f $plan.Target.SerialNumber)
        Write-Host ("Unique ID: {0}" -f $plan.Target.UniqueId)
        Write-Host ("Exact target bytes: {0}" -f $plan.Target.Size)
        Write-Host ("Image: {0}" -f $plan.ImagePath)
        Write-Host ("Image SHA-256: {0}" -f $plan.Image.ImageSha256)
        Write-Host ("Image bytes: {0}" -f $plan.Image.ImageBytes)
        Write-Host ("Final tail clear: offset {0}, length {1} bytes" -f $plan.Tail.Offset, $plan.Tail.Bytes)
        Write-Host $plan.DataLoss
        Write-Host 'Windows remains internal. Verification cannot restore existing SSD data. No firmware/BitLocker policy is changed.'
        Write-Host ("Type exactly: {0}" -f (Get-ThoxConfirmation $plan))
        $typed = Read-Host 'Confirmation'
        Assert-ThoxConfirmation $plan $typed
        # Refresh after human confirmation. Disk numbers from old enumeration never become write addresses.
        $freshHost = Get-ThoxHostSnapshot
        $freshDisks = @(Get-ThoxDiskInventory)
        $freshDisk = Select-ThoxDisk $freshDisks $plan.Target.UniqueId $plan.Target.SerialNumber $plan.Target.Size
        $freshProtected = @(Get-ThoxProtectedDisks -Disks $freshDisks -Paths @($context.Manifest.Path, $context.Manifest.ImagePath, $context.PlanPath, $plan.ReceiptPath) -Image $context.Image)
        $null = Test-ThoxTarget -Disk $freshDisk -AllDisks $freshDisks -ProtectedDiskNumbers $freshProtected -ImageBytes $plan.Image.ImageBytes -MinimumTargetBytes $plan.Image.MinimumTargetBytes
        Test-ThoxPlanFresh $plan $freshHost $freshDisk
        $null = [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($plan.ReceiptPath))
        foreach ($number in [Thox.ExternalSsd.WindowsStorage]::PathDiskNumbers([IO.Path]::GetDirectoryName($plan.ReceiptPath))) {
            if ($number -eq $freshDisk.Number) { throw 'Receipt directory resolves onto the target. No disk change is permitted.' }
        }
        $receipt = [pscustomobject]@{
            Schema = 'thox.external-ssd.receipt.v1'; PlanId = $plan.PlanId
            StartedUtc = [DateTimeOffset]::UtcNow.ToString('o'); FinishedUtc = $null
            Phase = 'authorized-no-image-write-yet'; Target = $plan.Target
            ManifestSha256 = $plan.ManifestSha256; ImageSha256 = $plan.Image.ImageSha256; ImageBytes = $plan.Image.ImageBytes; Tail = $plan.Tail
            ImageWriteStarted = $false; ImageBytesWritten = $null; TailWriteStarted = $false; OfflineSet = $false
            Verification = $null; Error = $null
            Recovery = 'Any receipt without phase verified is incomplete or unknown. Do not boot or format the SSD. No old-data rollback exists. Keep it offline, preserve this receipt, inspect identity and image, then make a fresh plan if rewriting is intended.'
        }
        Save-ThoxJson $receipt $plan.ReceiptPath -NewOnly
        $receiptOwned = $true
        $session = [Thox.ExternalSsd.DiskSession]::Open($freshDisk.Path, $true)
        Assert-ThoxSessionIdentity $session $plan.Target
        $openedDisks = @(Get-ThoxDiskInventory)
        $opened = Select-ThoxDisk $openedDisks $plan.Target.UniqueId $plan.Target.SerialNumber $plan.Target.Size
        $openedProtected = @(Get-ThoxProtectedDisks -Disks $openedDisks -Paths @($context.Manifest.Path, $context.PlanPath, $plan.ReceiptPath) -Image $context.Image)
        $null = Test-ThoxTarget -Disk $opened -AllDisks $openedDisks -ProtectedDiskNumbers $openedProtected -ImageBytes $plan.Image.ImageBytes -MinimumTargetBytes $plan.Image.MinimumTargetBytes
        Test-ThoxPlanFresh $plan (Get-ThoxHostSnapshot) $opened
        Assert-ThoxSessionIdentity $session $opened
        $expectedVolumes = [string[]]@($plan.Target.Volumes | ForEach-Object { $_.Name })
        $session.BeginExclusive($expectedVolumes, [int[]]$openedProtected)
        $receipt.Phase = 'write-or-verification-in-progress'; $receipt.OfflineSet = $session.OfflineSet
        Save-ThoxJson $receipt $plan.ReceiptPath
        $verification = $session.WriteVerified($context.Image, [long]$plan.Tail.Offset, [long]$plan.Tail.Bytes, (New-ThoxProgress))
        $receipt.ImageWriteStarted = $session.ImageWriteStarted; $receipt.ImageBytesWritten = $session.ImageBytesWritten
        $receipt.TailWriteStarted = $session.TailWriteStarted; $receipt.OfflineSet = $session.OfflineSet
        $receipt.Verification = $verification; $receipt.Phase = 'verified'; $receipt.FinishedUtc = [DateTimeOffset]::UtcNow.ToString('o')
        Save-ThoxJson $receipt $plan.ReceiptPath
        return [pscustomobject]@{ State = 'written-and-readback-verified'; ReceiptPath = $plan.ReceiptPath; Verification = $verification; Next = 'Leave the Linux SSD offline in Windows. Safely remove it, then use the PC one-time UEFI boot menu. Firmware boot and installed-system acceptance are still separate.' }
    } catch {
        $errorMessage = $_.Exception.Message
        if ($receiptOwned -and $null -ne $receipt) {
            $receipt.Phase = 'failed-or-interrupted'; $receipt.Error = $errorMessage; $receipt.FinishedUtc = [DateTimeOffset]::UtcNow.ToString('o')
            if ($null -ne $session) {
                $receipt.ImageWriteStarted = $session.ImageWriteStarted; $receipt.ImageBytesWritten = $session.ImageBytesWritten
                $receipt.TailWriteStarted = $session.TailWriteStarted; $receipt.OfflineSet = $session.OfflineSet
            }
            try { Save-ThoxJson $receipt $context.Plan.ReceiptPath }
            catch { Write-Warning 'Receipt update also failed. The disk state is unknown; preserve any earlier receipt and do not infer success.' }
        }
        throw
    } finally {
        if ($null -ne $session) { $session.Dispose() }
        if ($null -ne $context) { $context.Image.Dispose() }
        if ($owned -and $null -ne $mutex) { $mutex.ReleaseMutex() }
        if ($null -ne $mutex) { $mutex.Dispose() }
        Write-Progress -Id 71 -Activity 'THOX external SSD' -Completed
    }
}

function Test-ThoxWrittenDisk {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$PlanPath)
    $context = $null; $session = $null
    try {
        $context = Open-ThoxPlanContext $PlanPath -ReadOnlyVerification
        $session = [Thox.ExternalSsd.DiskSession]::Open($context.Disk.Path, $false)
        Assert-ThoxSessionIdentity $session $context.Plan.Target
        return $session.Verify([long]$context.Plan.Image.ImageBytes, [string]$context.Plan.Image.ImageSha256, [long]$context.Plan.Tail.Offset, [long]$context.Plan.Tail.Bytes, (New-ThoxProgress))
    } finally {
        if ($null -ne $session) { $session.Dispose() }
        if ($null -ne $context) { $context.Image.Dispose() }
        Write-Progress -Id 71 -Activity 'THOX external SSD' -Completed
    }
}

function Get-ThoxReceipt {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$ReceiptPath)
    Initialize-ThoxNative
    $record = Read-ThoxJson $ReceiptPath
    if ((Get-ThoxText $record.Object 'Schema') -cne 'thox.external-ssd.receipt.v1') { throw 'Unsupported receipt schema.' }
    return $record.Object
}

Export-ModuleMember -Function Get-ThoxHostSnapshot, Get-ThoxDiskInventory, Get-ThoxPreflight, New-ThoxDiskPlan, Invoke-ThoxDiskWrite, Test-ThoxWrittenDisk, Get-ThoxReceipt
