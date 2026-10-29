# Validation report

Run 2026-10-28 to 2026-10-29 (America/Chicago) by Odette Lark on an Ubuntu 24.04 build host: 2 vCPU, 7 GB RAM, Docker 29.9.2, no `/dev/kvm`. Every Ginux boot below is QEMU TCG (software CPU). Nothing ran on KnightHub hardware.

## Artifacts

| Artifact | Identity |
|---|---|
| Ginux source | gmkurtzer/ginux `36503bda2d87465765e1b94e65f9d100f27ed5be` + patches 0001-0003 |
| `GINUX.EFI` (ThoxOS build) | SHA-256 `0a7c68a48af43bd51389800b4bbd62cd945bf0839b9a4d8bef955a2ea9a5fd27` |
| ThoxOS userspace (OCI, gzip) | 4 layers, 109,774,985 bytes in the Ginux cache |
| Demo image | `thoxos-g/demo:0.1.0`, QEMU 11.1.2, OVMF 4M, registry v2, ttyd 1.7.7 |
| KnightHub SSD image | `thoxos-ginux-knighthub-0.1.0.img`, 8 GiB GPT (512 MiB ESP + 7.5 GiB ext4), host kernel 6.12.113+deb13-amd64; final SHA-256 `6edc11d0085aa71f4689544b4ef333727d9fc986c926f44a5ae89537f4865690` (each build writes `build/ssd/*.sha256`). Delivered as `thoxos-ginux-knighthub-0.1.0.img.xz` (`xz -9e`, 416,857,780 bytes, SHA-256 `7802f7183bc0219a1257aeef05e00549a541ae43be1457bed9f2f0e336be2857`; decompresses to the image hash above) |

## Results

