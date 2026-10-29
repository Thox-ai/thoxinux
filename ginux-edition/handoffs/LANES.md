# Lane assignments: ThoxOS Ginux Edition

Shape: THOX-CLOSEOUT-HANDOFF-001 (Task, Inputs, Exit evidence, Stop). An assignment is not evidence that a lane ran it. Lanes pick up only rows that name them. Source: branch `ginux-edition-0.2.0` of `ttracx/thoxos-ginux`, directory `ginux-edition/`.

The same repository holds a separate record from a ChatGPT/Codex session (root `module-ginux/`, `ssd-module/`). Read `docs/RECONCILIATION_2026-10-28.md` first. Never merge the two records' claims.

## 0.2.0: Azure images and ThoxOS Desktop

| Lane | Task | Inputs | Exit evidence | Stop |
|---|---|---|---|---|
| Hermes | With Tommy's subscription: run `azure/publish-image.sh` for the desktop VHD, deploy `azure/azuredeploy.json` on Standard_D4s_v5 from one source IP, RDP in, switch the three looks, run `thoxos-ginux doctor` (KVM present) and `thoxos-ginux shell`; save the boot diagnostics screenshot | VHD and `.sha256` from the build, `docs/AZURE.md` | Image version ID, deployment output, screenshots, doctor output, add rows to `docs/VALIDATION.md` | Never open SSH or RDP to `*`; never put the admin password or AI key in the packet |
| Codex | Review `azure/azuredeploy.json` and `publish-image.sh` against current Azure CLI and ARM API versions; port the template to Bicep with a compile check in CI | `azure/`, `tests/test_azure_image.py` | PR with `az bicep build` output | Never mark unrun work done; never invent a price, date or certification |
| Muse | Captions for `docs/previews/azure/*.png`, each labeled "QEMU capture over RDP, not Azure" | Captures, `docs/VALIDATION.md` V20 onward | `docs/previews/azure/CAPTIONS.md` | Never publish; a simulation label never becomes a physical or Azure claim |
| Claude | Next named patches only: DEV_QUEUE item 10 (RDP screen lock) or 17 (GTK 4 and Qt themes) when Tommy schedules one | `docs/DESKTOP.md`, generator | Base and head SHA, `make test`, a bench run with captures | Never disable a guard (brand-lock scan, AA contrast check, VHD check) to pass |

| Name | Task | Exit evidence | Stop |
|---|---|---|---|
| Clara Voss | Brand check of every Azure capture and the generated themes: `#05A451` only green, ThoxOS casing, chip mark geometry, no neon | Checklist result per capture | No public-copy changes without Sera |
| Sera | Claim review of README, AZURE.md and the report: no Azure run claimed, AVD limits stated | Approved wording | No claim of an Azure deployment until Hermes's evidence exists |
| Julian Hale | Mount the 0.2.0 report HTML at `/docs/thoxos-ginux` on the Developers site with the research-preview label | Live URL | Developers site only; not the public thox.ai site |
| Nova | From a clean clone: `make test`, then the Azure desktop build and bench; return logs | Logs with exit codes and the VHD SHA-256 | Report failures as failures |
| Samuel Reed | File `docs/AZURE.md` and `docs/DESKTOP.md` in the docs lane | Links that resolve | Keep `.agents/` out of user docs |
| Kai | KnightHub desktop variant only when Tommy asks: write `DESKTOP=desktop` image to a spare USB SSD | Photo of the greeter, `lsblk` before and after | Never write Windows, system, protected or ambiguous storage, or the THOXOS-labeled SSD |
| Sadie | Closeout email for 0.2.0 (sent by the Odette lane from the Sadie@thox.ai mailbox) | Sent Items record | No substitute mailbox |

## 0.1.0
### Agent lanes

| Lane | Task | Inputs | Exit evidence | Stop |
|---|---|---|---|---|
| Hermes | Enforce closeout on the Sadie runtime: confirm the branch head, the preview path and the Outlook send record for this delivery; then run `make selftest` on KnightHub with `/dev/kvm` and record KVM timings | Branch head SHA, `docs/VALIDATION.md`, KnightHub with Docker | Packet with preview path, SHA, email record, selftest log with `accel=kvm` | Never send from AgentMail or Gmail; no tokens in the packet |
| Codex | Open the upstream pull request for `patches/0001` against gmkurtzer/ginux and file issues for REVIEW F3 (QEMU 10.0 virtio-net), F4 (auxv fixture) and F12 (OCI cache answers by tag) with the traces in REVIEW.md | `patches/0001-*.patch`, `docs/REVIEW.md` | PR URL, issue URLs, base and head SHA | Never claim an upstream merge; never invent a QEMU root cause for F3 |
| Muse | Draft claim-safe captions for the previews in `docs/previews/`: the web console boot, the web console shell session and the KnightHub SSD tty1 capture (label it "QEMU USB simulation") | `docs/previews/*.png`, `docs/VALIDATION.md` | Caption file in `docs/previews/CAPTIONS.md` | Never publish; never turn the QEMU simulation into a hardware claim |
| Claude | Apply only named patches in a clean checkout of this branch: next is the F4 fix (DEV_QUEUE item 18 since the 2026-10-29 re-score) when Tommy schedules it | `docs/REVIEW.md` F4 trace, `scripts/ginux-source.sh` | Base SHA, head SHA, commands, `make selftest` result | Never disable a Ginux guard to make a check pass |

### DigitalHumans lanes

| Name | Task | Exit evidence | Stop |
|---|---|---|---|
| Samuel Reed | File `docs/REVIEW.md`, `docs/USER_GUIDE.md` and this handoff in the docs lane | Links that resolve | Keep `.agents/` out of user docs |
| Julian Hale | Mount the HTML preview (`docs/previews/thoxos-ginux-edition-report.html`) at `/docs/thoxos-ginux` on the Developers site with the research-preview label visible | Live URL | Developers site only; not the public thox.ai site |
| Clara Voss | Check brand green `#05A451`, ThoxOS casing and the trademarked slogan in the report and README | Checklist result | No public-copy changes without Sera |
| Nova | Run `make test` and `make demo-image` from a clean clone; return the logs | Logs with exit codes | Report failures as failures |
| Kai | Own the KnightHub hardware steps: pick a spare USB SSD (not the THOXOS Vibe SSD), write the image, boot, photograph tty1, run `thoxos-g doctor` on tty2 | Photo, doctor output, `lsblk` before and after | Never write the internal NVMe or the THOXOS-labeled SSD without Tommy's ruling |
| Sera | Review claim language in the report and email before send | Approved wording | No claim of hardware boot until Kai's evidence exists |
| Sadie | Send the closeout email after the push (done in this delivery by the Odette lane from the Sadie@thox.ai mailbox) | Sent Items record | No substitute mailbox |

## Adherence plan

1. Every lane quotes the branch head SHA it worked from.
2. Results land as new rows in `docs/VALIDATION.md` with date, lane and evidence path.
3. A claim without evidence is written as "not run".
