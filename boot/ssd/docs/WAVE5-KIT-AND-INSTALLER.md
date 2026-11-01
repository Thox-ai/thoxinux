# Wave 5: payload kit assembly and installer dry-run hardening

Lane C, Wave 5 items 3 and 7. Host: KnightHub (WSL2, Ubuntu 26.04,
x86-64, Docker up, /dev/kvm present). Date: 2026-10-31
(America/Chicago). Safety: no physical disk was written at any point.
All targets were ordinary image files, disposable directories or loop
devices backed by files in scratch space. Writer refusal guards were
not modified.

**Your AI. Your Data. Your Rules.™**

## Item 3: the payload kit format

The kit format is defined by `install_host.verify_kit` in `boot/ssd/`
and consumed by both `install_host.install` and
`build_external_ssd.prepare`. A valid kit is a directory (conventional
name `module-ginux`) holding:

| Path | Requirement |
|---|---|
| `artifacts/GINUX.EFI` | Regular file, not a symlink, starts with the PE magic `MZ` |
| `artifacts/GINUX_LICENSE` | Regular file, non-empty upstream license text |
| `artifacts/GINUX_NOTICE` | Regular file, non-empty upstream notice text |
| `artifacts/build-receipt.json` | Regular file; its SHA-256 must equal the expected receipt hash given on the command line; its `artifacts` map must bind the EFI, license and notice hashes exactly |
| `artifacts/SHA256SUMS` | One `<sha256>  <name>` line per artifact, covering all four artifacts exactly, no duplicates, no path separators in names |
| `scripts/run-vm.sh` | Regular file, not a symlink, first bytes `#!` |

Nothing else is required by the format. In particular the kit does not
carry a kernel source tree, a userspace image or an edition payload:
the userspace side of `build_external_ssd.py` comes from the pinned
host source it clones (see below), and the Ginux guest enters that
image as the staged overlay files under `opt/thox/ginux`. The kit
recorded in `boot/ssd/evidence/actual-payload-staging.json` (receipt
SHA-256 `182dedf18e3e91468ef58f455010d8dfdf6920ae518b02eb18c8ec8f045b4977`,
EFI SHA-256 `4fd25157b9f0348346a56fcb3e8d51d29414094f0f3aaa533ffddb52932e69e8`)
was staging-only and its destination was removed, so it cannot be
reused.

## Item 3: the assembled kit

Assembled by the new committed script `boot/ssd/assemble_payload_kit.py`
and placed on disk at `/mnt/d/w5-c-kit/module-ginux` (13 MB). The kit
itself is not committed: the EFI alone is 12,507,648 bytes of binary
that is already published as the v0.9.0 release asset, and large
binaries do not go in git. The script plus this record make the kit
reproducible byte for byte except the receipt, which carries its own
assembly timestamp.

Components, each labelled with its source line:

| Component | Source line | SHA-256 |
|---|---|---|
| `artifacts/GINUX.EFI` | unified (Payload U, from `/mnt/d/thoxinux-build/artifacts-u1/`) | `85722bd41426491bf86f810bbdd25f951c53afc49e1bf32ad5b34c63ab4420ae` |
| `artifacts/GINUX_LICENSE` | unified (Payload U artifacts) | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
| `artifacts/GINUX_NOTICE` | unified (Payload U artifacts) | `65efae7eeef0e462670e5e80a2a122f2f5910559f2c73e9e88c53d45414f1bcf` |
| `artifacts/build-receipt.json` | Wave 5 assembly (see note) | `63ce5f2de9ba00d334b2f03252f8772409bd68197bf323990db744668997d2ab` for the kit assembled in this wave |
| `artifacts/SHA256SUMS` | Wave 5 assembly | `1aca2aaaedd10fee6268729922a9234f0b98203d9fc1422884c59b1246640cd7` |
| `scripts/run-vm.sh` | unified (repo `kernel/ginux/scripts/run-vm.sh`) | `c7694116061f7ea5b3d9f4eda416d9eca1410d7568d6560edf2e4617708e91c8` |

Receipt note, stated plainly: no build-time `build-receipt.json`
exists for Payload U. The unified build copied the EFI, then its
receipt step failed on a legacy patch filename
(`write-build-receipt.py` looked for `patches/thox-banner.patch`,
which the unified patch series does not carry; the failure is in the
unified build log). The assembler therefore generates the receipt at
assembly time, in the same `artifacts` binding format the verifier
requires, and the receipt names its own kind as
`wave5-kit-assembly`. It claims no build-time provenance. The
launcher hash is a useful cross-check: it is byte-identical to the
launcher staged in the earlier staging-only kit recorded in
`boot/ssd/evidence`.

