# Agent handoff: ThoxInux

## Status (2026-10-31, updated by the D16 wave program)
- Monorepo created by transforming ttracx/thoxos-ginux (kept untouched as the private archive of record). Repository: Thox-ai/thoxinux, PUBLIC since D15 (2026-10-31), main carries the full thoxos-ginux history plus the consolidation commits. Private mirror: Thox-ai/thoxinux-staging.
- Phase 0 (audit and consolidation): unified patch series built and verified (docs/RECONCILIATION-2026-10-31.md); syscall audit at docs/COMPATIBILITY.md; threat model at docs/THREAT-MODEL.md; thox-agentos adopted at userspace/agentos/.
- Phase 1 (v0.9): unified EFI (Payload U) built on KnightHub and boot-tested in QEMU. Release v0.9.0 PUBLISHED on the public repo (pre-release, engineering preview) under D16. Correction of an earlier overstatement in this file: at D14 close the Docker demo was BLOCKED (daemon down) and the SSD bench was NOT RUN; their current state lives in docs/WAVES.md, Waves 1-2.
- Phase 2 (agentic loop): demonstrated per REVIEW-PACK.md evidence scope; guest integration state is stated there and in docs/WAVES.md exactly.
- Continuous waves: D16 (2026-10-31) authorizes wave-after-wave work with push and merge to public main when exits pass. The wave ledger is docs/WAVES.md; read it before starting any lane.

## Key files and roles
- kernel/ginux/patches/series: the ONLY sanctioned form of THOX changes to upstream. Regenerate patches; never edit the prepared source.
- kernel/ginux/scripts/prepare_source.py: byte-exact patch verification. A refusal is a stop signal, not a bug to route around.
- kernel/ginux/scripts/build-native.sh, run-vm.sh: build and boot. QEMU profile is load-bearing: 2 GiB, 1 vCPU, intel-iommu intremap=off aw-bits=48.
- userspace/agentos/: agent supervisor workspace (thox-agentd). cargo test there is the agent contract's test suite.
- boot/ssd/: SSD image and installer. Its refusal guards are features; weakening one is a firing offense in this repo.
- docs/COMPATIBILITY.md: the syscall matrix at the pinned commit. Re-run the audit on every upstream re-sync before editing any number.
- REVIEW-PACK.md (repo root): what is proven, what is not, founder gates.

## Conventions
- Commits: small, imperative, Signed-off-by. Branches: lane/<topic>.
- Numbers always carry payload + environment labels (A, B, E, U per docs/RECONCILIATION-2026-10-31.md).
- No emojis, no em dashes in docs or copy. Brand green #05A451. Tagline, where used, is exactly: Your AI. Your Data. Your Rules.™
- Secret scan before every push. The repo is public (D15); v0.9.0 is published (D16). Public main moves by fast-forward or merge of verified wave work, not force-pushes.

## Blockers and open questions
- Named spare SSD for physical acceptance: founder input outstanding. QEMU USB-disk bench substitutes and is labelled.
- Azure subscription: deployment variants stay at their credential gates.
- Secure Boot signing: Phase 2 (v0.9 posture is Secure Boot off, founder decision D14).
- Phase 3 independent security review: firm and budget are a founder call. Scope pack is ready at docs/SECURITY-REVIEW-SCOPE.md.
- Live wave state (Docker, reproducibility, F2, guest integration): docs/WAVES.md.

## Last verified
2026-10-31, by the ThoxInux D16 wave program (Sadie). Evidence: REVIEW-PACK.md (with its Wave 1 addendum), docs/WAVES.md, and the run logs archived with the plan at ~/workspace/thoxinux-plan-20261031/evidence/ (fleet-internal path).
