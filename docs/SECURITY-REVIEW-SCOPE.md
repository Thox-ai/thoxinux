# Security Review Scope: ThoxInux

Prepared by: THOX.ai (Sadie Weaving, Chief Agentic Officer)
Date: 2026-10-31
Status: RFP-ready scope. Engagement, firm selection, and budget are a
founder decision (Tommy Xaypanya, CTO). This document scopes the work so
any qualified firm can bid against it without further discovery calls.

## 1. Why this review exists

ThoxInux is an Apache-2.0 fork of Ginux, an independent Rust-first x86-64
kernel that implements the Linux ABI as a personality and boots as a
single UEFI image. Upstream Ginux has never had an independent security
review. THOX intends ThoxInux to become the open kernel story for ThoxOS
and, only after this review and hardware validation (Phase 3 of the
release plan), a candidate for production device use. Until then every
ThoxInux artifact is labelled experimental. This review is the gate
between "engineering preview" and any production claim.

## 2. Assets in scope

All assets are public or provided at engagement start; no proprietary
THOX components are in scope (see section 7).

| Asset | Location | Notes |
|---|---|---|
| Kernel fork (Ginux at pin 36503bda plus THOX patch series) | github.com/Thox-ai/thoxinux, `kernel/ginux` | Patch series: kernel-startup, thox-identity, qemu-tools, registry-anchor. Both the THOX patches and their interaction with upstream code are in scope; upstream code as a whole is in scope for the surfaces in section 3. |
| Boot and installer | `boot/ssd`, `kernel/ginux/scripts` | External SSD image builder and writer tooling, including its target-refusal guards. |
| Agent runtime (thox-agentos) | `userspace/agentos` | Supervisor (thox-agentd), signed agent manifests (ed25519), tool broker, capability policy, audit log, model slot. |
| Userspace edition | `userspace/ginux-edition` | Docker demo path, host image build, guest shell tooling (`thox` commands). |
| Release artifacts | v0.9.0 release: GINUX.EFI, SHA256SUMS | Plus the SBOM at `docs/SBOM-thoxinux-0.9.0.spdx.json`. Build reproducibility status is documented in docs/WAVES.md. |

## 3. Surfaces and questions the review must answer

1. **Domain and capability enforcement.** Ginux domains carry
   generation-tagged capability tables and the controller runs in ring 3.
   Can any sequence of syscalls from an unprivileged domain create,
   escalate, or resurrect kernel authority? Are generation checks
   complete on revocation paths?
2. **Syscall surface.** 375 dispatched syscalls at the pin (82 Complete,
   245 Partial, 48 Policy-denied, 0 Unsupported; docs/COMPATIBILITY.md).
   The Partial set is the concern: identify Partials whose incomplete
   semantics are exploitable (length checks, TOCTOU, sign extension,
   unchecked user pointers), and verify the 48 Policy-denied syscalls
   cannot be reached through alternate numbers, compat paths, or the
   non-syscall ABI surface (23 surfaces scored in the pinned ledger).
3. **Memory safety boundaries.** The kernel is Rust; audit the `unsafe`
   surface, the identity-map and page-table setup at EFI boot, and the
   auxv stack construction (a real defect lived here; see
   docs/RECONCILIATION-2026-10-31.md and the kernel-startup patch).
4. **Agent runtime.** Manifest signature verification (offline ed25519),
   capability parsing and enforcement in the broker, audit log integrity
   (append-only claims, monotonicity), supervisor lifecycle handling
   (agent containment on daemon shutdown; a defect here was found and
   fixed in Wave 3), and the model slot swap and rollback path. Threat:
   a malicious or compromised agent attempting host or peer-agent escape.
5. **Boot and install chain.** v0.9.0 ships unsigned with an explicit
   Secure Boot off posture (D14). Review the SSD writer's refusal guards
   (protected disk exclusion, target identity checks) for bypass, and
   assess the documented Phase 2 signing plan for soundness.
6. **Update and supply chain.** Patch-series hygiene against upstream,
   dependency inventory per the SBOM, release checksum verification, and
   the re-sync process described in the plan (monthly review, security
   fast-track).

## 4. What reviewers receive

- Full source at a named commit, with the patch series separated from
  upstream so THOX changes are reviewable in isolation.
- The evidence pack: REVIEW-PACK.md (D14 run), docs/WAVES.md (continuous
  wave ledger with per-suite results and payload labels), lifecycle and
  test suites in-tree, all runnable on QEMU (Q35, OVMF) with the
  documented profile.
- docs/THREAT-MODEL.md, docs/COMPATIBILITY.md, docs/RECONCILIATION-2026-10-31.md.
- A named THOX engineering contact and a 5-business-day response SLA for
  reviewer questions during the engagement.
- Test hardware profile: all current evidence is QEMU on KnightHub
  (WSL2). No physical hardware validation exists yet; a bare-metal phase
  can be scoped as a follow-on once a target machine is named.

## 5. Deliverables expected from the firm

1. Findings report with severity ratings, each finding tied to file and
   line at the reviewed commit, with a reproduction or proof sketch.
2. A specific verdict on the six questions in section 3, including
   explicit negative results ("we attempted X, it held") where a surface
   resisted.
3. Remediation guidance ordered by exploitability, distinguishing
   "fix before any production claim" from "fix in normal course".
4. Re-test of the production-blocking findings after THOX remediation,
   and a short public summary letter THOX may publish with the Phase 3
   exit report. (Publication of the summary letter is agreed in the
   engagement terms; findings themselves are delivered to THOX.)

## 6. Constraints and rules of engagement

- Testing is against QEMU images and source. No THOX production system,
  device, or third-party system is in scope or may be touched.
- No physical hardware testing in this scope; nothing in this engagement
  authorizes writing ThoxInux to any physical disk.
- Coordinated disclosure: findings are confidential to THOX until the
  remediation re-test, after which THOX publishes its Phase 3 report;
  embargo terms are set in the engagement contract.
- The review covers the open ThoxInux tree only. It is not a review of
  ThoxOS as a whole.

## 7. Explicitly out of scope (proprietary, by design)

MeshStack (closed plugin over the domain and control ABI), ThoxKey
firmware and secure boot keys, ThoxWork, and non-Apache-2.0 model
weights. The public line, stated on every surface: "ThoxOS Core is open.
MeshStack and ThoxKey firmware are not." Reviewers get the ABI the closed
components speak to, not the components.

## 8. Known open items at scope time (honest starting point)

Maintained live in REVIEW-PACK.md sections 9 and 10 and docs/WAVES.md.
At this writing they include: no physical hardware validation; EFI build
reproducibility under measurement (Wave 3); agentOS guest integration
evidence limited to the environments named in the wave ledger; the
48 Policy-denied posture verified by construction and test, not yet by
independent review (that is this engagement).
