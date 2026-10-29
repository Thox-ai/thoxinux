# Lane assignments: ThoxOS Ginux Edition 0.1.0

Shape: THOX-CLOSEOUT-HANDOFF-001 (Task, Inputs, Exit evidence, Stop). An assignment is not evidence that a lane ran it. Lanes pick up only rows that name them. Source: branch `ginux-edition-0.1.0` of `ttracx/thoxos-ginux`, directory `ginux-edition/`.

The same repository holds a separate record from a ChatGPT/Codex session (root `module-ginux/`, `ssd-module/`). Read `docs/RECONCILIATION_2026-10-28.md` first. Never merge the two records' claims.

## Agent lanes

| Lane | Task | Inputs | Exit evidence | Stop |
|---|---|---|---|---|
| Hermes | Enforce closeout on the Sadie runtime: confirm the branch head, the preview path and the Outlook send record for this delivery; then run `make selftest` on KnightHub with `/dev/kvm` and record KVM timings | Branch head SHA, `docs/VALIDATION.md`, KnightHub with Docker | Packet with preview path, SHA, email record, selftest log with `accel=kvm` | Never send from AgentMail or Gmail; no tokens in the packet |
| Codex | Open the upstream pull request for `patches/0001` against gmkurtzer/ginux and file issues for REVIEW F3 (QEMU 10.0 virtio-net), F4 (auxv fixture) and F12 (OCI cache answers by tag) with the traces in REVIEW.md | `patches/0001-*.patch`, `docs/REVIEW.md` | PR URL, issue URLs, base and head SHA | Never claim an upstream merge; never invent a QEMU root cause for F3 |
| Muse | Draft claim-safe captions for the previews in `docs/previews/`: the web console boot, the web console shell session and the KnightHub SSD tty1 capture (label it "QEMU USB simulation") | `docs/previews/*.png`, `docs/VALIDATION.md` | Caption file in `docs/previews/CAPTIONS.md` | Never publish; never turn the QEMU simulation into a hardware claim |
| Claude | Apply only named patches in a clean checkout of this branch: next is DEV_QUEUE item 8 (finish the F4 fix) when Tommy schedules it | `docs/REVIEW.md` F4 trace, `scripts/ginux-source.sh` | Base SHA, head SHA, commands, `make selftest` result | Never disable a Ginux guard to make a check pass |

## DigitalHumans lanes

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