Verification: the assembler ends by running the real
`install_host.verify_kit` over the assembled kit; it passed. The
kit was also consumed end to end by `install_host.install` (staging
mode, below) and by `build_external_ssd.prepare` (below).

## Item 3: build_external_ssd.py runs

`build_external_ssd.py` has no physical-device argument. Given
`--source` (a clone of `ttracx/thoxos-vibe-rust`), `--worktree` (a new
directory), `--kit`, `--expected-receipt-sha256` and `--out`, it
verifies the kit, clones the pinned host commit
`e912d82ad9d8e3475a945039b5f16228c9a4bf56` into the worktree, checks
four pinned source blobs, adds the guest packages to the mkosi
configuration, and stages the kit into the image overlay. With
`--build` it then runs, in order, `cargo test --workspace` and
`bash image/build-image.sh --variant x86_64-dual --version
0.1.0-ginux-host --out <out> --min-free-gib 125`; only the second
command produces a `.img` file.

Source used in this wave: a fresh clone of
`https://github.com/ttracx/thoxos-vibe-rust.git`, whose `main` is
exactly the pinned commit `e912d82ad9d8e3475a945039b5f16228c9a4bf56`
(verified with `git ls-remote` and after cloning). The pre-existing
local preview clone does not contain that commit.

### Prepare run: PASS

With source and worktree on WSL-native ext4:

```
python3 build_external_ssd.py \
  --source ~/w5-vibe-src --worktree ~/w5-c-build/worktree-prep \
  --kit /mnt/d/w5-c-kit/module-ginux \
  --expected-receipt-sha256 63ce5f2de9ba00d334b2f03252f8772409bd68197bf323990db744668997d2ab \
  --out ~/w5-c-build/out-prep
```

Exit 0. Record status `prepared-not-built`, host commit and all four
pinned blobs verified by the builder itself, mkosi configuration
patched (modified SHA-256
`9de1bba47dc7dd7156a5bfd993cc06c62307520dcb891f1e399a6c7d3ee43acd`),
kit staged into `image/common/overlay/opt/thox/ginux` with the
Payload U EFI hash intact, source clone left clean. The full record
is `ginux-integration-source.json` in the worktree and the output
directory.

Environment finding: the same prepare with source and worktree under
`/mnt/d` did not finish in 20 minutes. The clone and checkout of a
954-file, 53 MB repository stalls on the DrvFs filesystem; on ext4
the identical run completes in seconds. Wave 2 recorded the same
rule for QEMU runtime state. Build state for this lane belongs on
WSL-native ext4; only large sequential outputs belong on `/mnt/d`.

### Full build run: BLOCKED at command 1, exact evidence

The `--build` run (worktree on ext4, `--out /mnt/d/w5-c-build/out-build`,
cache directory redirected to `/mnt/d`) prepared successfully, then
failed in its first executed command:

- Record `ginux-integration-source.json` in the output directory:
  `"status": "failed"`, `"executed_commands": [{"command": ["cargo",
  "test", "--workspace"], "exit_code": 101, "log":
  "integration-command-1.log"}]`. The builder printed `Stopped:
  Command failed with exit 101; retained
  /mnt/d/w5-c-build/out-build/integration-command-1.log`. The image
  build command never ran and no `.img` was produced by this path in
  Wave 5.
- The retained log shows 573 crates compiled, then two space
  failures: `collect2: fatal error: ld terminated with signal 7 [Bus
  error]` while linking a test binary, and `error: could not compile
  thox-vault-core (lib test)` caused by `No space left on device (os
  error 28)`.
- Root cause, measured: the host root filesystem `/dev/sdd` (1007 GB)
  had 11 GiB free at 99 percent use when the run started. The vibe
  workspace debug target alone grew to 11 GiB before the failure, and
  the root reached 100 percent (1.6 GiB free) at the failure. The
  lane's target directory was removed after the run and the root
  returned to 13 GiB free.
- Why the pipeline did not see this coming: the 125 GiB free-space
  gate in the pinned `image/build-image.sh` measures only the
  `--out` filesystem (`/mnt/d`, 309 GiB free, passes). It does not
  measure the filesystems that actually fill first on this host: the
  cargo target in the worktree and the Docker data root with its
  build and cargo volumes, both on `/dev/sdd`. The October 25 run of
  the same image build allocated 13.5 GiB in its Docker work volume
  alone, which also exceeds the free space the root had at the start
  of this run, so the image command would have faced the same wall
  even if the test command had passed.
