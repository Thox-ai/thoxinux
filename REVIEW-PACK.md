# ThoxInux Review Pack: D14 Execution Run (FINAL, with evidence-lane corrections)

Date: 2026-10-31 (America/Chicago). Executor: Sadie CAO coordinator run under
Tommy's D14 order ("Go with your recommendations, proceed, do not stop looping
until it is finished and ready for my review"). This final version incorporates
the evidence lane's correction supplement, which supersedes the interim
numbers in the draft pack.

Status legend: PROVEN means run and observed in this run. RECORDED means a
preserved historical record, not rerun. BLOCKED means a named external blocker
with evidence. OPEN means remaining work, listed honestly.

## 1. What was built

- ThoxInux monorepo: ttracx/thoxos-ginux (private) transformed in a working
  copy into the plan layout: `kernel/ginux` (was module-ginux), `boot/ssd`
  (was ssd-module), `userspace/ginux-edition` (was ginux-edition),
  `userspace/agentos` (thox-agentos adopted, see section 5), plus new
  `thoxbeam/` (interface only), `sdk/`, `docs/deployment-azure` (was azure),
  `evidence/`. Git history preserved. ttracx/thoxos-ginux untouched as the
  archive of record.
- ONE unified patch series against upstream Ginux at the pin
  36503bda2d87465765e1b94e65f9d100f27ed5be: kernel-startup, thox-identity
  (hand-merged from the two conflicting identity patches), qemu-tools,
  registry-anchor. The identity conflict between the two parent lines is
  resolved; the surviving difference (hosted systemd target vs minimal
  target) is a runtime boot-profile choice, documented in
  docs/RECONCILIATION-2026-10-31.md. Legacy patch sets preserved under
  patches-legacy-* directories.
- Payload U (the unified build): built, SHA-256 85722bd4..., consolidation
  commit 905a15d.
- Root documentation set per Repository Creation Standard v1.0: README,
  LICENSE (Apache-2.0), NOTICE.md, UPSTREAM.md, RIGHTS.md, START_HERE.md,
  docs/USER_GUIDE.md, docs/QUICKSTART.md, docs/DEVELOPMENT.md,
  docs/THREAT-MODEL.md, docs/COMPATIBILITY.md,
  docs/RECONCILIATION-2026-10-31.md, docs/previews/, .agents/HANDOFF.md.

## 2. Founder gate at the top: the public name-holder repo

`Thox-ai/thoxinux` ALREADY EXISTS and is PUBLIC. It was created
2026-10-31T22:42:38Z, during this run, by a parallel lane: a single
"Initial commit" with a stub README, no releases (verified by Sadie:
root contains README.md only). This run did NOT touch it: no push, no
visibility change, per the standing rule that visibility and public content
changes need Tommy's explicit order.

- This run's staging home is `Thox-ai/thoxinux-staging` (PRIVATE),
  collaborators sadiethox and cross80127.
- Decision needed from Tommy: replace the stub's contents with this run's
  tree, merge, or rename the staging repo into the name. Nothing about the
  public repo changes until he rules.

## 3. Kernel and compatibility (Phase 0)

- Syscall audit, three independent counts plus upstream's own checker,
  doc and source agree **at the pinned commit 36503bda**: 82 Complete /
  245 Partial / 48 Policy-denied / 0 Unsupported / 0 Missing of 375
  dispatched. The plan's 53/257/48/17 figures describe upstream **main**
  (which has moved since the pin), not the pin. The original brief's 82/245
  was right for the pin but omitted the 48 Policy-denied. Full record:
  docs/COMPATIBILITY.md. Any public copy must state which commit its
  numbers belong to.
- Dispatcher at the pin is the monolithic kernel/src/arch/x86_64/cpu.rs.

## 4. Evidence rerun (KnightHub, QEMU 10.2.1, OVMF 2025.11)

Payload labels: B = October 28 research line, A = Azure candidate,
R = A-equivalent rebuild (see caveat), U = unified ThoxInux build,
E = ginux-edition tree.

| Suite | Result this run | Payload |
|---|---|---|
| Launcher pytest | 10 passed | B |
| Module pytest total | 17 passed + 3 subtests (launcher 10 + source_preparation 7) | B |
| Upstream library tests | 53 passed | B |
| Module lifecycle (QEMU) | **22/22 passed under TCG; 22/22 again under KVM** | R |
| SSD pytest | 15 passed (the historical claim, confirmed) | B |
| Edition pytest | **171 passed, 2 skipped** after one environment-fix loop (first run 163 passed / 8 failed / 2 skipped as an unprivileged user; all 8 failures proven environment-caused: the entrypoint assumes root + a `thoxos` user, which was created on KnightHub to mirror the Dockerfile; reversible via userdel) | E |
| Azure unit checks (120) | NOT rerunnable: self-contained guest payload, generator absent from the repo. Record preserved, not re-claimed | A (record) |
| thox-agentos cargo test | 9 passed, 0 failed, 3 runs identical | agentos |

Payload provenance caveat: Payload A's EFI is not in the clean clone
(artifacts are gitignored except receipt, checksums, license, notice), so A
itself was not booted. The 22/22 lifecycle runs used Payload R, a same-day
rebuild found in the kernel-team clone (SHA-256 79679992..., 12,506,624
bytes) whose upstream commit and all three patch hashes match Payload A's
receipt exactly (kernel-startup ca19175f...), but which is not
byte-identical to A. The 22-command lifecycle claim is PROVEN for the
A-equivalent payload, with the byte-identity caveat recorded here.

