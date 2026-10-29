# Agent Handoff: thoxos-ginux (ginux-edition module)

Last verified: 2026-10-29 by Odette Lark (Claude runtime)
Policy: THOX-REPO-001 v1.0

This module is the second runtime record in `ttracx/thoxos-ginux`. The first record (root `module-ginux/`, `ssd-module/`, `evidence/`) came from a ChatGPT/Codex session the same evening. The two are kept separate on purpose; `docs/RECONCILIATION_2026-10-28.md` at the repository root compares them. Do not merge their claims into one record.

## Status
- Done: Ginux review (`docs/REVIEW.md`), patches 0001-0003, ThoxOS userspace image, Docker demo image, headless selftest gate passing under TCG, interactive shell domain (`thox-shell`, e2e passing), browser console, KnightHub SSD disk image (8 GiB GPT, systemd-boot, Debian 13 host, tty1 in shell mode), Linux and Windows writers, QEMU USB-disk boot harness, stale-cache volume reset, 80 unit tests.
- In progress: none in this runtime after closeout.
- Next: `docs/DEV_QUEUE.md` items 1 to 3 (KnightHub KVM boot, upstream PR and issues, KVM timings).

## Key files
| Path | Role |
|---|---|
| `upstream.lock` | Ginux commit and Rocky image digest pins |
| `patches/` | ThoxOS changes to Ginux (IOMMU width and firmware discovery, banner, scoped registry root) |
| `scripts/ginux-source.sh`, `make-local-ca.sh`, `build-efi.sh` | Source prep, per-build PKI, EFI build |
| `rootfs/` | ThoxOS userspace image (Containerfile, overlay, `thox` CLI, `thox-shell` line editor) |
| `runtime/thoxos_g.py` | QEMU profile and controller console driver (single source of truth) |
| `docker/` | Demo image and entrypoint (console, web, selftest, doctor, qemu, exec) |
| `installer/` | Host root, disk assembly, Linux writer, Windows writer |
| `tests/` | pytest suite, fake QEMU, e2e scripts |

## Conventions
- Naming: `thoxos-g` for the launcher and services, `THOXOS_G_*` for settings.
- Commit style: imperative subject, why in the body, `docs:` prefix for docs-only.
- Test command: `make test`; boot gate: `make selftest`; shell gate: `tests/e2e/shell_session.py`; SSD harness: `tests/e2e/boot-ssd-image.sh`.
- Build command: `make demo-image`, `make ssd-image` (add `EXTRA_CA=` behind a TLS-inspecting proxy).

## Blockers and open questions
- KnightHub hardware boot not run (machine not reachable from this runtime).
- Target disk for the SSD image needs Tommy's ruling: the THOXOS-labeled 500 GB SSD carries ThoxOS Vibe; the installer refuses it without `--erase-existing-thoxos`.
- Getty login inside the Ginux domain does not reach a password prompt (VALIDATION.md, V9). Interactive use goes through the shell domain (`thox-shell`, V12) until upstream adds console line discipline.
- Windows writer not run on Windows.

## Compliance
| Section | State |
|---|---|
| README with badges | present |
| LICENSE + NOTICE.md (THOX.ai LLC IP notice) | present |
| docs/USER_GUIDE.md | present |
| docs/QUICKSTART.md (tested commands only) | present |
| docs/previews screenshots | present (QEMU captures) |
| docs/DEVELOPMENT.md | present |
| GitHub description and topics | partial (repository owned by the first record; not changed by this runtime) |
| Formal release | missing (no release until hardware acceptance) |
