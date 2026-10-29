// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 THOX.ai LLC.
// C# 5-compatible Windows interop. Never called by the Linux/file-only test suite.
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace Thox.ExternalSsd
{
    internal static class Win32
    {
        internal const uint GenericRead = 0x80000000, GenericWrite = 0x40000000;
        internal const uint ShareReadWrite = 3, OpenExisting = 3;
        internal const uint NoBuffering = 0x20000000, WriteThrough = 0x80000000, BackupSemantics = 0x02000000;
        // CTL_CODE values from the Windows SDK winioctl.h.
        internal const uint StorageQueryProperty = 0x002d1400, StorageGetDeviceNumber = 0x002d1080;
        internal const uint DiskGetLength = 0x0007405c, VolumeGetDiskExtents = 0x00560000;
        internal const uint LockVolume = 0x00090018, DismountVolume = 0x00090020;
        internal const uint DiskGetAttributes = 0x000700f0, DiskSetAttributes = 0x0007c0f4;
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern SafeFileHandle CreateFileW(string name, uint access, uint share, IntPtr security, uint creation, uint flags, IntPtr template);
        [DllImport("kernel32.dll", EntryPoint = "DeviceIoControl", SetLastError = true)]
        internal static extern bool Ioctl(SafeFileHandle device, uint code, byte[] input, uint inputSize, byte[] output, uint outputSize, out uint returned, IntPtr overlapped);
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool SetFilePointerEx(SafeFileHandle device, long distance, out long position, uint origin);
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool ReadFile(SafeFileHandle device, IntPtr buffer, uint count, out uint read, IntPtr overlapped);
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool WriteFile(SafeFileHandle device, IntPtr buffer, uint count, out uint written, IntPtr overlapped);
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool FlushFileBuffers(SafeFileHandle device);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern IntPtr FindFirstVolumeW(StringBuilder volume, uint capacity);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern bool FindNextVolumeW(IntPtr find, StringBuilder volume, uint capacity);
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool FindVolumeClose(IntPtr find);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern bool GetVolumeInformationW(string root, StringBuilder label, uint labelLength, out uint serial, out uint maxComponent, out uint flags, StringBuilder fs, uint fsLength);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern bool GetVolumePathNamesForVolumeNameW(string name, char[] paths, uint length, out uint needed);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        internal static extern uint GetDriveTypeW(string root);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        internal static extern uint GetFinalPathNameByHandleW(SafeFileHandle file, StringBuilder path, uint size, uint flags);
        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool GetFirmwareType(out uint kind);
        [DllImport("kernel32.dll")]
        internal static extern void GetNativeSystemInfo(IntPtr info);

        internal static void RequireWindows()
        {
            if (Environment.OSVersion.Platform != PlatformID.Win32NT || !Environment.Is64BitProcess) throw new PlatformNotSupportedException("Windows x64 process required for native disk access.");
        }
        internal static Exception Error(string operation) { return new Win32Exception(Marshal.GetLastWin32Error(), operation); }
        internal static SafeFileHandle Open(string path, uint access, uint flags)
        {
            SafeFileHandle handle = CreateFileW(path, access, ShareReadWrite, IntPtr.Zero, OpenExisting, flags, IntPtr.Zero);
            if (handle.IsInvalid) { Exception error = Error("Open device/file failed: " + path); handle.Dispose(); throw error; }
            return handle;
        }
        internal static byte[] Query(SafeFileHandle handle, uint code, byte[] input, int capacity)
        {
            byte[] output = new byte[capacity]; uint returned;
            if (!Ioctl(handle, code, input, input == null ? 0 : (uint)input.Length, output, (uint)capacity, out returned, IntPtr.Zero)) throw Error("Device query failed, code 0x" + code.ToString("x"));
            if (returned > output.Length) throw new IOException("Device returned an oversized response.");
            Array.Resize(ref output, (int)returned); return output;
        }
        internal static void Control(SafeFileHandle handle, uint code, byte[] input)
        {
            uint returned;
            if (!Ioctl(handle, code, input, input == null ? 0 : (uint)input.Length, null, 0, out returned, IntPtr.Zero)) throw Error("Device control failed, code 0x" + code.ToString("x"));
        }
    }

    public sealed class VolumeIdentity
    {
        public string Name { get; set; }
        public int[] DiskNumbers { get; set; }
        public bool ExtentsKnown { get; set; }
        public string Label { get; set; }
        public bool LabelKnown { get; set; }
        public string[] MountPaths { get; set; }
        public string Error { get; set; }
    }
    public sealed class DiskIdentity
    {
        public int Number { get; set; }
        public long Size { get; set; }
        public int LogicalSectorSize { get; set; }
        public int PhysicalSectorSize { get; set; }
        public int BusType { get; set; }
        public string DescriptorSerial { get; set; }
        public string DescriptorSha256 { get; set; }
        public string DeviceIdSha256 { get; set; }
        public bool HasDeviceId { get; set; }
    }
    public sealed class VerificationResult
    {
        public string ImageSha256 { get; set; }
        public long ImageBytesVerified { get; set; }
        public long TailBytesVerified { get; set; }
        public bool Offline { get; set; }
        public string Scope { get { return "Full image-prefix SHA-256 and declared tail readback. This does not prove firmware boot, persistence across power loss or restoration of previous SSD data."; } }
    }

    public static class WindowsStorage
    {
        public static string Firmware()
        {
            Win32.RequireWindows(); uint type;
            if (!Win32.GetFirmwareType(out type)) throw Win32.Error("Cannot determine host firmware.");
            return type == 2 ? "UEFI" : (type == 1 ? "BIOS" : "Unknown");
        }
        public static string Architecture()
        {
            Win32.RequireWindows(); IntPtr memory = Marshal.AllocHGlobal(64);
            try { Win32.GetNativeSystemInfo(memory); ushort kind = (ushort)Marshal.ReadInt16(memory); return kind == 9 ? "x64" : (kind == 12 ? "arm64" : "unsupported"); }
            finally { Marshal.FreeHGlobal(memory); }
        }
        public static string[] VolumeNames()
        {
            Win32.RequireWindows(); List<string> result = new List<string>(); StringBuilder name = new StringBuilder(1024);
            IntPtr find = Win32.FindFirstVolumeW(name, 1024);
            if (find == new IntPtr(-1)) throw Win32.Error("Cannot enumerate volume GUIDs.");
            try {
                while (true) {
                    result.Add(name.ToString());
                    if (result.Count > 4096) throw new IOException("Volume inventory is unexpectedly large.");
                    name.Clear();
                    if (!Win32.FindNextVolumeW(find, name, 1024)) {
                        int error = Marshal.GetLastWin32Error();
                        if (error == 18) break;
                        throw new Win32Exception(error, "Volume enumeration was incomplete.");
                    }
                }
            } finally { Win32.FindVolumeClose(find); }
            result.Sort(StringComparer.OrdinalIgnoreCase); return result.ToArray();
        }
        internal static int[] Extents(SafeFileHandle volume)
        {
            byte[] b = Win32.Query(volume, Win32.VolumeGetDiskExtents, null, 16384);
            if (b.Length < 8) throw new IOException("Incomplete volume extents.");
            uint count = BitConverter.ToUInt32(b, 0);
            if (count == 0 || count > 512 || b.Length < 8 + count * 24) throw new IOException("Invalid or unsupported volume extent count.");
            List<int> disks = new List<int>();
            for (int i = 0; i < count; i++) {
                int number = checked((int)BitConverter.ToUInt32(b, 8 + i * 24));
                disks.Add(number); // Preserve repeated extents: a spanned volume is not a single safe target extent.
            }
            disks.Sort(); return disks.ToArray();
        }
        public static VolumeIdentity[] Volumes()
        {
            Win32.RequireWindows(); List<VolumeIdentity> result = new List<VolumeIdentity>();
            foreach (string name in VolumeNames()) {
                if (Win32.GetDriveTypeW(name) == 5) continue; // Optical media are never disk targets.
                VolumeIdentity volume = new VolumeIdentity { Name = name, DiskNumbers = new int[0], Label = "", MountPaths = new string[0] };
                try {
                    using (SafeFileHandle h = Win32.Open(name.TrimEnd('\\'), 0, 0)) volume.DiskNumbers = Extents(h);
                    volume.ExtentsKnown = true;
                    uint serial, component, flags; StringBuilder label = new StringBuilder(1024), fs = new StringBuilder(1024);
                    volume.LabelKnown = Win32.GetVolumeInformationW(name, label, 1024, out serial, out component, out flags, fs, 1024);
                    volume.Label = label.ToString();
                    char[] paths = new char[32768]; uint needed;
                    if (!Win32.GetVolumePathNamesForVolumeNameW(name, paths, (uint)paths.Length, out needed)) throw Win32.Error("Cannot enumerate all mount paths.");
                    volume.MountPaths = new string(paths).Split(new char[] { '\0' }, StringSplitOptions.RemoveEmptyEntries);
                } catch (Exception e) { volume.Error = e.Message; }
                result.Add(volume);
            }
            return result.ToArray();
        }
        public static int[] HandleDiskNumbers(SafeFileHandle file)
        {
            Win32.RequireWindows(); StringBuilder path = new StringBuilder(32768);
            uint length = Win32.GetFinalPathNameByHandleW(file, path, (uint)path.Capacity, 1);
            if (length == 0 || length >= path.Capacity) throw Win32.Error("Cannot resolve the opened path to a local volume GUID.");
            string text = path.ToString(); int close = text.IndexOf("}\\", StringComparison.Ordinal);
            if (!text.StartsWith(@"\\?\Volume{", StringComparison.OrdinalIgnoreCase) || close < 0) throw new IOException("Only locally resolvable volume-backed kit/image/receipt paths are accepted.");
            string volume = text.Substring(0, close + 1);
            using (SafeFileHandle handle = Win32.Open(volume, 0, 0)) return Extents(handle);
        }
        public static int[] PathDiskNumbers(string path)
        {
            Win32.RequireWindows();
            using (SafeFileHandle handle = Win32.Open(System.IO.Path.GetFullPath(path), 0, Win32.BackupSemantics)) return HandleDiskNumbers(handle);
        }
        public static bool IsProtectedVolume(VolumeIdentity volume)
        {
            string[] protectedNames = { "VibeStore", "THOXSTORE", "THOXKEY", "WD Game Drive" };
            List<string> text = new List<string>(volume.MountPaths); text.Add(volume.Label);
            foreach (string value in text) foreach (string name in protectedNames)
                if (value != null && value.IndexOf(name, StringComparison.OrdinalIgnoreCase) >= 0) return true;
            return false;
        }
    }

    public sealed class DiskSession : IDisposable
    {
        private SafeFileHandle Handle;
        private readonly bool Writable;
        private readonly List<SafeFileHandle> Locks = new List<SafeFileHandle>();
        private bool Exclusive;
        public bool ImageWriteStarted { get; private set; }
        public long ImageBytesWritten { get; private set; }
        public bool TailWriteStarted { get; private set; }
        public bool OfflineSet { get; private set; }
        public DiskIdentity Identity { get; private set; }

        private DiskSession(string path, bool writable)
        {
            Win32.RequireWindows();
            if (path == null || !path.StartsWith(@"\\?\", StringComparison.Ordinal) || path.IndexOf("PhysicalDrive", StringComparison.OrdinalIgnoreCase) >= 0) throw new ArgumentException("Stable device-interface path required; number aliases are refused.");
            Writable = writable;
            try {
                Handle = Win32.Open(path, Win32.GenericRead | (writable ? Win32.GenericWrite : 0), Win32.NoBuffering | (writable ? Win32.WriteThrough : 0));
                Identity = InspectHandle();
                if (Identity.BusType != 7 || Identity.LogicalSectorSize != 512) throw new IOException("Retained device handle is not USB with 512-byte logical sectors.");
                if (Identity.PhysicalSectorSize < 512 || Identity.PhysicalSectorSize > 65536 || (Identity.PhysicalSectorSize & (Identity.PhysicalSectorSize - 1)) != 0) throw new IOException("Unsupported physical-sector alignment.");
                if (String.IsNullOrWhiteSpace(Identity.DescriptorSerial) && !Identity.HasDeviceId) throw new IOException("The bridge exposes no serial or device-ID evidence through its retained handle.");
                if (Identity.DescriptorSerial.IndexOf("VY2EJ04M", StringComparison.OrdinalIgnoreCase) >= 0) throw new IOException("Protected THOX never-write device.");
            } catch { Dispose(); throw; }
        }
        public static DiskSession Open(string path, bool writable) { return new DiskSession(path, writable); }
        public static DiskIdentity Probe(string path) { using (DiskSession session = Open(path, false)) return session.Identity; }
        private static byte[] Property(SafeFileHandle handle, int property)
        {
            byte[] query = new byte[12]; Buffer.BlockCopy(BitConverter.GetBytes(property), 0, query, 0, 4);
            byte[] header = Win32.Query(handle, Win32.StorageQueryProperty, query, 8);
            if (header.Length < 8) throw new IOException("Storage property header is incomplete.");
            uint size = BitConverter.ToUInt32(header, 4);
            if (size < 8 || size > 1048576) throw new IOException("Storage property size is invalid.");
            byte[] full = Win32.Query(handle, Win32.StorageQueryProperty, query, (int)size);
            if (full.Length < size) throw new IOException("Storage property response is truncated.");
            return full;
        }
        private static string DescriptorText(byte[] data, int offsetField)
        {
            uint at = BitConverter.ToUInt32(data, offsetField);
            if (at == 0) return "";
            if (at >= data.Length) throw new IOException("Device descriptor has an invalid string offset.");
            int end = (int)at;
            while (end < data.Length && data[end] != 0) end++;
            if (end == data.Length) throw new IOException("Device descriptor string is not terminated.");
            return Encoding.ASCII.GetString(data, (int)at, end - (int)at).Trim();
        }
        private DiskIdentity InspectHandle()
        {
            byte[] number = Win32.Query(Handle, Win32.StorageGetDeviceNumber, null, 12);
            byte[] length = Win32.Query(Handle, Win32.DiskGetLength, null, 8);
            byte[] descriptor = Property(Handle, 0), alignment = Property(Handle, 6), ids;
            if (number.Length < 12 || BitConverter.ToUInt32(number, 0) != 7 || length.Length != 8 || descriptor.Length < 36 || alignment.Length < 28) throw new IOException("Incomplete physical-disk identity.");
            bool hasIds = false;
            try { ids = Property(Handle, 2); hasIds = ids.Length >= 12 && BitConverter.ToUInt32(ids, 8) > 0; }
            catch (Win32Exception e) { if (e.NativeErrorCode != 1 && e.NativeErrorCode != 50 && e.NativeErrorCode != 87) throw; ids = new byte[0]; }
            return new DiskIdentity {
                Number = checked((int)BitConverter.ToUInt32(number, 4)), Size = BitConverter.ToInt64(length, 0),
                LogicalSectorSize = checked((int)BitConverter.ToUInt32(alignment, 16)), PhysicalSectorSize = checked((int)BitConverter.ToUInt32(alignment, 20)),
                BusType = checked((int)BitConverter.ToUInt32(descriptor, 28)), DescriptorSerial = DescriptorText(descriptor, 24),
                DescriptorSha256 = ImageChecks.Sha256Bytes(descriptor), DeviceIdSha256 = ImageChecks.Sha256Bytes(ids), HasDeviceId = hasIds
            };
        }
        public void AssertIdentity(int number, long size, int logical, int physical, string descriptorHash, string idHash)
        {
            DiskIdentity current = InspectHandle();
            if (current.Number != number || current.Size != size || current.LogicalSectorSize != logical || current.PhysicalSectorSize != physical ||
                current.BusType != 7 || !String.Equals(current.DescriptorSha256, descriptorHash, StringComparison.Ordinal) ||
                !String.Equals(current.DeviceIdSha256, idHash, StringComparison.Ordinal)) throw new IOException("Retained handle identity does not match the approved plan. No retargeting is attempted.");
        }
        private ulong Attributes()
        {
            byte[] attributes = Win32.Query(Handle, Win32.DiskGetAttributes, null, 16);
            if (attributes.Length < 16) throw new IOException("Cannot confirm disk attributes.");
            return BitConverter.ToUInt64(attributes, 8);
        }
        public bool IsOffline { get { return (Attributes() & 1UL) != 0; } }
        public void BeginExclusive(string[] expectedVolumes, int[] protectedDiskNumbers)
        {
            if (!Writable || Exclusive) throw new InvalidOperationException("A new writable session is required.");
            foreach (int number in protectedDiskNumbers) if (number == Identity.Number) throw new IOException("Protected source/system disk.");
            if ((Attributes() & 3UL) != 0) throw new IOException("Target must start online and writable so its mounted labels can be validated.");
            AssertIdentity(Identity.Number, Identity.Size, Identity.LogicalSectorSize, Identity.PhysicalSectorSize, Identity.DescriptorSha256, Identity.DeviceIdSha256);
            string[] beforeNames = WindowsStorage.VolumeNames();
            List<VolumeIdentity> targets = new List<VolumeIdentity>();
            foreach (VolumeIdentity volume in WindowsStorage.Volumes()) {
                if (!volume.ExtentsKnown || !String.IsNullOrEmpty(volume.Error)) throw new IOException("Volume inventory is incomplete: " + volume.Name);
                if (Array.IndexOf(volume.DiskNumbers, Identity.Number) < 0) continue;
                if (volume.DiskNumbers.Length != 1 || !volume.LabelKnown || WindowsStorage.IsProtectedVolume(volume)) throw new IOException("Target volume is protected, unreadable or spans disks.");
                targets.Add(volume);
            }
            List<string> names = new List<string>(); foreach (VolumeIdentity volume in targets) names.Add(volume.Name);
            names.Sort(StringComparer.OrdinalIgnoreCase);
            string[] approved = (string[])expectedVolumes.Clone(); Array.Sort(approved, StringComparer.OrdinalIgnoreCase);
            if (String.Join("\n", names.ToArray()) != String.Join("\n", approved)) throw new IOException("Target volume set changed after planning.");
            foreach (VolumeIdentity volume in targets) {
                SafeFileHandle lockHandle = Win32.Open(volume.Name.TrimEnd('\\'), Win32.GenericRead | Win32.GenericWrite, 0);
                try {
                    int[] extents = WindowsStorage.Extents(lockHandle);
                    if (extents.Length != 1 || extents[0] != Identity.Number) throw new IOException("Volume moved to a different physical device.");
                    Win32.Control(lockHandle, Win32.LockVolume, null);
                    Locks.Add(lockHandle); // The successful lock remains held through verification and disposal.
                    Win32.Control(lockHandle, Win32.DismountVolume, null);
                } catch { if (!Locks.Contains(lockHandle)) lockHandle.Dispose(); throw; }
            }
            if (String.Join("\n", beforeNames) != String.Join("\n", WindowsStorage.VolumeNames())) throw new IOException("Volume enumeration changed during exclusive preparation. Re-plan.");
            AssertIdentity(Identity.Number, Identity.Size, Identity.LogicalSectorSize, Identity.PhysicalSectorSize, Identity.DescriptorSha256, Identity.DeviceIdSha256);
            byte[] offline = new byte[40];
            Buffer.BlockCopy(BitConverter.GetBytes(40U), 0, offline, 0, 4);
            offline[4] = 1; // Persist only this external target's offline state; never bring it online automatically.
            Buffer.BlockCopy(BitConverter.GetBytes(1UL), 0, offline, 8, 8);
            Buffer.BlockCopy(BitConverter.GetBytes(1UL), 0, offline, 16, 8);
            Win32.Control(Handle, Win32.DiskSetAttributes, offline);
            OfflineSet = true;
            if (!IsOffline) throw new IOException("Cannot confirm target is offline.");
            Exclusive = true;
        }
        private void Seek(long position)
        {
            if (position < 0 || position > Identity.Size || position % 512 != 0) throw new IOException("Unaligned or out-of-bounds disk offset.");
            long actual;
            if (!Win32.SetFilePointerEx(Handle, position, out actual, 0) || actual != position) throw Win32.Error("Cannot seek retained disk handle.");
        }
        private sealed class AlignedBuffer : IDisposable
        {
            private IntPtr Allocation;
            internal readonly IntPtr Pointer;
            internal AlignedBuffer(int length)
            {
                Allocation = Marshal.AllocHGlobal(length + 65536);
                Pointer = new IntPtr((Allocation.ToInt64() + 65535L) & ~65535L);
            }
            public void Dispose() { if (Allocation != IntPtr.Zero) { Marshal.FreeHGlobal(Allocation); Allocation = IntPtr.Zero; } }
        }
        private void Read(AlignedBuffer buffer, int count)
        {
            uint actual;
            if (count % 512 != 0 || !Win32.ReadFile(Handle, buffer.Pointer, (uint)count, out actual, IntPtr.Zero)) throw Win32.Error("Physical-disk read failed.");
            if (actual != count) throw new IOException("Short physical-disk read; verification stopped.");
        }
        private void Write(AlignedBuffer buffer, int count)
        {
            if (!Writable || !Exclusive || !IsOffline) throw new IOException("Exclusive offline state is not confirmed.");
            uint actual;
            if (count % 512 != 0 || !Win32.WriteFile(Handle, buffer.Pointer, (uint)count, out actual, IntPtr.Zero)) throw Win32.Error("Physical-disk write failed; target may be incomplete.");
            if (actual != count) throw new IOException("Short physical-disk write; target is incomplete.");
        }
        private static void Notify(Action<TransferProgress> callback, string phase, long done, long total, ref DateTime last)
        {
            if (callback != null && ((DateTime.UtcNow - last).TotalMilliseconds >= 250 || done == total)) {
                callback(new TransferProgress { Phase = phase, Completed = done, Total = total }); last = DateTime.UtcNow;
            }
        }
        private string HashPrefix(long bytes, Action<TransferProgress> progress)
        {
            if (bytes <= 0 || bytes > Identity.Size || bytes % 512 != 0) throw new IOException("Invalid verify bounds.");
            Seek(0); long done = 0; byte[] managed = new byte[4 * 1024 * 1024]; DateTime last = DateTime.MinValue;
            using (AlignedBuffer buffer = new AlignedBuffer(managed.Length))
            using (SHA256 sha = SHA256.Create()) {
                while (done < bytes) {
                    int take = (int)Math.Min(managed.Length, bytes - done); Read(buffer, take); Marshal.Copy(buffer.Pointer, managed, 0, take);
                    sha.TransformBlock(managed, 0, take, managed, 0); done += take; Notify(progress, "verify-image", done, bytes, ref last);
                }
                sha.TransformFinalBlock(new byte[0], 0, 0); return ImageChecks.Hex(sha.Hash);
            }
        }
        private void CheckTailBounds(long imageBytes, long offset, long bytes)
        {
            if (bytes == 0) { if (offset != 0 || Identity.Size != imageBytes) throw new IOException("Only exact-sized targets may omit tail clearing."); return; }
            if (bytes != 1048576 || offset != Identity.Size - bytes || offset < imageBytes || offset % 512 != 0) throw new IOException("Tail must be the last 1 MiB wholly outside the image.");
        }
        private void VerifyTail(long offset, long bytes, Action<TransferProgress> progress)
        {
            if (bytes == 0) return;
            Seek(offset);
            using (AlignedBuffer buffer = new AlignedBuffer((int)bytes)) {
                Read(buffer, (int)bytes); byte[] data = new byte[bytes]; Marshal.Copy(buffer.Pointer, data, 0, data.Length);
                foreach (byte value in data) if (value != 0) throw new IOException("Stale-GPT tail clearing failed readback.");
            }
            if (progress != null) progress(new TransferProgress { Phase = "verify-tail", Completed = bytes, Total = bytes });
        }
        public VerificationResult Verify(long imageBytes, string expectedHash, long tailOffset, long tailBytes, Action<TransferProgress> progress)
        {
            CheckTailBounds(imageBytes, tailOffset, tailBytes);
            AssertIdentity(Identity.Number, Identity.Size, Identity.LogicalSectorSize, Identity.PhysicalSectorSize, Identity.DescriptorSha256, Identity.DeviceIdSha256);
            string actual = HashPrefix(imageBytes, progress);
            if (!String.Equals(actual, expectedHash, StringComparison.Ordinal)) throw new IOException("Full written-image SHA-256 does not match. Target is not verified.");
            VerifyTail(tailOffset, tailBytes, progress);
            return new VerificationResult { ImageSha256 = actual, ImageBytesVerified = imageBytes, TailBytesVerified = tailBytes, Offline = IsOffline };
        }
        public VerificationResult WriteVerified(ImageFile source, long tailOffset, long tailBytes, Action<TransferProgress> progress)
        {
            if (source == null || !Writable || !Exclusive || !IsOffline) throw new IOException("Authorized exclusive session and a pinned source are required.");
            long imageBytes = source.Layout.ImageBytes;
            CheckTailBounds(imageBytes, tailOffset, tailBytes);
            foreach (int number in WindowsStorage.HandleDiskNumbers(source.Handle)) if (number == Identity.Number) throw new IOException("The opened image is stored on the target.");
            AssertIdentity(Identity.Number, Identity.Size, Identity.LogicalSectorSize, Identity.PhysicalSectorSize, Identity.DescriptorSha256, Identity.DeviceIdSha256);
            source.Stream.Position = 0; Seek(0); byte[] managed = new byte[4 * 1024 * 1024]; DateTime last = DateTime.MinValue;
            using (AlignedBuffer buffer = new AlignedBuffer(managed.Length)) {
                while (ImageBytesWritten < imageBytes) {
                    int wanted = (int)Math.Min(managed.Length, imageBytes - ImageBytesWritten), have = 0;
                    while (have < wanted) { int read = source.Stream.Read(managed, have, wanted - have); if (read <= 0) throw new EndOfStreamException("Pinned source truncated."); have += read; }
                    Marshal.Copy(managed, 0, buffer.Pointer, wanted);
                    ImageWriteStarted = true; Write(buffer, wanted); ImageBytesWritten += wanted;
                    Notify(progress, "write-image", ImageBytesWritten, imageBytes, ref last);
                }
                if (!Win32.FlushFileBuffers(Handle)) throw Win32.Error("Disk flush failed; write is not verified.");
                string writtenHash = HashPrefix(imageBytes, progress);
                if (!String.Equals(writtenHash, source.Sha256, StringComparison.Ordinal)) throw new IOException("Full image readback SHA-256 mismatch.");
                if (tailBytes > 0) {
                    Seek(tailOffset); Array.Clear(managed, 0, managed.Length); Marshal.Copy(managed, 0, buffer.Pointer, (int)tailBytes);
                    TailWriteStarted = true; Write(buffer, (int)tailBytes);
                    if (!Win32.FlushFileBuffers(Handle)) throw Win32.Error("Tail flush failed.");
                    VerifyTail(tailOffset, tailBytes, progress);
                }
                if (!IsOffline) throw new IOException("Target unexpectedly returned online.");
                return new VerificationResult { ImageSha256 = writtenHash, ImageBytesVerified = imageBytes, TailBytesVerified = tailBytes, Offline = true };
            }
        }
        public void Dispose()
        {
            // Deliberately no Set-Disk, drive-number reopening, online transition or automatic recovery write.
            foreach (SafeFileHandle volume in Locks) volume.Dispose();
            Locks.Clear();
            if (Handle != null) { Handle.Dispose(); Handle = null; }
        }
    }
}