Environment lessons recorded: (1) QEMU runtime state must live on WSL-native
ext4, not /mnt/d: a 64G volume create on drvfs stuck 17+ minutes in
uninterruptible D state and QEMU never started; the rerun on ext4 passed
22/22 with evidence copied back to /mnt/d. (2) The handoff claim that
`aw-bits=48` is load-bearing conflicts with upstream's run.sh passing no
aw-bits argument in either passing run; QUICKSTART.md's QEMU profile
section is to be annotated with that discrepancy rather than asserting
aw-bits as proven.

## 5. Minimal-domain start failure: root cause (CORRECTED, Phase 0 exit met)

The draft pack's interim framing (a QEMU 8.2.2-era environment issue) is
SUPERSEDED by the evidence lane's proven root cause: **the patch set, not
the environment.** Payload B was banner-only over pristine upstream
36503bda, and pristine upstream failed identically on QEMU 8.2.2. The
kernel-startup patch (auxv stack-layout overlap after AT_SYSINFO_EHDR;
linux-system-init.S mount expectation EPERM to EFAULT; plus restart,
console and TCP fixes documented in the repo's own DIAGNOSIS.md) makes the
same environment pass, and the patched payload passes on QEMU 10.2.1 /
OVMF 2025.11 under both TCG and KVM. QEMU version, OVMF, accelerator and
RAM are all excluded as explanations. The minimal-domain start is
exercised directly in the suite and passes for the patched payload. The
unified series carries kernel-startup, so it addresses the failure by
construction; the direct lifecycle run against Payload U (run2) is the one
remaining confirmation to collect and is listed as OPEN, not claimed.

## 6. thox-agentos (Phase 0 adoption, Phase 2 loop)

- cargo build PASS, zero warnings. cargo test 9/9 integration tests pass
  (identity refusal, capability denial for fs/exec/network, audit
  monotonicity, model swap and rollback, supervisor restart policy).
- Live daemon smoke on KnightHub host (native filesystem state dir): full
  pass. Supervisor up, reporter agent identity-verified and autostarted,
  broker-mediated fs.read calls granted and audit-logged, stop/start/reload
  verified, model slot surface present (model show/swap/rollback).
  Environment: host demonstration. Guest integration is OPEN (blocked with
  the Docker path, section 7) and is not claimed.
- Real bug found and fixed (F1): the daemon autostarted agents before
  binding its control socket, orphaning them on bind failure. Fix carried
  into the adopted copy; tests still 9/9.
- Open bug documented (F2): daemon SIGTERM does not stop supervised agents;
  mitigated under systemd (control-group kill), bare runs are not.
- One further documented finding (F3) concerns socket behavior on drvfs,
  the same filesystem class as the QEMU volume lesson in section 4.
- Adopted into userspace/agentos with LICENSE, NOTICE.md,
  .agents/HANDOFF.md and a captured-output preview added.

## 7. Unified build, boot, release (Phase 1)

- Payload U built from the consolidated tree (SHA-256 85722bd4...),
  consolidation commit 905a15d pushed to private Thox-ai/thoxinux-staging.
- **Draft release v0.9.0 exists on thoxinux-staging with GINUX.EFI +
  SHA256SUMS assets, verified DRAFT** (Sadie readback: isDraft true;
  repo tree 555 entries). Release notes state: experimental, Secure Boot
  off posture (D14), QEMU/KnightHub evidence scope, physical install not
  accepted, MeshStack and ThoxKey firmware proprietary and not included.
- Docker demo path: BLOCKED. The Docker daemon on KnightHub WSL gives no
  server response. The native build path was used instead; substitution
  recorded per plan. This also blocks the host-image build.
- SSD image and QEMU USB-disk bench: NOT RUN. Blockers are precise: no
  build/ directory and no .img/.vhd anywhere in ginux-edition, and the
  wrapper needs Docker twice. The historical in-repo log showing 6 bench
  markers passing was NOT re-verified and is not claimed. Physical write
  was never attempted or authorized; the acceptance checklist is ready in
  boot/ssd.
- Reproducibility (two clean builds, hash comparison): NOT evidenced in
  the run's reports. OPEN. Historical builds were not byte-reproducible;
  no reproducibility claim is made for Payload U.

## 8. Repository state

- Staging: https://github.com/Thox-ai/thoxinux-staging (PRIVATE, verified)
- Public name-holder: https://github.com/Thox-ai/thoxinux (PUBLIC stub,
  README only, not touched by this run; Tommy's call, section 2)
- Archive of record: https://github.com/ttracx/thoxos-ginux (untouched)

## 9. Remaining founder gates

1. Thox-ai/thoxinux public stub: replace, merge, or rename (section 2).
2. Public flip of the real tree: only on Tommy's explicit order after review.
3. Named spare SSD for physical install acceptance.
4. Azure subscription for deployment (both variants stop at the credential gate).
5. Phase 3 independent security review: firm and budget (out of scope by D14).
6. Secure Boot signing: v0.9 ships explicitly unsigned (D14); signing is Phase 2 work.
7. Docker daemon on KnightHub WSL: revive or replace; it gates the demo
   path, the host-image build, and the SSD bench.

## 10. Known defects and open items, carried openly

- F2: thox-agentd SIGTERM orphans supervised agents outside systemd.
- Payload U direct lifecycle run (run2) not yet collected (section 5).
- Reproducibility of the EFI build unproven (section 7).
- Docker-dependent paths unproven this run (section 7).
- aw-bits=48 documentation discrepancy to annotate (section 4).
- No physical hardware validation of any ThoxInux artifact exists yet.
