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

## 0.2.0: Azure images and ThoxOS Desktop

Run 2026-10-29 (America/Chicago) by Odette Lark on the same build host (2 vCPU, 7 GB RAM, Docker 29.9, no `/dev/kvm`). Every boot below is QEMU TCG; ThoxOS on Ginux inside a booted image is nested software emulation. Nothing ran on Azure. Bench reports and logs: [evidence/0.2.0/](evidence/0.2.0/). The final images were built and benched in one chain (`final-chain-summary.txt`); its first desktop build stopped when the build host ran out of disk space and was repeated after removing old test volumes.

### Artifacts

| Artifact | Identity |
|---|---|
| `GINUX.EFI` (cold rebuild, same source and patches) | 12,497,920 bytes, SHA-256 `6ff22d32dbabaa621f85a6ba16acc42bb95ed85fc928ae9eb7312992286856a1`. Differs from 0.1.0's `0a7c68a4...` because each build embeds a fresh registry root (patch 0003) |
| Azure desktop VHD | `thoxos-ginux-azure-desktop-0.2.0.vhd`, 8 GiB fixed + 512-byte footer, SHA-256 `d6134d1a40043435ff936d1b0e7775a2fa22d31dad0e6968e9491ba310ef80a7`; host kernel 6.12.113+deb13-cloud-amd64 |
| Azure headless VHD | `thoxos-ginux-azure-headless-0.2.0.vhd`, SHA-256 `aa01d70c8b53dd8f61b35a07f2fa468853057bdd4631239ae31edf7dae53b13d` |
| KnightHub SSD image | `thoxos-ginux-knighthub-0.2.0.img`, 8 GiB, SHA-256 `fc6246a463196d57ad9f4894262e919ecea621273467a78eddc8c1a16c433c3d`; host kernel 6.12.113+deb13-amd64 |
| Image contents | Every overlay file, `configure-host.sh`, the desktop tools and `thox_ai_relay.py` inside the three host images compared byte for byte with the repository (`cmp`): no differences |

### Results

| ID | Check | Status | Evidence |
|---|---|---|---|
| V20 | Ginux kernel builds cold | Verified | `docker build --no-cache` of the demo image: 1 min 59 s, EFI stage 73 s, cargo release builds clean |
| V21 | Desktop theme generation | Verified | Generator runs in the image build; AA contrast and brand-lock checks pass (they stop the build otherwise). Full generation test with the real fonts in the build container: 13 of 13 |
| V22 | Unit and static checks | Verified | `make test`: 137 pytest cases pass, 1 skipped (the full theme generation needs JetBrains Mono, so it ran in the build container instead, V21); `bash -n` and shellcheck clean on 22 shell files |
| V23 | Azure VHD format | Verified | `vhd_check.py` on both VHDs: fixed type, footer checksum, whole MiB, size; `qemu-img` conversion test in the suite. Build times with a warm Docker cache: desktop 117 s, headless 47 s |
| V24 | ARM template and first-boot script | Verified (static) | Every `parameters()` and `variables()` reference resolves; SSH and RDP rules admit only `allowedSourceCidr`, which has no default; standard security; the template's `format()` script is rendered and run with stubs, including a hostile upstream URL and key: no injection, relay file written, look set. Not deployed |
| V25 | `thox-ai-relay` | Verified (local) | 17 tests: loopback-only listen, auth header per scheme, model alias, streaming refused, size caps, rate limit, upstream error mapping, against a stub upstream. No hosted model called |
| V26 | Desktop VHD boots and provisions like Azure | Verified | `tests/e2e/boot-azure-image.sh ... 600`: 23 of 23 checks, 20 min 43 s. SSH after 43 s; cloud-init `status: done` (NoCloud seed; the image lists `[Azure, NoCloud]`); systemd `running`, no failed units; identity and cloud kernel; xrdp, LightDM, registry, DNS, SSH active; administrator in `sudo` and `kvm`; root grown to 19.1 GiB; SSH and xrdp keys made at first boot; machine ID `a4d8f21f...` equal to the VM's UUID (generated, not copied); AI relay off and chip AI OFF; `thoxos-ginux doctor` ok; `Provisioning.Agent=cloud-init`, Hyper-V modules in the initrd. Outside Azure the agent stays inactive and chrony runs on the NTP pool |
| V27 | Console splash and greeter | Verified | Plymouth ThoxOS splash and the LightDM greeter captured from the VGA console (`previews/azure/boot-splash.png`, `lightdm-greeter.png`) |
| V28 | RDP login and the three looks | Verified | Branded xrdp login captured; one RDP session per look reached `xfce4-panel` and `plank`, and `xfconf-query` returned `ThoxOS-Slate`, `ThoxOS-Porcelain`, `ThoxOS-ConsolePro`; launcher icons present in the icon cache (`previews/azure/rdp-*.png`) |
| V29 | ThoxOS on Ginux inside the desktop | Verified | Console Pro session, dock launcher command: the user's Ginux VM pulled ThoxOS from the host registry (4 layers, 109,778,634 bytes; OCI total 445.6 s), Linux init to console 116.9 s, then typed `uname -srm` gave `Ginux 6.12.0-ginux.0.1 x86_64` and `thox status` reported ThoxOS 0.1.0 Ginux Edition with AI not configured (`previews/azure/rdp-console-pro-ginux.png`) |
| V30 | Headless VHD boots, provisions, and runs ThoxOS on Ginux | Verified | Same bench on the headless VHD: 13 of 13 checks, 15 min 19 s. SSH after 40 s; cloud-init done; systemd `running`; registry, DNS, SSH active; machine ID equal to the VM's UUID; `thoxos-ginux doctor` ok; then the administrator's own Ginux VM booted ThoxOS with systemd to `Welcome to ThoxOS` and `login:` in 853 s (nested software emulation). The serial console shows the login banner `ThoxOS Ginux Edition host on Debian 13 (Trixie)` |
| V31 | KnightHub 0.2.0 SSD image (regression after the shared Dockerfile) | Verified | `tests/e2e/boot-ssd-image.sh` on the 0.2.0 image as a USB disk: 6 of 6 (kernel, root, growroot, registry, DNS, console) in 2 min 15 s; machine ID from the random generator, not the image; tty1 capture `previews/knighthub-ssd-tty1-qemu-usb-0.2.0.png` |
| V32 | Azure: gallery image, deployment, Azure datasource, agent provisioning, Hyper-V devices, PTP time | Not run | No Azure subscription in this runtime (DEV_QUEUE item 2) |
| V33 | Nested KVM for Ginux on Azure | Not run | Microsoft lists nested virtualization as supported on Dsv5; not measured |
| V34 | Hosted model through the relay | Not run | No endpoint or key in this runtime (DEV_QUEUE item 5) |
| V35 | Secure Boot / Trusted Launch | Not supported | Unsigned systemd-boot; images use standard security (DEV_QUEUE item 12) |

