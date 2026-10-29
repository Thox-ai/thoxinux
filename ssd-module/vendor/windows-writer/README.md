# THOX external SSD provisioning for Windows

This kit prepares a persistent ThoxOS NiceC0re installation on a specifically identified external USB SSD. Windows stays on the internal drive. After provisioning, use the PC's one-time **UEFI** boot menu to choose the external SSD.

**The selected SSD's existing contents will be destroyed.** Back them up separately. A receipt and a verified image do not recover previous SSD contents.

This is an engineering candidate. Disk-free PowerShell/C# tests and independent safety review are recorded in the delivery evidence. Windows PowerShell 5.1 execution, native Windows device calls and a physical USB SSD write have not been exercised in this development environment. Consult the final delivery receipt for the actual image, VM and hardware validation state.

## Requirements

- Windows x64 on an x86-64 UEFI PC, with 64-bit PowerShell 5.1 or newer.
- An administrator **local ConsoleHost** for planning and writing. ISE, remoting and redirected confirmation input are refused for destructive writes.
- A USB SSD with unique, concrete serial and storage UniqueId values, 512-byte logical sectors, and adequate capacity. The image contract specifies at least 32,000,000,000 bytes.
- A verified raw .img and payload-manifest.json, with the image beside the manifest. ZIP, ISO, compressed input, live installers and unresolved manifests are refused by the writer.
- The kit, image, plan and receipts on another physical drive. Use a filesystem that can hold the image, such as NTFS; FAT32 cannot hold a file larger than 4 GiB.

Only USB-bus targets are supported. There is no internal-disk override. Bridges may not report SSD/HDD type, so match the physical SSD's model, serial and size. A bridge without usable handle identity is refused.

The target must be blank or have partitions whose labels can be inspected through Windows. Foreign or uninspectable partitions are refused. A known Microsoft Reserved partition without a filesystem is handled separately. This conservative rule preserves protected-volume exclusions; reimaging an existing Linux SSD may need a separately reviewed storage recovery operation.

The kit observes firmware mode, Secure Boot and system-volume protection status. It does not obtain recovery material or change Secure Boot, BitLocker, boot order, BCD, TPM or NVRAM.

## Authorize this reviewed copy for one PowerShell process

Compare the downloaded archive's SHA-256 with the independently supplied delivery receipt:

~~~powershell
Get-FileHash -LiteralPath .\ThoxOS_NiceC0re_External_SSD_Kit.zip -Algorithm SHA256
~~~

Extract the complete verified kit to a separate drive. Open **64-bit Windows PowerShell as Administrator**, change to the extracted script folder and review the source. Check applicable policy:

~~~powershell
Get-ExecutionPolicy -List
~~~

If MachinePolicy or UserPolicy is set by your organization, follow it. An organization requiring signed code must approve/sign this reviewed source through its existing process. Do not override organizational policy.

On a personally managed PC with both Group Policy scopes Undefined, start a process-scoped RemoteSigned console:

~~~powershell
powershell.exe -NoLogo -NoProfile -ExecutionPolicy RemoteSigned
~~~

In that new console, after verifying and reviewing the extracted code, explicitly unblock only these files if they retain an Internet-zone marker:

~~~powershell
$reviewedFiles = @(
    '.\Inspect-D-Drive.ps1',
    '.\thox-external-ssd.ps1',
    '.\Thox.ExternalSsd.psm1',
    '.\Thox.Ssd.Policy.psm1',
    '.\Thox.Image.cs',
    '.\Thox.WindowsStorage.cs'
)
foreach ($file in $reviewedFiles) {
    Unblock-File -LiteralPath $file
}
Get-ExecutionPolicy
~~~

These are explicit operator actions. The launcher performs neither, never uses Bypass and never elevates automatically. Microsoft documents process-only scope, Group Policy precedence and reviewed-file unblocking in [about_Execution_Policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1).

## If the intended SSD currently appears as D:

After authorizing this verified copy as above, run the dedicated read-only check:

~~~powershell
.\Inspect-D-Drive.ps1
.\Inspect-D-Drive.ps1 -Json
~~~

The script resolves the local D: volume to one consistent backing disk, displays its number, UniqueId, serial, exact bytes, bus, boot/system flags and every partition/label, then runs the existing THOX protection inventory. Missing D:, network mappings, SUBST/path aliases, spanned or ambiguous associations and changed observations produce a clear refusal. Unknown filesystem labels remain explicit and may make the disk ineligible.

**D: is a volume, not proof of an external SSD.** If D: is a partition on the internal Windows disk, that entire disk is protected and must not be provisioned. If D: is on an eligible external USB SSD, any later confirmed full-image write erases **all partitions on that physical SSD**, not just the D: volume. Match the reported model and serial to the physical device before using the separate planning workflow.

This convenience script never creates a plan, formats, offlines or writes a disk, and never elevates itself. Its result is a read-only snapshot, not write authorization. Keep the verified kit and payload on a different physical disk.

## Inventory and source verification

~~~powershell
.\thox-external-ssd.ps1 inventory
.\thox-external-ssd.ps1 inventory -Json
~~~

Start-ThoxOS-SSD.cmd runs the same read-only inventory. No target is selected automatically. Match model, serial, UniqueId and exact Size. Eligibility concerns the device; image fit and publisher hashes are checked during planning. Drive letters and disk numbers alone cannot authorize a write.