- What a future run needs: at least roughly 40 GiB free on the root
  filesystem (or the worktree target and the Docker data root hosted
  on a volume with that space), then rerun the identical command.
  The kit, the source pin and the prepare stage are proven and are
  not part of the blocker.

### Image layout verification

No new image exists to verify from this path. As a labelled
reference only, the previous output of the same pinned builder
(`image/build-image.sh`, variant `x86_64-dual`, built 2026-10-25
from the same host commit, without the Ginux kit overlay) still
exists on the host and was verified read-only in this wave:
`/home/ttracx/thox-build-out/thoxos-vibe-rust-20261025/x86_64-dual/thoxos-x86_64-dual-1.0.0-rc.1+20261025.img`,
36,508,287,488 bytes, SHA-256
`8a58e2a62d0eda779689d2df342f5e9bd82f8d6869d6a90e75626a10e0929f85`,
matching its own `.sha256` sidecar. `sfdisk -l` shows a GPT with
four partitions: 1 GiB EFI System, 24 GiB Linux root (x86-64),
1 GiB Linux extended boot, 8 GiB Linux root (ARM-64). This is the
layout `build_external_ssd.py --build` would produce; it is not a
Wave 5 artifact and it does not contain the Payload U kit.

The Wave 2 edition SSD image
(`thoxos-ginux-knighthub-0.2.0.img`, SHA-256
`469b4f0c876eef78decb7c523e8cc1cb1dad4de0b377d8e53b293d39b0bb47f0`)
is no longer present under `/mnt/d/thoxinux-build/wave2-ssd/`; only
its logs and summary remain there. Its build record stands in that
summary; the file itself could not be re-verified in this wave.

## Item 7: installer dry-run verdict

There is no dry-run mode. Exact evidence:

- `install_host.py --dry-run` fails with `install_host.py: error:
  unrecognized arguments: --dry-run` (argparse, exit 2). Its modes
  are a system install (root, x86-64 Linux only) and `--stage-root`,
  which packages ordinary files only.
- `install-to-ssd.sh --dry-run` (edition tree,
  `userspace/ginux-edition/installer/install-to-ssd.sh`) fails with
  `install-to-ssd: unknown argument: --dry-run`, exit 1.
  `install-to-ssd.sh` has no preview flag of any kind; its safety
  model is refusal guards plus a typed confirmation before the
  first write.
- The only dry-run in the tree is in the vendored Windows writer
  (`boot/ssd/vendor/windows-writer/Thox.ExternalSsd.psm1`, a
  `dry-run-no-disk-write` plan state). It is PowerShell, was not run
  in this wave, and its source is vendored unchanged.

No dry-run mode was added. Per the wave rules the finding is
documented here instead, and the closest non-writing paths were
exercised:

1. `preflight.py --json`: runs clean, read-only. KVM accessible
   true, QEMU available true, running root is not a USB
   nonrotational candidate (root disk `/dev/sdd`, rotational), as
   expected under WSL.
2. `install_host.py --stage-root` with the real Payload U kit:
   exit 0, receipt `thox.ginux.host-install.v1`, `staging_only:
   true`, `physical_write: false`, `vm_started: false`, nine files
   staged under `/mnt/d/w5-c-kit/staged-root` including the EFI at
   the pinned Payload U hash.
3. `install_host.py` without `--stage-root` as the desktop user:
   refused, `Refused: System installation requires sudo; no VM is
   started by this installer`. The `--require-usb-root` form refuses
   at the same gate.
4. `install-to-ssd.sh` refusal matrix, run as root against image
   files and loop devices only. Every run exited 1 before any
   write:

| Case | Result |
|---|---|
| Run as desktop user | `install-to-ssd: run as root (sudo)` |
| `--device` is a regular file (`/mnt/d/w5-loop/small.img`) | `install-to-ssd: /mnt/d/w5-loop/small.img is not a block device` |
| `--device /dev/sdz99` does not exist | `install-to-ssd: /dev/sdz99 is not a block device` |
| Loop device without `--allow-internal` | `install-to-ssd: /dev/loop2 is a loop, not a whole disk (pass /dev/sdX, not a partition)` |
| Loop device (64 MiB) smaller than the image (128 MiB), with `--allow-internal` | `install-to-ssd: /dev/loop2 (67108864 bytes) is smaller than the image (134217728 bytes)` |
| Wrong confirmation name, loop device, `--allow-internal` | Target summary printed, then `install-to-ssd: confirmation 'wrongname' does not match 'loop2'; nothing was written` |
| Running root disk `--device /dev/sdd` | `install-to-ssd: /dev/sdd has mounted file systems; unmount them first` (mounts listed: `/`, `/var/lib/docker`, others) |

