# ThoxInux Wave Ledger

Continuous execution record under decision D16 (2026-10-31): work
proceeds wave after wave against the REVIEW-PACK open items; when a
wave's exits pass, it is pushed and merged to this public repo without
per-step approval. Hard gates that stop work: physical disk writes (no
named spare SSD), Azure deployment (no subscription), Phase 3
security-review firm engagement or any spend, thox.ai website, founder
email or social posts.

Status legend: PROVEN means run and observed. BLOCKED means a named
blocker with evidence. OPEN means remaining work, stated honestly.

Baseline: D14 run, REVIEW-PACK.md in this repo. Public main started the
wave program at commit 5ec049b.

## Wave 1: Publish and confirm (complete 2026-10-31)

Scope: publish v0.9.0 on the public repo from the staging draft assets;
run the 22-command lifecycle suite against Payload U itself (run2, TCG
and KVM); sync staging and public; REVIEW-PACK addendum.

- Release v0.9.0: PUBLISHED at
  https://github.com/Thox-ai/thoxinux/releases/tag/v0.9.0 as a
  pre-release (engineering preview), not a draft. Assets GINUX.EFI
  (12,507,648 bytes) and SHA256SUMS were downloaded from the private
  staging draft, hash-verified (GINUX.EFI SHA-256
  85722bd41426491bf86f810bbdd25f951c53afc49e1bf32ad5b34c63ab4420ae),
  uploaded to the public release, then downloaded back from the public
  release and hash-verified again: byte-identical at every hop. An
  unauthenticated read of the release confirms draft=false,
  prerelease=true. Release notes carry the run2 result below and state
  plainly that build reproducibility is not yet demonstrated.
- Payload U lifecycle run2: PROVEN. The suite
  (kernel/ginux/tests/acceptance_lifecycle.py) exercises the
  minimal-domain start directly. First runs stopped at 0/22-executed on
  both accelerators: the suite hardcoded the Azure candidate banner
  ("THOX Azure Compute Edition (QEMU/TCG)") while Payload U prints the
  unified banner by design; the guest had booted cleanly to the prompt.
  Classified as a stale harness expectation, not a kernel defect. With
  the banner expectation corrected, the result is 22/22 under TCG and
  22/22 under KVM (KnightHub, QEMU 10.2.1, OVMF 2025.11, runtime state
  on WSL-native ext4). The correction is now committed in the suite
  itself (it accepts either known THOX profile banner), and the
  committed suite was re-run by the coordinator: 22/22 KVM and 22/22
  TCG against Payload U. The Oct 28 failure string "minimal system init
  execution failed" appears in no serial log. This closes the D14 open
  confirmation: the unified series addresses the minimal-domain start
  failure, now proven against the actual Payload U bytes.
- Repo sync: public main and private staging main fast-forwarded to the
  same commits. Wave 1 code and docs commit: 722c262 (suite banner fix,
  QUICKSTART aw-bits annotation, COMPATIBILITY drift note).

## Wave 2: Docker, demo, SSD

Scope: revive Docker on KnightHub WSL or prove it cannot run there; if
it lives, host-image tests, the Docker demo path end to end, the SSD
image build and the QEMU USB-disk bench.

- Status: IN PROGRESS (results land here as they are proven).

## Wave 3: Reproducibility, agentos, docs

Scope: two clean-tree EFI builds with SHA-256 compare; thox-agentd F2
SIGTERM fix with regression test; agentOS guest integration attempt;
QUICKSTART aw-bits annotation and COMPATIBILITY drift note.

- Doc corrections: DONE in commit 722c262. QUICKSTART.md's QEMU profile
  now carries the aw-bits annotation (upstream run.sh passes no aw-bits
  argument in the passing lifecycle runs; the requirement is unproven),
  and COMPATIBILITY.md carries a dated drift note (pin numbers vs
  upstream main numbers, both read 2026-10-31).
- Reproducibility: IN PROGRESS.
- F2 fix: IN PROGRESS.
- Guest integration: IN PROGRESS (depends on Wave 2 Docker or a QEMU
  guest path).

## Wave 4: Hardening prep (no external spend)

Scope: SBOM for the v0.9.0 artifacts; agentos manifest and capability
parser robustness tests; security review scope pack; re-audit of every
open item, defining Wave 5.

- SBOM: GENERATED from the actual trees (cargo metadata for the unified
  kernel workspace and the agentos workspace): 162 packages, SPDX 2.3
  JSON, committed at docs/SBOM-thoxinux-0.9.0.spdx.json. Its root package
  carries the release EFI SHA-256, verified against the published asset.
- Security review scope: docs/SECURITY-REVIEW-SCOPE.md (RFP-ready; firm
  and budget remain a founder call).
- Parser robustness: IN PROGRESS (rides with the Wave 3 agentos lane).
- Wave 5 definition: PENDING the open-item re-audit at Wave 4 close.
