<#
.SYNOPSIS
  Write the ThoxOS Ginux Edition KnightHub disk image to an external SSD (Windows).

.DESCRIPTION
  ERASES the target disk. Guards, all checked before a byte is written:
    * must run elevated (Administrator)
    * target must not be the boot or system disk
    * target bus must be USB unless -AllowInternal
    * target must be at least as large as the image
    * a disk with a Windows-visible volume labeled THOXOS needs -EraseExistingThoxos
    * the operator types the disk number back (or passes -ConfirmDiskNumber)
  After writing, the partition region is read back and compared by SHA-256.

  Validation status: this script has not been run on Windows by the author's
  build pipeline. Rufus (DD image mode) or balenaEtcher are equivalent
  alternatives for writing the same .img file.

.EXAMPLE
  .\Install-ThoxOSGinux.ps1 -ImagePath .\thoxos-ginux-knighthub-0.1.0.img -DiskNumber 3
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ImagePath,
    [Parameter(Mandatory = $true)][int]$DiskNumber,
    [int]$ConfirmDiskNumber = -1,
    [switch]$AllowInternal,
    [switch]$EraseExistingThoxos,
    [switch]$SkipVerify
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ChunkBytes = 4MB
$RegionOffset = 1MB

function Fail([string]$Message) {
    Write-Error "Install-ThoxOSGinux: $Message" -ErrorAction Continue
    exit 1
}

function Get-RegionHash([string]$Path, [long]$Offset, [long]$Length, [bool]$IsDevice) {
    # SHA-256 of [Offset, Offset + Length) read in sector-aligned chunks.
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = if ($IsDevice) {
        [System.IO.FileStream]::new($Path, 'Open', 'Read', 'ReadWrite', $ChunkBytes)
    } else {
        [System.IO.File]::OpenRead($Path)
    }
    try {
        [void]$stream.Seek($Offset, 'Begin')
        $buffer = New-Object byte[] $ChunkBytes
        $remaining = $Length
        while ($remaining -gt 0) {
            $want = [int][Math]::Min([long]$ChunkBytes, $remaining)
            $read = $stream.Read($buffer, 0, $want)
            if ($read -le 0) { throw "short read at offset $($Offset + $Length - $remaining)" }
            [void]$sha.TransformBlock($buffer, 0, $read, $null, 0)
            $remaining -= $read
        }
        [void]$sha.TransformFinalBlock(@(), 0, 0)
        return ([BitConverter]::ToString($sha.Hash) -replace '-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
}

$principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Fail 'run this script from an elevated PowerShell (Run as administrator)'
}

$image = Get-Item -LiteralPath $ImagePath -ErrorAction SilentlyContinue
if (-not $image) { Fail "image not found: $ImagePath" }
if ($image.Extension -ne '.img') { Fail 'pass the uncompressed .img (decompress .xz with 7-Zip first)' }
$imageBytes = [long]$image.Length
if ($imageBytes -le 0 -or ($imageBytes % 1MB) -ne 0) { Fail 'image size must be a positive multiple of 1 MiB' }

$disk = Get-Disk -Number $DiskNumber -ErrorAction SilentlyContinue
if (-not $disk) { Fail "disk $DiskNumber not found (see Get-Disk)" }
if ($disk.IsBoot -or $disk.IsSystem) { Fail "disk $DiskNumber is the boot or system disk" }
if ($disk.BusType -ne 'USB' -and -not $AllowInternal) {
    Fail "disk $DiskNumber bus type is $($disk.BusType), not USB; pass -AllowInternal if you are certain"
}
if ([long]$disk.Size -lt $imageBytes) { Fail "disk $DiskNumber ($($disk.Size) bytes) is smaller than the image ($imageBytes bytes)" }

$labels = @(Get-Partition -DiskNumber $DiskNumber -ErrorAction SilentlyContinue |
    Get-Volume -ErrorAction SilentlyContinue | ForEach-Object { $_.FileSystemLabel })
if ($labels -contains 'THOXOS' -and -not $EraseExistingThoxos) {
    Fail "disk $DiskNumber has a volume labeled THOXOS (the ThoxOS Vibe SSD); pass -EraseExistingThoxos to replace it"
}

Write-Host 'Target:'
$disk | Format-Table Number, FriendlyName, SerialNumber, BusType, @{n = 'SizeGB'; e = { [Math]::Round($_.Size / 1GB, 1) } } -AutoSize | Out-Host
Write-Host ("Image:  {0} ({1:N0} MiB)" -f $image.FullName, ($imageBytes / 1MB))
Write-Host "Everything on disk $DiskNumber will be destroyed." -ForegroundColor Yellow
if ($ConfirmDiskNumber -lt 0) {
    $typed = Read-Host "Type the disk number ($DiskNumber) to continue"
    if ($typed -ne "$DiskNumber") { Fail 'confirmation did not match; nothing was written' }
} elseif ($ConfirmDiskNumber -ne $DiskNumber) {
    Fail 'confirmation did not match; nothing was written'
}

# Remove partitions so Windows holds no volume locks on the disk, then write raw.
if ($disk.IsReadOnly) { Set-Disk -Number $DiskNumber -IsReadOnly $false }
if ($disk.PartitionStyle -ne 'RAW') {
    Clear-Disk -Number $DiskNumber -RemoveData -RemoveOEM -Confirm:$false
}
Set-Disk -Number $DiskNumber -IsOffline $true

$devicePath = "\\.\PhysicalDrive$DiskNumber"
$source = [System.IO.File]::OpenRead($image.FullName)
$target = [System.IO.FileStream]::new($devicePath, 'Open', 'ReadWrite', 'ReadWrite', $ChunkBytes, [System.IO.FileOptions]::WriteThrough)
try {
    $buffer = New-Object byte[] $ChunkBytes
    $written = [long]0
    while ($written -lt $imageBytes) {
        $read = $source.Read($buffer, 0, $ChunkBytes)
        if ($read -le 0) { throw "unexpected end of image at $written bytes" }
        $target.Write($buffer, 0, $read)
        $written += $read
        Write-Progress -Activity 'Writing ThoxOS Ginux Edition' -Status ("{0:N0} / {1:N0} MiB" -f ($written / 1MB), ($imageBytes / 1MB)) -PercentComplete ([int](100 * $written / $imageBytes))
    }
    $target.Flush($true)
} finally {
    $source.Dispose()
    $target.Dispose()
    Write-Progress -Activity 'Writing ThoxOS Ginux Edition' -Completed
}

if (-not $SkipVerify) {
    Write-Host 'Verifying...'
    $region = $imageBytes - 2MB
    $expected = Get-RegionHash $image.FullName $RegionOffset $region $false
    $actual = Get-RegionHash $devicePath $RegionOffset $region $true
    if ($expected -ne $actual) { Set-Disk -Number $DiskNumber -IsOffline $false; Fail 'verification failed: disk contents differ from the image' }
    Write-Host 'Partitions verified.'
}

Set-Disk -Number $DiskNumber -IsOffline $false
Update-Disk -Number $DiskNumber
Write-Host ''
Write-Host 'Done. Disable Secure Boot in firmware setup, keep the SSD plugged in, reboot, open the'
Write-Host 'boot menu (F11 or F12 on most desktop boards) and pick the UEFI entry for this SSD.'
Write-Host 'Windows will not show the Linux partitions; that is expected. First boot grows the'
Write-Host 'root partition to fill the SSD. Console: tty1. Admin: Ctrl-Alt-F2, user thox.'
