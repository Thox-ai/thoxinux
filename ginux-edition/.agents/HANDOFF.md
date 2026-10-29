# Agent Handoff: thoxos-ginux (ginux-edition module)

Last verified: 2026-10-29 (0.2.0 closeout) by Odette Lark (Claude runtime)
Policy: THOX-REPO-001 v1.0

This module is the second runtime record in `ttracx/thoxos-ginux`. The first record (root `module-ginux/`, `ssd-module/`, `evidence/`) came from a ChatGPT/Codex session the same evening. The two are kept separate on purpose; `docs/RECONCILIATION_2026-10-28.md` at the repository root compares them. Do not merge their claims into one record.

## Status
- Done (0.2.0, 2026-10-29): Azure target in the host Dockerfile (cloud kernel with Hyper-V drivers in the initrd, cloud-init with the Azure datasource, agent with provisioning handed to cloud-init, conditional PTP refclock, serial console), ThoxOS Desktop for Azure and KnightHub (TXF 5.2 tokens, generated GTK 3 / xfwm4 / dock / terminal / splash / wallpapers / icons, three looks, `thoxos-look`, LightDM and xrdp login), fixed MiB-aligned VHD with checks, gallery publish script, ARM template with a first-boot script, `thox-ai-relay` for hosted models, per-user Ginux VMs, QEMU + RDP test bench with real captures, cold rebuild of GINUX.EFI.
- Final 0.2.0 evidence: desktop VHD bench 23 of 23, headless bench 13 of 13 (ThoxOS on Ginux to login for the administrator), KnightHub 0.2.0 SSD bench 6 of 6; hashes in `docs/evidence/0.2.0/`. Images and repository compared byte for byte.
- Done (0.1.0): Ginux review (`docs/REVIEW.md`), patches 0001-0003, ThoxOS userspace image, Docker demo image, headless selftest gate passing under TCG, interactive shell domain (`thox-shell`, e2e passing), browser console, KnightHub SSD disk image (8 GiB GPT, systemd-boot, Debian 13 host, tty1 in shell mode), Linux and Windows writers, QEMU USB-disk boot harness, stale-cache volume reset, 80 unit tests.
- In progress: none in this runtime after closeout.
- Next: `docs/DEV_QUEUE.md` items 1 to 3 (KnightHub KVM boot, first Azure deployment, ruling on the desktop implementation location).

## Key files
| Path | Role |
|---|---|
| `upstream.lock` | Ginux commit and Rocky image digest pins |
| `patches/` | ThoxOS changes to Ginux (IOMMU width and firmware discovery, banner, scoped registry root) |
| `scripts/ginux-source.sh`, `make-local-ca.sh`, `build-efi.sh` | Source prep, per-build PKI, EFI build |
| `rootfs/` | ThoxOS userspace image (Containerfile, overlay, `thox` CLI, `thox-shell` line editor) |
| `runtime/thoxos_g.py` | QEMU profile and controller console driver (single source of truth) |
| `docker/` | Demo image and entrypoint (console, web, selftest, doctor, qemu, exec) |
| `installer/host/Dockerfile`, `configure-host.sh` | Every host root: `TARGET=knighthub|azure`, `DESKTOP=headless|desktop` |
| `installer/` | Disk assembly (`assemble-disk.sh`), image build wrapper (`build-host-image.sh`), Linux writer, Windows writer |
| `desktop/` | ThoxOS Desktop: `tokens/txf-tokens.json` (copied unchanged from TXF), `generator/txf_desktop_gen.py`, `bin/` (thoxos-look, AI chip, Ask THOX), `overlay/` (panel, dock, greeter, launchers, first boot) |
| `azure/` | Azure overlay, `build-vhd.sh` + `vhd_check.py`, `publish-image.sh`, `azuredeploy.json` |
| `runtime/thox_ai_relay.py` | Loopback relay for hosted AI (stdlib only) |
| `tests/e2e/azure/` | QEMU + xfreerdp bench for the Azure VHD |
| `tests/` | pytest suite, fake QEMU, e2e scripts |

## Conventions
- Naming: `thoxos-g` for the launcher and services, `THOXOS_G_*` for settings.
- Commit style: imperative subject, why in the body, `docs:` prefix for docs-only.
- Test command: `make test`; boot gate: `make selftest`; shell gate: `tests/e2e/shell_session.py`; SSD harness: `tests/e2e/boot-ssd-image.sh`; Azure bench: `tests/e2e/boot-azure-image.sh VHD OUT GINUX_WAIT`.
- Build command: `make demo-image`, `make ssd-image`, `installer/build-host-image.sh --target azure --desktop desktop|headless ...` (add `EXTRA_CA=` behind a TLS-inspecting proxy).
- Versions: host images read `HOST_VERSION` (0.2.0); the guest reads `VERSION` (0.1.0).
- Desktop themes are generated: edit `desktop/generator/txf_desktop_gen.py` or the token file, never the generated files. The generator fails the build on `#10B981` or `#00FF88`.

## Blockers and open questions
- Azure itself not run: no subscription in this runtime. Publish and deploy are DEV_QUEUE item 2.
- Contradiction for Tommy: TXF `DESKTOP-VARIANTS.json` names `ttracx/thoxos-desktop` canonical for ThoxOS Desktop; that repository holds Ubuntu 26.10 + Plasma tooling only. The Debian 13 implementation lives here until ruled (DESKTOP.md, D19).
- Azure Virtual Desktop cannot host Linux session hosts; the image runs as a plain Azure VM (AZURE.md, D17).
- KnightHub hardware boot not run (machine not reachable from this runtime).
- Target disk for the SSD image needs Tommy's ruling: the THOXOS-labeled 500 GB SSD carries ThoxOS Vibe; the installer refuses it without `--erase-existing-thoxos`.
- Getty login inside the Ginux domain does not reach a password prompt (VALIDATION.md, V9). Interactive use goes through the shell domain (`thox-shell`, V12) until upstream adds console line discipline.
- Windows writer not run on Windows.
- 0.1.0 KnightHub image very likely shares one machine ID across every SSD written from it (VALIDATION D-16); use the 0.2.0 image.
- Record A's Azure variant (pull request #2) awaits a ruling beside this one (`docs/RECONCILIATION_2026-10-29.md`, R4 to R8).
- GitHub CI runs end `startup_failure` before any job (VALIDATION V19); check the repository's Actions settings.

## Compliance
| Section | State |
|---|---|
| README with badges | present |
| LICENSE + NOTICE.md (THOX.ai LLC IP notice) | present |
| docs/USER_GUIDE.md | present |
| docs/QUICKSTART.md (tested commands only) | present |
| docs/previews screenshots | present (QEMU captures; Azure desktop over RDP in `docs/previews/azure/`) |
| docs/DEVELOPMENT.md | present |
| GitHub description and topics | partial (repository owned by the first record; not changed by this runtime) |
| Formal release | missing (no release until hardware acceptance) |
