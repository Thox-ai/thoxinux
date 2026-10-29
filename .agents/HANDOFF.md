# Current Azure Compute lane

Read [AZURE_HANDOFF.md](AZURE_HANDOFF.md) for the current kernel, Azure variant and evidence. The remaining content is the preserved Oct28 predecessor record.

# Standalone repository migration

Owning standalone repository: `ttracx/thoxos-ginux`, private. GitHub repository ID1437922846; owner and push permission were verified after Tommy supplied the new URL. Requested by Tommy after the original module review. The following original handoff is retained as historical source provenance and operational limits. The standalone root now contains `module-ginux/`, `ssd-module/`, `docs/`, `evidence/` and `.agents/`. References to `ports/ginux/` below identify the predecessor module location. Repository creation is verified. The initial remote import must receive an exact branch-head and file-blob readback before marking the push verified. Local prepared source history ended at `944314da2114c41335265a53852eb9b09c0e21b2`; connected GitHub API import creates its own remote commit chain. Preserve this mapping rather than claiming the local and remote commit IDs match.

# THOX Ginux research handoff

Internal. Prepared 2026-10-28 America/Chicago by the current ChatGPT/Codex session for Tommy Xaypanya. This is source continuity and queued work, not an acknowledgement from another runtime.

## Predecessor baselines and ownership

- Owning repository: `ttracx/thoxos-desktop-debian`, base `1385e9780fea4023f8e73b897ce8140d3dae3d96`. New isolated port only. Preserve the existing desktop and NiceC0re image lanes.
- Active implementation source reviewed: `ttracx/thoxos-vibe-rust` main `e912d82ad9d8e3475a945039b5f16228c9a4bf56`. Preserve `fix/offline-dualboot-knighthub-20261025` and its owner.
- Ginux upstream: `gmkurtzer/ginux` `36503bda2d87465765e1b94e65f9d100f27ed5be`, Apache-2.0. Only source modification is the research banner; no ABI, prompt, capability or driver guard was removed.
- Repository policy: `ttracx/thox-brain` `f03e8d951dd12d7a4a916bd2ad51e4fa887b8332` plus current closeout source `ttracx/thox-handoffs` `10febc7daff03665faa30c2d621ff7a32c8f0ad0`. Hash/load receipt is `evidence/policy-load.json`. This current session loaded the policies; external runtime activation is unclaimed.
- Current local review colleagues: Ginux source reviewer, packaging implementer, platform/SSD implementer and documentation reviewer. Independent source review is attributed to that session colleague, not to Sera, Claude or another external persona.

## Delivered behavior and evidence

The tested EFI is 12,497,920 bytes, SHA-256 `4fd25157b9f0348346a56fcb3e8d51d29414094f0f3aaa533ffddb52932e69e8`. Its build receipt SHA-256 is `182dedf18e3e91468ef58f455010d8dfdf6920ae518b02eb18c8ec8f045b4977`. Binary bytes are in the hashed installation ZIP and authenticated archive, not a speculative Git download. `module-ginux/artifacts/` retains the receipt, checksum inventory and upstream license/notice.

Native QEMU TCG 8.2.2 and OVMF 2024.02: THOX banner, status, components, domain list, help, clean shutdown and configuration recovery across a separate reboot passed. Use 2 GiB RAM, one vCPU and explicit `intel-iommu,intremap=off,aw-bits=48`. QEMU defaults39bit and fails Ginux's48bit contract. A4GiB attempt fails EFI identity-map placement. These findings justify launcher constraints, not kernel guard removal.

Nine upstream library packages passed53 unit tests. Launcher10 tests and SSD15 tests passed. ShellCheck/Bash/Python checks passed. Actual payload verification and ordinary-file staging passed. Fixture source clone/overlay tests passed; they are not a full image build. See `evidence/VALIDATION_SUMMARY.json`, module tests, SSD evidence and the eight-page HTML/PDF guide.