After the confirmation refusal, the loop backing file was verified
unchanged (`sha256sum -c` OK) and the loop device was detached.
Nothing was written to any device in this matrix.

Observation on the root-disk guard, recorded and not fixed in this
wave: `install-to-ssd.sh` derives the root disk from
`lsblk -o PKNAME` of the root source. Under WSL the root source is
the whole disk `/dev/sdd`, whose PKNAME is empty, so the dedicated
root-disk comparison does not fire; the mounted-filesystems guard
directly below it catches the same target instead. Defence in depth
held on this host. On a conventional install, where the root source
is a partition, PKNAME names the disk and the first guard fires.

## Item 7: refusal-guard tests

`boot/ssd/tests/test_host.py` before this wave: 15 tests, all
passing. After: 32 tests, all passing
(`python3 -m pytest -q tests` in `boot/ssd/`: 32 passed; one
transient failure in a single run made under heavy parallel
`/mnt/d` IO from the builder clone did not reproduce in two
subsequent full runs). Guards themselves were not modified; every
new test drives the real guard code.

New tests in `GuardRefusalTests` (14), each proving one refusal:

- `test_malformed_receipt_hash_refuses`: the expected receipt hash
  (the installer's confirmation token) must be exactly 64 hex
  characters; short, long, empty and non-hex values refuse.
- `test_missing_artifacts_directory_refuses`: a nonexistent kit and
  a kit whose `artifacts` is a regular file both refuse.
- `test_symlinked_artifacts_directory_refuses`: a symlinked
  `artifacts` directory refuses even when it resolves to real files.
- `test_directory_in_place_of_artifact_refuses`: a directory where
  an artifact file belongs refuses as non-regular.
- `test_missing_checksum_entry_refuses`: SHA256SUMS missing one of
  the four required entries refuses.
- `test_duplicate_checksum_entry_refuses`: a duplicated SHA256SUMS
  entry refuses.
- `test_receipt_missing_payload_binding_refuses`: a receipt whose
  `artifacts` map omits a payload refuses even with fresh checksums.
- `test_non_pe_efi_refuses_even_when_fully_bound`: an EFI without
  the `MZ` magic refuses even when receipt and checksums are
  honestly rebuilt around it.
- `test_empty_attribution_refuses_even_when_fully_bound`: an empty
  notice refuses under the same honest-rebinding setup.
- `test_launcher_without_shebang_refuses`: a launcher without a
  shebang line refuses.
- `test_stage_root_system_root_refuses`: `--stage-root /` (the
  running system root) refuses.
- `test_stage_require_usb_root_refuses`: staging combined with
  `--require-usb-root` refuses; staging cannot qualify storage.
- `test_builder_existing_worktree_refuses`:
  `build_external_ssd.prepare` refuses an existing worktree and the
  marker file inside it is preserved.
- `test_builder_output_under_dev_refuses`: `build_external_ssd`
  main refuses an `--out` under `/dev` with exit 2 and creates
  nothing there.

New tests in `KitAssemblyTests` (3), for the item 3 assembler:

- `test_assembled_kit_passes_verify_kit`: a kit assembled from a
  fixture payload passes the real `verify_kit`, with source lines
  recorded in the manifest.
- `test_assembler_refuses_unpinned_efi`: an EFI that does not match
  the pinned Payload U digest refuses and no kit is created.
- `test_assembler_refuses_existing_output`: an existing output
  directory refuses and its contents are preserved.

Already covered by the original 15 and not duplicated: wrong receipt
digest, corrupted artifact, checksums rewritten against the pinned
receipt, symlink payload file, checksum path traversal, existing
installation preserved, staging with package actions refused,
symlinked destination parent, preflight root-disk ancestry,
additive mkosi patching, vendored writer blob identity, and the
isolated build checkout.

## Files in this lane

- `boot/ssd/assemble_payload_kit.py` (new): reproducible kit
  assembly from a unified build output directory, with the Payload
  U digest pinned and the receipt generated honestly at assembly
  time.
- `boot/ssd/tests/test_host.py`: 17 tests added, no existing test
  changed, no guard code changed.
- `boot/ssd/docs/WAVE5-KIT-AND-INSTALLER.md`: this record.
- `boot/ssd/evidence/wave5-payload-kit.json`: machine-readable
  record of the kit, the runs and the test counts.
