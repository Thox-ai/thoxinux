// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 THOX.ai LLC.
// C# 5-compatible, pure file/stream image validation. No device APIs.
using System;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Thox.ExternalSsd
{
    public static class SafeFileOperations
    {
        public static void ReplaceExisting(string source, string destination)
        {
            // Preserve a real CLR null; PowerShell may coerce $null to an empty path.
            File.Replace(source, destination, null);
        }
    }

    public sealed class TransferProgress
    {
        public string Phase { get; set; }
        public long Completed { get; set; }
        public long Total { get; set; }
    }

    public sealed class ImageLayout
    {
        public long ImageBytes { get; set; }
        public string DiskGuid { get; set; }
        public long EspOffset { get; set; }
        public long RootOffset { get; set; }
        public string BootFile { get; set; }
        public string ValidationScope { get { return "GPT CRCs and bounds, FAT32 fallback x64 PE header, Linux filesystem superblock; not a boot test or signature attestation"; } }
    }

    public static class ImageChecks
    {
        private const int Sector = 512;
        private static readonly uint[] CrcTable = CreateCrcTable();
        private static readonly Guid EspType = new Guid("c12a7328-f81f-11d2-ba4b-00a0c93ec93b");
        private static readonly Guid LinuxType = new Guid("0fc63daf-8483-4772-8e79-3d69d8477de4");
        private static readonly Guid LinuxRootX64 = new Guid("4f68bce3-e8cd-4db1-96e7-fbcaf984b709");

        private static uint[] CreateCrcTable()
        {
            uint[] table = new uint[256];
            for (uint n = 0; n < 256; n++) {
                uint c = n;
                for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xedb88320U ^ (c >> 1) : c >> 1;
                table[n] = c;
            }
            return table;
        }
        public static uint Crc32(byte[] bytes)
        {
            uint c = 0xffffffffU;
            foreach (byte b in bytes) c = CrcTable[(c ^ b) & 0xff] ^ (c >> 8);
            return c ^ 0xffffffffU;
        }
        public static string Hex(byte[] value) { return BitConverter.ToString(value).Replace("-", "").ToLowerInvariant(); }
        public static string Sha256Bytes(byte[] bytes) { using (SHA256 sha = SHA256.Create()) return Hex(sha.ComputeHash(bytes)); }
        private static byte[] ReadAt(Stream stream, long offset, int count)
        {
            if (!stream.CanRead || !stream.CanSeek || offset < 0 || count < 0 || offset > stream.Length - count) throw new InvalidDataException("Image read is outside its bounds.");
            stream.Position = offset;
            byte[] result = new byte[count];
            int total = 0;
            while (total < count) {
                int read = stream.Read(result, total, count - total);
                if (read == 0) throw new EndOfStreamException("Truncated image.");
                total += read;
            }
            return result;
        }
        private static ulong U64(byte[] b, int at) { return BitConverter.ToUInt64(b, at); }
        private static uint U32(byte[] b, int at) { return BitConverter.ToUInt32(b, at); }
        private static ushort U16(byte[] b, int at) { return BitConverter.ToUInt16(b, at); }
        private static Guid G(byte[] b, int at) { byte[] value = new byte[16]; Buffer.BlockCopy(b, at, value, 0, 16); return new Guid(value); }
        private static bool Same(byte[] a, byte[] b) {
            if (a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
            return true;
        }
        private static long ByteOffset(ulong lba, long length) {
            if (lba > (ulong)(length / Sector)) throw new InvalidDataException("GPT sector is outside the image.");
            return checked((long)lba * Sector);
        }
        private static byte[] Header(Stream stream, long offset, ulong expectedLba, ulong alternateLba)
        {
            byte[] h = ReadAt(stream, offset, Sector);
            if (Encoding.ASCII.GetString(h, 0, 8) != "EFI PART" || U32(h, 8) != 0x00010000 || U32(h, 20) != 0) throw new InvalidDataException("Expected a GPT v1 header.");
            uint size = U32(h, 12);
            if (size < 92 || size > Sector) throw new InvalidDataException("Invalid GPT header length.");
            byte[] crcInput = new byte[size]; Buffer.BlockCopy(h, 0, crcInput, 0, (int)size);
            Array.Clear(crcInput, 16, 4);
            if (Crc32(crcInput) != U32(h, 16)) throw new InvalidDataException("GPT header CRC mismatch.");
            if (U64(h, 24) != expectedLba || U64(h, 32) != alternateLba) throw new InvalidDataException("GPT primary/backup placement does not match the exact image length.");
            if (G(h, 56) == Guid.Empty) throw new InvalidDataException("Missing GPT disk GUID.");
            return h;
        }
        private sealed class Partition { public Guid Type; public ulong First; public ulong Last; }

        public static ImageLayout Inspect(Stream stream, long expectedBytes)
        {
            if (expectedBytes < 8388608 || expectedBytes % Sector != 0 || stream.Length != expectedBytes) throw new InvalidDataException("Image length is wrong or unaligned.");
            byte[] mbr = ReadAt(stream, 0, Sector);
            if (mbr[510] != 0x55 || mbr[511] != 0xaa) throw new InvalidDataException("Missing protective MBR signature.");
            int protective = 0;
            for (int i = 0; i < 4; i++) {
                byte type = mbr[446 + i * 16 + 4];
                if (type == 0xee) {
                    protective++;
                    uint expectedSectors = (uint)Math.Min((ulong)(expectedBytes / Sector - 1), (ulong)UInt32.MaxValue);
                    if (U32(mbr, 446 + i * 16 + 8) != 1 || U32(mbr, 446 + i * 16 + 12) != expectedSectors) throw new InvalidDataException("Protective MBR extent does not cover the image.");
                }
                else if (type != 0) throw new InvalidDataException("Hybrid MBR images are not accepted.");
            }
            if (protective != 1) throw new InvalidDataException("Expected a single protective MBR entry.");
            // Explicitly reject ISO9660 hybrid installer media.
            byte[] iso = ReadAt(stream, 32769, 5);
            if (Encoding.ASCII.GetString(iso) == "CD001") throw new InvalidDataException("ISO/live installer media are not persistent installed-system images.");
            ulong lastLba = (ulong)(expectedBytes / Sector - 1);
            byte[] primary = Header(stream, Sector, 1, lastLba);
            byte[] backup = Header(stream, expectedBytes - Sector, lastLba, 1);
            uint count = U32(primary, 80), entrySize = U32(primary, 84);
            if (count == 0 || count > 128 || entrySize != 128 || U64(primary, 72) != 2) throw new InvalidDataException("Unsupported GPT entry layout.");
            int tableBytes = checked((int)(count * entrySize));
            long tableSectors = (tableBytes + Sector - 1) / Sector;
            if (U64(backup, 72) != lastLba - (ulong)tableSectors || U32(backup, 80) != count || U32(backup, 84) != entrySize || G(primary, 56) != G(backup, 56)) throw new InvalidDataException("Primary and backup GPT metadata differ.");
            ulong firstUsable = U64(primary, 40), lastUsable = U64(primary, 48);
            if (firstUsable < (ulong)(2 + tableSectors) || lastUsable >= lastLba - (ulong)tableSectors || firstUsable >= lastUsable || U64(backup, 40) != firstUsable || U64(backup, 48) != lastUsable) throw new InvalidDataException("Invalid GPT usable-sector bounds.");
            byte[] entries = ReadAt(stream, 2 * Sector, tableBytes);
            byte[] backupEntries = ReadAt(stream, ByteOffset(U64(backup, 72), expectedBytes), tableBytes);
            if (Crc32(entries) != U32(primary, 88) || Crc32(backupEntries) != U32(backup, 88) || !Same(entries, backupEntries)) throw new InvalidDataException("GPT partition-array CRC or copy mismatch.");
            List<Partition> partitions = new List<Partition>(); HashSet<Guid> partitionIds = new HashSet<Guid>();
            Partition esp = null, root = null;
            for (int at = 0; at < tableBytes; at += 128) {
                Guid type = G(entries, at);
                if (type == Guid.Empty) continue;
                Partition p = new Partition { Type = type, First = U64(entries, at + 32), Last = U64(entries, at + 40) };
                Guid partitionId = G(entries, at + 16);
                if (partitionId == Guid.Empty || !partitionIds.Add(partitionId) || p.First < firstUsable || p.Last > lastUsable || p.Last < p.First) throw new InvalidDataException("Invalid or duplicated partition identity or extent.");
                foreach (Partition other in partitions) if (!(p.Last < other.First || p.First > other.Last)) throw new InvalidDataException("Overlapping partitions.");
                partitions.Add(p);
                if (type == EspType) { if (esp != null) throw new InvalidDataException("More than one EFI system partition."); esp = p; }
                if (type == LinuxType || type == LinuxRootX64) { if (root != null) throw new InvalidDataException("This writer requires exactly one Linux root candidate."); root = p; }
            }
            if (esp == null || root == null || partitions.Count != 2) throw new InvalidDataException("Exactly two partitions are required: an EFI system partition and a persistent Linux root.");
            long espStart = ByteOffset(esp.First, expectedBytes), rootStart = ByteOffset(root.First, expectedBytes);
            byte[] super = ReadAt(stream, rootStart + 1024, 1024);
            if (U16(super, 56) != 0xef53) throw new InvalidDataException("Linux root lacks the expected ext filesystem superblock.");
            uint logBlockSize = U32(super, 24);
            if (logBlockSize > 6) throw new InvalidDataException("Unsupported Linux filesystem block size.");
            ulong blocks = U32(super, 4);
            if ((U32(super, 96) & 0x80U) != 0) blocks |= (ulong)U32(super, 336) << 32;
            ulong blockBytes = 1024UL << (int)logBlockSize;
            ulong rootBytes = checked((root.Last - root.First + 1) * Sector);
            if (blocks == 0 || blocks > rootBytes / blockBytes) throw new InvalidDataException("Declared Linux filesystem extends outside the root partition.");
            Fat32 fat = new Fat32(stream, espStart, checked((long)(esp.Last - esp.First + 1) * Sector));
            byte[] pe = fat.ReadFallback();
            if (pe.Length < 64 || pe[0] != 'M' || pe[1] != 'Z') throw new InvalidDataException("UEFI fallback is not a PE image.");
            uint peAt = U32(pe, 60);
            if (peAt > pe.Length - 94 || peAt < 64 || pe[peAt] != 'P' || pe[peAt + 1] != 'E' || pe[peAt + 2] != 0 || pe[peAt + 3] != 0 || U16(pe, (int)peAt + 4) != 0x8664 ||
                U16(pe, (int)peAt + 20) < 112 || U16(pe, (int)peAt + 24) != 0x20b || U16(pe, (int)peAt + 92) != 10) throw new InvalidDataException("Fallback bootloader is not an x86-64 PE32+ EFI application.");
            return new ImageLayout { ImageBytes = expectedBytes, DiskGuid = G(primary, 56).ToString(), EspOffset = espStart, RootOffset = rootStart, BootFile = "EFI/BOOT/BOOTX64.EFI" };
        }

        private sealed class Fat32
        {
            private readonly Stream Stream;
            private readonly long Start, Length, DataStart, FatStart;
            private readonly uint Root, ClusterCount;
            private readonly int ClusterBytes;
            private sealed class Entry { public uint Cluster; public uint Size; public bool Directory; }
            public Fat32(Stream stream, long start, long length)
            {
                Stream = stream; Start = start; Length = length;
                byte[] b = ReadAt(stream, start, Sector);
                int sectorsPerCluster = b[13], fats = b[16]; ushort reserved = U16(b, 14);
                uint sectors = U32(b, 32), fatSectors = U32(b, 36);
                if (U16(b, 11) != Sector || sectorsPerCluster < 1 || sectorsPerCluster > 128 || (sectorsPerCluster & (sectorsPerCluster - 1)) != 0 || reserved == 0 || fats < 1 || fats > 2 || fatSectors == 0 || U16(b, 17) != 0 || b[510] != 0x55 || b[511] != 0xaa) throw new InvalidDataException("Unsupported EFI FAT32 filesystem.");
                long overhead = reserved + (long)fats * fatSectors;
                if (sectors <= overhead || (long)sectors * Sector > length) throw new InvalidDataException("EFI FAT32 geometry leaves its partition.");
                ClusterBytes = sectorsPerCluster * Sector;
                ClusterCount = (uint)((sectors - overhead) / sectorsPerCluster);
                if ((long)fatSectors * Sector < ((long)ClusterCount + 2) * 4) throw new InvalidDataException("EFI FAT is too small.");
                Root = U32(b, 44);
                FatStart = start + reserved * Sector; DataStart = start + overhead * Sector;
                CheckCluster(Root);
            }
            private void CheckCluster(uint cluster) { if (cluster < 2 || cluster >= ClusterCount + 2) throw new InvalidDataException("Invalid EFI cluster."); }
            private long ClusterAt(uint cluster) { CheckCluster(cluster); long at = DataStart + ((long)cluster - 2) * ClusterBytes; if (at > Start + Length - ClusterBytes) throw new InvalidDataException("EFI cluster outside partition."); return at; }
            private uint Next(uint cluster) { uint next = U32(ReadAt(Stream, FatStart + (long)cluster * 4, 4), 0) & 0x0fffffff; if (next >= 0x0ffffff8) return 0; CheckCluster(next); return next; }
            private Entry Find(uint directory, string name)
            {
                HashSet<uint> visited = new HashSet<uint>();
                uint cluster = directory;
                while (cluster != 0) {
                    if (!visited.Add(cluster) || visited.Count > 4096) throw new InvalidDataException("Cyclic or excessive EFI directory chain.");
                    byte[] data = ReadAt(Stream, ClusterAt(cluster), ClusterBytes);
                    for (int at = 0; at < data.Length; at += 32) {
                        if (data[at] == 0) throw new InvalidDataException("Required EFI fallback path is absent: " + name);
                        if (data[at] == 0xe5 || (data[at + 11] & 0x0f) == 0x0f || (data[at + 11] & 8) != 0) continue;
                        string stem = Encoding.ASCII.GetString(data, at, 8).TrimEnd();
                        string ext = Encoding.ASCII.GetString(data, at + 8, 3).TrimEnd();
                        string actual = ext.Length == 0 ? stem : stem + "." + ext;
                        if (String.Equals(actual, name, StringComparison.OrdinalIgnoreCase)) {
                            uint child = ((uint)U16(data, at + 20) << 16) | U16(data, at + 26);
                            CheckCluster(child);
                            return new Entry { Cluster = child, Size = U32(data, at + 28), Directory = (data[at + 11] & 0x10) != 0 };
                        }
                    }
                    cluster = Next(cluster);
                }
                throw new InvalidDataException("Required EFI fallback path is absent: " + name);
            }
            public byte[] ReadFallback()
            {
                Entry efi = Find(Root, "EFI"); if (!efi.Directory) throw new InvalidDataException("EFI path is not a directory.");
                Entry boot = Find(efi.Cluster, "BOOT"); if (!boot.Directory) throw new InvalidDataException("BOOT path is not a directory.");
                Entry file = Find(boot.Cluster, "BOOTX64.EFI"); if (file.Directory || file.Size < 64) throw new InvalidDataException("Invalid fallback file.");
                int wanted = (int)Math.Min(file.Size, 1048576U); byte[] output = new byte[wanted]; int done = 0; uint cluster = file.Cluster;
                HashSet<uint> visited = new HashSet<uint>();
                while (done < wanted) {
                    if (cluster == 0 || !visited.Add(cluster)) throw new InvalidDataException("Truncated or cyclic fallback file.");
                    int take = Math.Min(ClusterBytes, wanted - done);
                    byte[] data = ReadAt(Stream, ClusterAt(cluster), take); Buffer.BlockCopy(data, 0, output, done, take); done += take;
                    if (done < wanted) cluster = Next(cluster);
                }
                return output;
            }
        }

        public static string HashStream(Stream stream, long count, Action<TransferProgress> progress, string phase)
        {
            if (count < 0 || !stream.CanSeek || stream.Length != count) throw new InvalidDataException("Source length changed.");
            stream.Position = 0;
            byte[] buffer = new byte[4 * 1024 * 1024]; long done = 0; DateTime last = DateTime.MinValue;
            using (SHA256 sha = SHA256.Create()) {
                while (done < count) {
                    int read = stream.Read(buffer, 0, (int)Math.Min(buffer.Length, count - done));
                    if (read <= 0) throw new EndOfStreamException("Source truncated during hashing.");
                    sha.TransformBlock(buffer, 0, read, buffer, 0); done += read;
                    if (progress != null && ((DateTime.UtcNow - last).TotalMilliseconds >= 250 || done == count)) { progress(new TransferProgress { Phase = phase, Completed = done, Total = count }); last = DateTime.UtcNow; }
                }
                sha.TransformFinalBlock(new byte[0], 0, 0);
                stream.Position = 0; return Hex(sha.Hash);
            }
        }
    }

    public sealed class ImageFile : IDisposable
    {
        internal FileStream Stream;
        public string Path { get; private set; }
        public string Sha256 { get; private set; }
        public ImageLayout Layout { get; private set; }
        public Microsoft.Win32.SafeHandles.SafeFileHandle Handle { get { return Stream.SafeFileHandle; } }
        public static ImageFile Open(string path, long expectedBytes, string expectedSha256, Action<TransferProgress> progress)
        {
            ImageFile file = new ImageFile();
            try {
                file.Path = System.IO.Path.GetFullPath(path);
                // Deny concurrent writes and replacement for the complete validate/write lifetime.
                file.Stream = new FileStream(file.Path, FileMode.Open, FileAccess.Read, FileShare.Read, 1048576, FileOptions.SequentialScan);
                file.Layout = ImageChecks.Inspect(file.Stream, expectedBytes);
                file.Sha256 = ImageChecks.HashStream(file.Stream, expectedBytes, progress, "hash-source");
                if (!String.Equals(file.Sha256, expectedSha256, StringComparison.Ordinal)) throw new InvalidDataException("Full image SHA-256 does not match the pinned manifest.");
                return file;
            } catch { file.Dispose(); throw; }
        }
        public void Dispose() { if (Stream != null) { Stream.Dispose(); Stream = null; } }
    }
}