Embedded minimal Linux domain start fails with `minimal system init execution failed`. The pristine upstream EFI (SHA-256 `524d2d83c8e2d086819def18820981093cb41b501546313f8903217d183a2645`) reproduces the same failure in this environment. Upstream controller-console gate also fails there. Preserve failures and diagnose before broader Linux-userspace claims. `cargo test --workspace` is unsupported by the freestanding boot binary and fails E0152; the named library tests are the actual53-test result.

A restored-source rebuild produced different EFI bytes; no byte-reproducible build claim is made. Distribution tags/package resolution are not immutable. The installed ZIP retains the originally tested payload and receipt. Rebuilds need their own hashes and acceptance.

## Holds and precise blockers

- Docker executable/daemon absent in this execution environment: Docker recipe and KVM override reviewed, execution not run.
- Full Linux host image not built: existing pipeline needs125GiB free and Docker; workspace has about28GiB free. Builder prepares an independent pinned checkout, stages the verified guest, runs existing tests/build when requested, and records its overlay hashes.
- Fresh-media writer mismatch: Vibe dual/btrfs layout is not admitted by the bundled unchanged NiceC0re two-part/ext writer. Generic Vibe alternatives were reviewed and have inadequate current target-identity/readback guards. Do not bypass any refusal. Existing accepted external Linux hosts can use the postboot installer now.
- KnightHub remote device inventory reports offline. No physical target was selected or written, no firmware changed, no reboot performed. GPU, Secure Boot, CUDA, KVM and physical USB SSD behavior remain unqualified.
- Root canonical repository checker not run: this API-based scoped candidate is not a full authenticated local checkout. Module validation is not whole-repository certification.
- This is a private draft candidate. No merge, stable release, public website publication, production deployment or fleet activation is claimed.
- Native saved-memory/live graph tools are unavailable. This file and source-bound receipt provide additive repository continuity only.

## Named pickup assignments

| Lane | Task and inputs | Exit evidence | Stop condition |
|---|---|---|---|
| Hermes | Acquire an authorized Linux build host with Docker and125GiB free; use this exact source and guide | Docker image build/run log and full host-image receipts | No physical write/reboot from an unresolved target |
| Codex / Nova | Diagnose pristine-upstream domain panic and run full image/VM acceptance on the owning branch | Exact base/head, commands, payload hashes and actual results | Never disable guards to pass |
| Claude | Independently review only this additive port and matched image/writer work | Source, license, integrity, storage-refusal and acceptance review | No merge or image admission without evidence |
| Kai | Once KnightHub is online, inventory hardware and externalSSD read-only; qualify matched media later | Exact target plan, authorized erase confirmation, full readback, real UEFI/GPU/persistence evidence | Never write Windows/system/protected/ambiguous storage |
| Muse | Maintain evidence-matched captions using the supplied authentic transcript and guide | Revised HTML/PDF after new actual results | No production/physical claims from fixtures |
| Samuel / Julian | File internal docs under owning repo docs/ginux-research and port guide | Verified internal links and artifact hashes | Keep agent files and template masters out of customer downloads |
| Clara / Sera | Review brand and public claims before external use | Exact tagline/brand and evidence boundaries checked | No public publication or invented certification |
| Sadie | Finish factual Outlook copy delivery after source/archive verification | Verified sender, recipients, Sent Items and attached kit metadata | No substitute mailbox; unknown sends reconciled before retry |

These are prepared assignments. External lanes have not supplied acknowledgements in this session.

# Second record: ginux-edition (Claude runtime, Odette Lark)

Added 2026-10-29 on branch `ginux-edition-0.1.0`. This section is additive; the record above is unchanged and keeps its own provenance.

- Location: `ginux-edition/` (own README, docs, handoff at `ginux-edition/.agents/HANDOFF.md`, lane assignments at `ginux-edition/handoffs/LANES.md`).
- Scope: Ginux review, patches 0001-0003, ThoxOS userspace served over OCI from a local TLS registry, Docker demo (run and gated), KnightHub SSD disk image and writers, QEMU USB-disk boot harness.
- Comparison with the record above, including three items that need a ruling: `docs/RECONCILIATION_2026-10-28.md`.
- Do not merge claims across the two records. A lane quoting either one names which.
