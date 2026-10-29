# External SSD build and boot path for KnightHub

KnightHub's target profile is Intel i7-14700F, NVIDIA RTX 4060 Ti 16 GB and
approximately 126 GiB reported system RAM. Installed RAM is measured by the
preflight; earlier 126/128 GB descriptions are not treated as a hardware receipt.

The working architecture is Linux on the external SSD, the existing ThoxOS
desktop above Linux, and an isolated Ginux research guest launched by QEMU.
Ginux's validated target is a virtual Q35/OVMF/virtio platform. Its current source
does not establish USB storage, NVMe, NVIDIA or the complete physical KnightHub
hardware path. A native Ginux EFI copied onto an SSD is not a qualified desktop
installation.

## Preserve existing source ownership

This module belongs under `ports/ginux/` in `ttracx/thoxos-desktop-debian`, next
to the isolated `ports/nicecore/` port. Design authority remains that repository.
The established OS implementation remains in `ttracx/thoxos-vibe-rust`.

Source review checkpoint:

| Source | Exact revision | Observed state |
|---|---|---|
| `thoxos-desktop-debian` main | `1385e9780fea4023f8e73b897ce8140d3dae3d96` | Adopted desktop design and isolated NiceC0re port |
| `thoxos-vibe-rust` main | `e912d82ad9d8e3475a945039b5f16228c9a4bf56` | Existing Linux host image implementation |
| Active offline desktop branch | `c93503fb43cac190a4b980adaed21ca274c4d0b2` | `fix/offline-dualboot-knighthub-20261025`; preserve its owner |
| `thoxos-release-kit` main | `17efef076e7913d6404878d0fda82c027c098c6b` | Ordinary-file preparation, independently pinned artifacts |

These snapshots are source observations. They do not grant a new release,
prove a rebuilt image or supersede existing holds. Internal shipping coordination
remains with the existing repository owners and `thox-ship-tracker` coordinator.

## Build the existing Linux host

Use an authorized x86-64 Linux or KnightHub Docker runner with at least the
existing pipeline's 125 GiB free-space threshold. Windows source, cache and
artifacts remain on V:, and V: must never be the imaging target. On Windows,
run the following in Git Bash from an existing approved V: source directory:

```bash
git clone https://github.com/ttracx/thoxos-vibe-rust.git
python3 ssd-module/build_external_ssd.py \
  --source ./thoxos-vibe-rust \
  --worktree V:/dev/thoxos-ginux-host-build \
  --kit ./module-ginux \
  --expected-receipt-sha256 '<authenticated build-receipt SHA-256>' \
  --out V:/thox-release-artifacts/ginux-host \
  --build
```

Use new worktree and output directory names; existing work is preserved.
On Linux, use absolute source/worktree/output paths on the approved build volume
in place of the V: paths. Omit `--build` to prepare and inspect the candidate
source without starting containers. On Windows installations that provide only
`python`, substitute that Python 3 executable for `python3`.

The wrapper verifies the host commit and four reviewed Git blobs, creates a
separate detached local checkout, stages the verified Ginux payload and terminal
launcher in the desktop overlay, and adds QEMU/OVMF packages to its package
configuration. It then runs the required workspace tests and existing image
builder, retaining each command's exit code and log. The candidate receipt
contains exact overlay hashes. The source clone's current branch and dirty work
are not overwritten. Its Git database is self-contained inside the builder's
read-only source mount, so the existing artifact program can read the base
commit. The original image layout is retained.

The existing pipeline runs privileged **build containers**, not a physical disk
installer. Its inputs include distribution repositories, so this is a
pinned-source workflow, not a promise of byte-for-byte reproducible output.
Retain the image, integration receipt, source revision, package versions,
build logs and hashes. A successful build remains an unaccepted candidate.

Run the existing image VM review at the exact shipping source, retaining its
service/greeter/session, offline and persistence results:

```bash
bash V:/dev/thoxos-ginux-host-build/image/vm/loop.sh \
  --variant x86_64-dual \
  --artifact-dir V:/thox-release-artifacts/ginux-host \
  --skip-build
```