Set the manifest digest to the exact value in the delivery receipt:

~~~powershell
$manifestHash = '<published lowercase manifest SHA-256>'
.\thox-external-ssd.ps1 preflight -ManifestPath .\payload-manifest.json -ExpectedManifestSha256 $manifestHash
~~~

Preflight verifies manifest provenance by that supplied digest, exact image length and complete image SHA-256. It checks GPT CRCs and extents, exactly two partitions with unique IDs, a bounded Linux filesystem, and FAT32 EFI/BOOT/BOOTX64.EFI with an x64 PE32+ EFI application header. These are structural checks, not a firmware boot or signature attestation.

The source image remains open with sharing that denies modification/replacement throughout each validated operation. A successful preflight does not authorize later substituted bytes.

## Plan and dry run

Replace every bracketed field with the actual inventory value:

~~~powershell
.\thox-external-ssd.ps1 plan -ManifestPath .\payload-manifest.json -ExpectedManifestSha256 $manifestHash -DiskUniqueId '<exact UniqueId>' -DiskSerial '<exact serial>' -ExpectedDiskBytes <exact byte size> -PlanPath .\ssd-plan.json
~~~

Planning saves JSON and does not alter a disk. The plan records host boot session, hardware/handle identity, geometry, partition/volume observations, image digest and exact write ranges. It expires after 24 hours and becomes stale after a host restart, identity change or enumeration change. Use a new filename to preserve earlier plans. Plan with -WhatIf also suppresses saving the file.

Boot/system, internal, read-only, initially offline, unhealthy, clustered, ambiguous and protected targets are refused. Windows, pagefile, kit, image, manifest, plan and receipt locations are excluded by their resolved physical disks.

~~~powershell
.\thox-external-ssd.ps1 write -PlanPath .\ssd-plan.json
~~~

This revalidates the plan and payload without opening a writable disk handle. Write with -Apply -WhatIf also remains read-only.

The plan clears the target's last 1 MiB only when wholly beyond the image, removing stale backup GPT data. An exact-sized target retains the image's backup GPT. Less than 1 MiB of spare space is refused. This is **not secure erase**: data remnants outside the written ranges may remain.

## Authorize the write

~~~powershell
.\thox-external-ssd.ps1 write -PlanPath .\ssd-plan.json -Apply
~~~

The console displays the actual model, serial, UniqueId, capacity, image digest and tail range, then requires an exact, case-sensitive phrase:

~~~text
ERASE USB SSD <serial> <exact bytes> BYTES PLAN <plan ID>
~~~

No parameter supplies or bypasses this phrase. Confirm false does not skip it. A global mutex prevents concurrent kit writers.

After confirmation, identity and exclusions are refreshed. The writer opens a stable device-interface path and checks that retained handle against the plan. It locks every target volume GUID, including volumes without letters, before dismounting. Missing labels, unmapped partitions, changed enumeration or failed locks cause refusal.

The **same retained device handle** takes the target offline, writes, flushes, reads every image byte back for SHA-256, and clears/verifies the declared tail. No write target is reopened by disk number. Failed or short I/O stops the operation.

Progress distinguishes source hashing, writing and readback. Writing at 100% is not success. Success requires the final written-and-readback-verified result and a receipt with Phase verified.

## Verify and boot

The writer leaves the Linux SSD offline in Windows. An optional additional read-only check is available immediately, while the original host/plan session is valid, **before the first Linux boot**:

~~~powershell
.\thox-external-ssd.ps1 verify -PlanPath .\ssd-plan.json
~~~

Then safely remove the SSD and follow the PC manufacturer's one-time UEFI boot-menu instructions. Choose Windows Boot Manager to return to Windows. Cancel Windows initialize/format prompts for the Linux SSD.

Linux use changes filesystem bytes. The original raw-image hash is not a post-use health check; do not reflash because a used installation differs. Capacity expansion is a separate, explicitly confirmed Linux action in the main installation guide. The Windows writer does not relocate GPT or grow filesystems.

## Receipts and recovery

Receipts default to %LOCALAPPDATA%\THOX\ExternalSSD\receipts\<plan ID>.json. Plan with -ReceiptDirectory can select a different separate-disk location.

~~~powershell
.\thox-external-ssd.ps1 status -ReceiptPath '<printed receipt path>'
~~~

A receipt is exclusively created before image writes; another operation's existing receipt is preserved. Later phases use atomic replacement. Hard power loss or process termination can leave a prior phase and unknown physical state. Only Phase verified records completed readback.

On failure, keep the SSD offline and preserve the error/receipt. Do not boot or format it. No old-data rollback exists. A retry needs source verification and a new target plan. If the disk remains offline or contains unreadable foreign partitions, resolve that state through a separate, target-confirmed storage recovery action; the kit never silently brings it online or disables exclusions.

## Files and evidence boundaries

Thox.Ssd.Policy.psm1 supplies pure admission rules. Thox.Image.cs validates images and atomically replaces receipts. Thox.WindowsStorage.cs owns Windows device access. Thox.ExternalSsd.psm1 coordinates inventory, plans, authorization and receipts. The entrypoint is thox-external-ssd.ps1.

Disk-free test results do not certify Windows drivers, USB bridge firmware, power-loss persistence, physical boot, GPU support or the installed desktop. [SOURCES.md](SOURCES.md) records the API and owner-policy sources.