## Defects found and fixed during 0.2.0 validation

Every defect below was found by building the images or booting them in the Azure bench, and fixed before the final images.

| ID | Defect | Fix |
|---|---|---|
| D-01 | `Failed to enable unit: Unit cloud-init.service does not exist`: cloud-init 25 renamed its units | `configure-host.sh` detects `cloud-init-network.service` and requires every cloud-init stage to be enabled |
| D-02 | Firefox policies collided with the `distribution` symlink of the Debian package | Policies ship in `/etc/firefox/policies` and `/etc/firefox-esr/policies` |
| D-03 | xrdp branding never applied: Debian ships the login-screen keys commented out | The `xrdp.ini` edits match `#key=` and are verified line by line; the login box is light because xrdp draws its labels in black |
| D-04 | False "hv_vmbus missing from the initrd": `lsinitramfs | grep -q` died of SIGPIPE under `pipefail` | The listing goes to a file, then grep |
| D-05 | Boot paused 300 s after "Loading essential drivers": `rootdelay=300` is a fixed sleep in Debian's initramfs-tools | No `rootdelay` (D21); first boot to SSH fell from 340 s to under a minute in the bench |
| D-06 | `chrony.service` failed: chronyd stops fatally when the PHC refclock device is missing (everywhere but Hyper-V) | The refclock is written to `/run` only when `/dev/ptp_hyperv` exists |
| D-07 | RDP desktop never appeared; `xfce4-session` and `xfwm4` spun at full CPU: a `gtk-3.0/settings.ini` that sets `gtk-application-prefer-dark-theme` makes GTK 3 reload the theme in a loop | No `settings.ini` in the generated themes (unit test added) |
| D-08 | Folders stayed blue: the derived icon themes copied `folder-blue-*.svg` but not the generic names, which are symlinks | The generator mirrors those links |
| D-09 | A line across the desktop above the dock and a shadow under the top bar: xfwm4 shadows plank's full-width window | `show_dock_shadow=false`, `vblank_mode=off` (D28) |
| D-10 | After D-06, `chrony.service` still failed: the unit runs as `_chrony` under `ProtectSystem=strict`, so the new step could not write `/run` | `ExecStartPre=+` runs that one step as root (unit test added) |
| D-11 | No splash: with `console=ttyS0` Plymouth falls back to text on every console | `plymouth.ignore-serial-consoles` on the Azure desktop command line (D30) |
| D-12 | No console greeter in QEMU: the cloud kernel has no DRM driver, so logind never made seat0 graphical | udev rule tags the UEFI framebuffer `master-of-seat`; systemd's hwdb already tags Hyper-V's (D29) |
| D-13 | Three identical chip icons in the dock, a duplicate Files icon, four colored action buttons (one a lock with no locker behind it), the About window scrolled under a "child exited" bar | Six generated launcher icons, dock items point at `thunar.desktop` and `xfce4-terminal.desktop`, one log-out button, `thoxos-hold` instead of `--hold` |
| D-14 | Greeter caption cut off at the left on 16:10 screens | Caption centered on the login wallpaper |
| D-15 | Launcher icons fell back to a generic gear after a rebuild: apt's triggers had built the hicolor icon cache before the generated icons were copied, and GTK trusts the cache | `configure-host.sh` rebuilds the caches and fails if the icons are missing; the bench checks the cache |
| D-16 | Every VM from an image would get the same machine ID: the dbus package wrote `/var/lib/dbus/machine-id` during the build and systemd initializes an empty `/etc/machine-id` from it (serial log: "Initializing machine ID from D-Bus machine ID"). Found because two bench runs of one image reported the same ID. The 0.1.0 KnightHub image used the same build steps and is very likely affected; it is no longer here to inspect | The D-Bus file is a link to `/etc/machine-id`, `configure-host.sh` fails otherwise; the random seed is removed too. The bench now fails if the ID came from the image and records it beside the VM's UUID |