Run the VM harness on its supported Linux/WSL runner, translating those paths
to `/mnt/v/...` where required. The wrapper also accepts `--run-vm-gate` with
`--build` on a compatible runner; it never skips the harness's review stage.

The source's failed readiness record and historical firmware-banner stub
releases remain historical. A successful build command cannot close a failed
runtime gate. An image from this separate build must not be passed to a writer
that admits only another exact image identity.

## Use the existing guarded Windows writer

Do not implement a second disk writer. The existing NiceC0re external SSD
workflow is pinned here for source review:

- [Windows installation guide at the reviewed source](https://github.com/ttracx/thoxos-desktop-debian/blob/1385e9780fea4023f8e73b897ce8140d3dae3d96/ports/nicecore/external-ssd/INSTALL_WINDOWS.md)
- [Writer and admission source directory](https://github.com/ttracx/thoxos-desktop-debian/tree/1385e9780fea4023f8e73b897ce8140d3dae3d96/ports/nicecore/external-ssd)

Obtain its final accepted image, matching manifest and verified kit from its
owning lane before executing a media write. That source checkpoint references
a 24 GiB candidate but still marks fresh shipping-image acceptance pending.
The referenced final native acceptance file is absent at this revision. This
package does not fill that evidence gap or turn its raw-image hash into approval.

The unchanged writer source is bundled in `vendor/windows-writer/`. Its
`SOURCE-MANIFEST.json` binds all nine original files to Git blobs and SHA-256,
and the original readme, source/API record and Apache-2.0 license are retained.
Vendoring is source reuse, not native Windows execution or new-image admission.

**The build wrapper retains Vibe's dual-architecture btrfs layout. The bundled
NiceC0re writer admits exactly two GPT partitions and an ext root filesystem.
They are not currently a matched image/writer pair.** Use the postboot module
installer with an existing accepted Linux SSD, or have the owning build/writer
lane qualify the newly generated layout and exact image. Do not bypass the
writer's structural refusal. No complete fresh-media install is claimed by
combining these two independent source components.

Once the owning lane supplies a matched accepted kit, follow its exact guide. The workflow
starts with read-only mapping and inventory:

```powershell
.\Inspect-D-Drive.ps1
.\thox-external-ssd.ps1 inventory -Json
```

D: is a volume letter, not a physical target identity. The existing writer
requires a matching payload manifest hash, exact disk UniqueId, serial and byte
capacity, an eligible plan, preview, target-specific erase confirmation and full
write/readback verification. It refuses system, internal, protected and ambiguous
disks. Preserve those refusals. Do not copy its hash overrides, remove checks or
reuse an old plan for a different image or re-enumerated target.

After verified media preparation, use the machine's one-time UEFI boot menu and
choose the external SSD. Preserve Windows Boot Manager and the original firmware
settings. The owner must retain the Windows recovery key before firmware changes;
never put it in this kit or an uploaded report. Secure Boot signing is not claimed.

Create the local account through the existing host's first-boot workflow, then
run this module's preflight and installer from that SSD. `--require-usb-root`
refuses ordinary host installation when USB nonrotational root ancestry cannot
be established. Native Thunderbolt/NVMe enclosures may need a separately reviewed
storage path; do not weaken this check to label an unverified disk external.

## Remaining acceptance

| Gate | Required evidence |
|---|---|
| Linux host build | Exact source, logs, package versions and artifact hashes |
| Host VM | Real boot, local account, desktop, reboot and persistence |
| Physical write | Exact target identity, current plan and complete readback |
| KnightHub boot | Real external-SSD UEFI boot, Windows return path and persistence |
| GPU | Native RTX 4060 Ti driver, desktop and separately tested CUDA workload |
| Ginux guest | Exact EFI receipt, actual serial boot, controller and persistence |
| Security | Real Secure Boot state, encryption capability and current update status |

None of these physical results are inferred from source tests, the HTML guide,
the Docker recipe or an unexecuted command. No drive was flashed and no host was
rebooted by this integration module.
