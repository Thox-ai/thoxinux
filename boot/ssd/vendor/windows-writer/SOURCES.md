# Windows provisioning source and API record

Reviewed October 26, 2026. This technical record does not establish Windows hardware acceptance. The runtime does not download a payload.

## Primary Microsoft contracts

| Source | Applied behavior |
| --- | --- |
| [Get-Disk](https://learn.microsoft.com/en-us/powershell/module/storage/get-disk?view=windowsserver2025-ps) and [MSFT_Disk](https://learn.microsoft.com/en-us/windows-hardware/drivers/storage/msft-disk) | Provider identity, bus, boot/system flags, health and sectors; disk numbers are not persistent identities |
| [Get-Partition](https://learn.microsoft.com/en-us/powershell/module/storage/get-partition?view=windowsserver2025-ps), [Get-Volume](https://learn.microsoft.com/en-us/powershell/module/storage/get-volume?view=windowsserver2025-ps), [Win32_LogicalDiskToPartition](https://learn.microsoft.com/en-us/windows/win32/cimwin32prov/win32-logicaldisktopartition) and [Win32_Volume](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/vdswmi/win32-volume) | Read-only D: volume-to-partition-to-disk cross-check, including all backing-disk partitions; no drive-letter-only write selection |
| [CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew) | Retain the verified device-interface handle through writing and readback |
| [STORAGE_DEVICE_DESCRIPTOR](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-storage_device_descriptor) | Bind descriptor/serial/bus and device-ID fingerprints from the opened device |
| [IOCTL_STORAGE_GET_DEVICE_NUMBER](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_storage_get_device_number) | Cross-check the open handle with current enumeration |
| [IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_volume_get_volume_disk_extents) | Resolve volume GUIDs, mount points and protected locations to physical disks |
| [GetFinalPathNameByHandleW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getfinalpathnamebyhandlew) | Resolve actual opened file/directory locations, including reparse/mount-point resolution |
| [FSCTL_LOCK_VOLUME](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-fsctl_lock_volume) | Lock before dismount; keep successful lock handles until cleanup |
| [IOCTL_DISK_SET_DISK_ATTRIBUTES](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ni-winioctl-ioctl_disk_set_disk_attributes) and [SET_DISK_ATTRIBUTES](https://learn.microsoft.com/en-us/windows/win32/api/winioctl/ns-winioctl-set_disk_attributes) | Set only the selected external disk offline after authorization; never clear read-only state or automatically return online |
| [File buffering](https://learn.microsoft.com/en-us/windows/win32/fileio/file-buffering) | Unbuffered sector-aligned I/O, 64 KiB aligned memory, write-through and flush before complete readback |
| [GetFirmwareType](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getfirmwaretype) | Confirm UEFI without changing firmware |
| [Win32_EncryptableVolume.GetProtectionStatus](https://learn.microsoft.com/en-us/windows/win32/secprov/getprotectionstatus-win32-encryptablevolume) | Read protection status without protector/recovery-key enumeration |
| [PowerShell execution policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1) | Explicit process RemoteSigned and reviewed-file unblocking, honoring organizational policy |

Write-through and unbuffered readback reduce dependence on OS caching. They do not prove that a USB bridge/SSD honors every flush through sudden power loss; hardware acceptance remains separate.

The IOCTL function values, access flags, native USB bus enumeration and structure layouts were also compared with Microsoft's [WinSDK winioctl.h source](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/winioctl.h), retrieved as Git blob **8db00c7dc9772c4b90b36e0e84bb505731e2813b**. This was a source comparison; it does not claim a Windows SDK build or native API execution.

## Preserved owner protection policy

The existing lane was inspected at thoxos-vibe-rust revision:

~~~text
77f38105717cb3874d1805bdc77c38ef2be197b8
~~~

Its [protection constants](https://github.com/ttracx/thoxos-vibe-rust/blob/77f38105717cb3874d1805bdc77c38ef2be197b8/crates/thox-api/src/lib.rs) protect serial VY2EJ04M and label/mount fragments VibeStore, THOXSTORE, THOXKEY and WD Game Drive. The new policy retains case-insensitive substring protection. It adds strict hardware/handle identity, complete partition-to-volume mapping for writes, host/source exclusions and full-image verification.

Unknown foreign filesystem labels are not silently assumed safe. An unmapped partition blocks writing; only a known Microsoft Reserved partition without a filesystem is exempt from volume mapping. No internal or foreign-partition override is exposed.

## Payload contract

The schema is thox.external-ssd.raw-gpt.v1: uncompressed persistent installed-system image; x86-64 UEFI fallback; 512-byte logical sectors; GPT; FAT32 ESP and Linux root. The manifest pins exact image bytes/SHA-256, minimum target bytes and source commit. The operator supplies the independent publisher manifest digest.

The source tree never substitutes synthetic fixture bytes or unresolved hashes for a released payload. Test images are explicitly nonbootable.

## Runtime evidence

Development uses PowerShell 7.6.9 on Linux, extracted from Microsoft's package repository without running maintainer scripts. The package matched repository metadata SHA-256. C# sources compile with language version 5. Disk-free tests cover structural admission, full file hashing, JSON/receipt files, default dry run, WhatIf and redirected-confirmation refusal.

The exact [Microsoft package](https://packages.microsoft.com/repos/microsoft-ubuntu-noble-prod/pool/main/p/powershell/powershell_7.6.9-1.deb_amd64.deb) was 54,037,262 bytes with SHA-256 **491b1a51e257e2ac86af33e3a4dc9aa91adb1b3926a57967af39d9a1ca38dc79**. Test results bind the source hashes and report any source changes during execution.

Windows PowerShell 5.1/.NET Framework execution, Win32 P/Invoke, actual USB-volume locking/offlining, physical write/readback and hardware boot are unrun in this environment. The final delivery receipt separates these from any VM image-boot evidence.