| ID | Check | Status | Evidence |
|---|---|---|---|
| V1 | Upstream builds unmodified (Rust 1.99.0, clang 18) | Verified | 12,497,408-byte EFI |
| V2 | QEMU matrix, controller boot | Verified | 8.2.2: panics on IOMMU width without patch 0001, boots with it. 10.0.13: panics in virtio-net init. 10.2.2 and 11.1.2: boot |
| V3 | Embedded minimal-system domain (`embedded://minimal-system-v0`) | Blocked (upstream) | Panics on 8.2.2, 10.2.2, 11.1.2; source trace in REVIEW F4 |
| V4 | Unit and static checks | Verified | `make test`: 80 pytest cases pass, `bash -n` and shellcheck clean on 11 shell files |
| V5 | Docker selftest: ThoxOS system domain | Verified | `make selftest` exit 0: OCI pull 4 layers verified (19.2 s transfer, 38.5 s total), `Welcome to ThoxOS 0.1.0 Ginux Edition!`, `multi-user.target`, issue banner, `login:` |
| V6 | Registry trust is scoped | Verified | Ginux pulls from `registry.thoxos.internal` only through the per-build root; root key destroyed (`make-local-ca.sh`) |
| V7 | KnightHub SSD image build | Verified | `make ssd-image`: host root exported, ESP and ext4 assembled without loop mounts, 826 MB on disk. Final build 2026-10-29 05:20 UTC, 47 s with a warm Docker cache, image SHA-256 `6edc11d0085aa71f4689544b4ef333727d9fc986c926f44a5ae89537f4865690` |
| V8 | SSD image boots as a USB disk (QEMU, OVMF, xHCI usb-storage, e1000e, 12 GiB disk) | Verified | `tests/e2e/boot-ssd-image.sh` on the final image (`6edc11d0...5690`, 2026-10-29, 2 min 14 s): kernel, root mounted, growroot to 11.5 GiB, registry, DNS, console service. tty1 capture shows Ginux, the ThoxOS banner, the `thoxos-shell` domain set up in shell mode and the OCI pull from the host registry (`docs/previews/knighthub-ssd-tty1-qemu-usb.png`). The harness captures tty1 during the pull, so the shell prompt on the SSD host is not verified here; KnightHub (V13) is that check |
| V9 | Console login inside the Ginux domain | Blocked (upstream) | `ginux login:` accepts a user name, then the getty restarts without a password prompt. Bash as domain init prints its prompt, then `exit` at its first read, and the domain is marked failed. The Ginux console has no line discipline (one byte per read, no echo). Upstream tests never log in interactively |
| V10 | Linux writer on a loop device | Verified | Refused: loop without `--allow-internal`, wrong confirmation, THOXOS-labeled disk. Wrote and verified 8 GiB in 21 s; `sgdisk -v`: no problems, backup GPT at disk end. The final image as `.img.xz` written to a 10 GiB loop device in 1 min 16 s: partitions verified against the image, `sgdisk -v` clean |
| V11 | Web console | Verified | Unauthenticated request 401, with credential 200; one client; capture in `docs/previews/web-console-thoxos-boot.png` |
| V12 | ThoxOS shell domain (`--shell`, init `thox-shell`) | Verified | `tests/e2e/shell_session.py`: ThoxOS banner and motd, then typed commands run on Ginux: `grep PRETTY_NAME /etc/os-release` gives `ThoxOS 0.1.0 Ginux Edition`, `uname -srm` gives `Ginux 6.12.0-ginux.0.1 x86_64`, `thox status` reports kernel Ginux, `thox version` gives `0.1.0` |
| V13 | KVM boot on KnightHub | Not run | Hardware not reachable from this runtime |
| V14 | Windows writer (`Install-ThoxOSGinux.ps1`) | Not run | No Windows host in this runtime |
| V15 | Secure Boot | Not supported | Unsigned systemd-boot; documented |
| V16 | Stale Ginux cache after a rebuild (REVIEW F12) | Verified | One volume, filled by the previous demo build: shell e2e failed after `/etc/issue` (`Linux init execution failed`). With the stamp fix the same volume was replaced (`persistent storage initialized (generation 1)`, `OCI cache miss; pulling image`) and `tests/e2e/shell_session.py` passed all five steps. A later `make demo` on the stamped volume reported `OCI cache hit (4 layers)` with no reset |
| V17 | Browser console, shell session | Verified | `thoxos-g/demo:0.1.0 web` with `THOXOS_G_MODE=shell`, headless Chromium typing into ttyd: `grep PRETTY_NAME /etc/os-release`, `uname -srm` (`Ginux 6.12.0-ginux.0.1 x86_64`) and `thox status` ran; capture in `docs/previews/web-console-thoxos-shell.png`. Ginux printed its 60-second runtime diagnostic once while the shell waited for input (informational, REVIEW F13) |
| V18 | Quick-start make targets | Verified | Under a pty: `make demo-shell` reached the `thoxos:~#` prompt; `make demo` reached `Welcome to ThoxOS 0.1.0 Ginux Edition!` and `ginux login:`; `make demo-web` answered 401 without the generated credential |
| V19 | GitHub CI (`.github/workflows/ginux-edition-ci.yml`) | Blocked | Push and pull-request runs on `962703a` both ended `startup_failure` before any job started; this is the repository's first workflow. The cause is not visible from this runtime; the repository's Actions settings are the place to check. `make test` passes from a fresh clone of the branch (80 tests) |

## Defects found and fixed during validation

| Defect | Fix |
|---|---|
| The writer's THOXOS-label guard read labels through `lsblk`, which depends on udev and returned nothing on the build host: the guard failed open and a rehearsal write proceeded on a loop device | Labels are now probed with `blkid -p` on the disk and every partition; rehearsal repeated and refused |
| The writer's verify step died with SIGPIPE (exit 141) under `pipefail` | Region hash reads with `dd count=`; SIGPIPE from the producer is expected and tolerated |
| `make test` syntax-checked only the first shell file | Loops over every file |
| SSD harness crashed QEMU 11.1 TCG when the guest host started KVM on emulated SVM | Harness exposes no SVM/VMX; the guest host falls back to TCG |
| Console matching missed systemd's coloured `Welcome to ThoxOS` | Escape sequences are stripped before matching (tests added) |
| A browser-console shell session on a volume reused from the previous build failed right after `/etc/issue` (`Linux init execution failed`): Ginux served the cached userspace of that build | Volume stamped with the served manifest's SHA-256 and replaced on change (REVIEW F12, five tests added) |
