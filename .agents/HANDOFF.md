# Agent handoff: ThoxInux

## Status (2026-10-31, updated by the D16 wave program)
- Monorepo created by transforming ttracx/thoxos-ginux (kept untouched as the private archive of record). Repository: Thox-ai/thoxinux, PUBLIC since D15 (2026-10-31), main carries the full thoxos-ginux history plus the consolidation commits. Private mirror: Thox-ai/thoxinux-staging.
- Phase 0 (audit and consolidation): unified patch series built and verified (docs/RECONCILIATION-2026-10-31.md); syscall audit at docs/COMPATIBILITY.md; threat model at docs/THREAT-MODEL.md; thox-agentos adopted at userspace/agentos/.
- Phase 1 (v0.9): unified EFI (Payload U) built on KnightHub and boot-tested in QEMU. Release v0.9.0 PUBLISHED on the public repo (pre-release, engineering preview) under D16. Correction of an earlier overstatement in this file: at D14 close the Docker demo was BLOCKED (daemon down) and the SSD bench was NOT RUN; their current state lives in docs/WAVES.md, Waves 1-2.
- Phase 2 (agentic loop): demonstrated per REVIEW-PACK.md evidence scope; guest integration state is stated there and in docs/WAVES.md exactly.
- Continuous waves: D16 (2026-10-31) authorizes wave-after-wave work with push and merge to public main when exits pass. The wave ledger is docs/WAVES.md; read it before starting any lane. Waves 1-5 are complete (v0.9.0 and v0.9.1 published; v0.9.1 is the controlled reproducible build, EFI SHA-256 1bc1c7af..., differing from Payload U only in 14 build-control bytes; make test green under both root and unprivileged users; lifecycle records now name the real accelerator; upstream re-sync evaluated, HOLD recommended; ARM64 scoped in docs/ARM64-SCOPING.md). Wave 6 is defined at the end of docs/WAVES.md; its starter item (build provenance in the receipt) is already merged. Open Wave 6 work: the upstream re-sync itself, the build_external_ssd.py disk-space unblock, the AgentOS guest retry on the re-synced kernel, installer --dry-run, demo EFI receipt discipline.

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
- KnightHub root filesystem was at 0 bytes free at Wave 5 close; it blocks build_external_ssd.py --build and any root-resident build state. Wave 6 item 2 owns the unblock.
- AgentOS in the Ginux guest is blocked on an upstream domain snapshot/resume fault with resident state-writing daemons (Wave 5 item 5 evidence); AgentOS itself is exonerated by bisects. Retry is gated on the Wave 6 re-sync.
- ARM64: scoping doc is ready (docs/ARM64-SCOPING.md); the five decision inputs there are Tommy's, target hardware class first.

## Last verified
2026-10-31, by the ThoxInux D16 wave program (Sadie), Wave 5 close. Evidence: REVIEW-PACK.md (with its Wave 1 and Waves 2-4 addenda), docs/WAVES.md (Waves 1-5 results, Wave 6 definition), evidence/wave5-lifecycle/ and evidence/wave5-lane-e/ in this repo, and the run logs archived with the plan at ~/workspace/thoxinux-plan-20261031/evidence/ (fleet-internal path).
