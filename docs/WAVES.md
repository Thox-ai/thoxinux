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

## Wave 2: Docker, demo, SSD (complete 2026-10-31)

Scope: revive Docker on KnightHub WSL or prove it cannot run there; if
it lives, host-image tests, the Docker demo path end to end, the SSD
image build and the QEMU USB-disk bench.

- Docker: UP. The daemon answers (server 29.1.3, systemd docker.service
  active, in-distro Docker CE on Ubuntu 26.04 WSL2). It gave no server
  response at D14 and at wave start; it came up during the wave window.
  The diagnosis lane died on a transport error before filing, so the
  precise revival step is UNRECORDED; the state is verified, the story
  is not claimed. First Docker work then failed on a second, distinct
  cause: ~/.docker/config.json carried a Docker Desktop credential
  helper ("credsStore": "desktop.exe") that does not exist in-distro,
  breaking every registry fetch. Fix: config backed up, credsStore
  removed; proof pulls followed, including the Rocky base at the exact
  digest the Containerfile pins.
- Edition pytest: 171 passed, 2 skipped as root, matching the D14
  baseline exactly. As the unprivileged user: 163 passed, 8 failed,
  2 skipped; all 8 failures are in tests/test_entrypoint_environment.py
  and are host-privilege failures (the real entrypoint writes
  /var/log/thoxos-g-registry.log and runs usermod), not Docker failures.
  Correction to the D14 record: the consolidated tree has NO
  test_host_image.py; the D14 attribution of edition failures to that
  file and to the dead daemon does not match this tree. The suite here
  is 12 files, 173 tests.
- make test: cannot go fully green on this host today for two
  independent pre-existing environment reasons: the entrypoint tests
  need root (above), and as root shellcheck 0.11.0 stops the target on
  one info-level finding (SC2329, scripts/local-ci.sh:101; no
  .shellcheckrc in tree). No repo files were changed to chase either;
  both are carried to Wave 5 as an explicit decision item.
- make demo-image: PASS. Built thoxos-g/userspace:0.1.0 and
  thoxos-g/demo:0.1.0; the EFI inside the runtime stage verified by
  sha256sum -c (af58ecc721aef5dbd5a6cd3a39efe41ff161b74b3c23eaf259b8d27a9b31132b;
  this is the demo path's own build, a different binary from Payload U
  and labelled as such). The build exposed a real consolidation
  defect, fixed in this wave (see below).
- Consolidation defect found and fixed: consolidation commit 905a15d
  renamed the edition patch series to patches-legacy-edition/ but left
  docker/Dockerfile (COPY patches) and scripts/ginux-source.sh pointing
  at the removed patches/ path, so the demo image could not build from
  a clean tree. The coordinator's fix points both consumers and the
  test fixtures at patches-legacy-edition. Verified after the fix:
  edition suite 171 passed / 2 skipped as root, make demo-image exit 0
  with the in-build EFI checksum OK, make selftest reached the login
  gate. The lane's earlier local workaround (an uncommitted copy of the
  directory) was discarded.
- make selftest: PASS. Headless boot gate reached in order: Welcome to
  ThoxOS, the ThoxOS 0.1.0 Ginux Edition banner (Rocky Linux 10
  userspace), login prompt.
- make demo-shell: the interactive target refuses to run without a TTY
  (by design). Its documented headless equivalent, the demo image exec
  mode driving tests/e2e/shell_session.py, PASSED against the thoxos-shell
  domain on the Ginux kernel under QEMU/KVM: PRETTY_NAME, uname, thox
  status, thox version, id checks all ok. Literal guest output:
  thox version "0.1.0"; thox status os "ThoxOS 0.1.0 Ginux Edition",
  base "Rocky Linux 10", kernel "Ginux 6.12.0-ginux.0.1 (#1)", host
  "ginux", arch "x86_64", ai not configured.
- SSD image: PASS. make ssd-image produced
  thoxos-ginux-knighthub-0.2.0.img (8,589,934,592 bytes, SHA-256
  469b4f0c876eef78decb7c523e8cc1cb1dad4de0b377d8e53b293d39b0bb47f0)
  with manifest (target knighthub, headless, version 0.2.0). Assembly
  ran inside containers; no host loop devices. Both D14 blockers are
  cleared (Docker up; build/ exists with real artifacts).
- QEMU USB-disk bench: PASS, all six checks in order (kernel, root
  mounted, growroot, registry, dns, console), tty1 framebuffer
  captured. Runtime state on WSL-native ext4; the bench exercised a
  sparse 12G copy so first-boot root growth ran for real; the shipped
  image is unchanged. The historical 6-marker claim from the D14 pack
  is now re-verified, not just recorded.
- boot/ssd tooling: unit tests 15 passed; preflight runs clean.
  build_external_ssd.py was NOT run: it needs an assembled payload kit
  and the kit recorded in boot/ssd/evidence was staging-only with its
  ephemeral destination removed; no matching kit exists in the repo.
  Assembling a current kit from the unified build is carried to Wave 5.
  No physical disk was written at any point; install-to-ssd.sh was
  never run; writer refusal guards untouched.

## Wave 3: Reproducibility, agentos, docs (complete 2026-10-31)

Scope: two clean-tree EFI builds with SHA-256 compare; thox-agentd F2
SIGTERM fix with regression test; agentOS guest integration attempt;
QUICKSTART aw-bits annotation and COMPATIBILITY drift note.

- Doc corrections: DONE in commit 722c262 (see Wave 1).
- Reproducibility: PROVEN UNDER NAMED CONTROLS; not reproducible as-is.
  Two clean-tree builds of the unified procedure with no controls
  differ: 363 bytes in 7 clusters of a 12,507,648-byte EFI. Root
  causes, both measured: (1) the build generates a fresh registry root
  CA per build (random ECDSA keypair, random serial, build-time
  validity) and embeds it, so the network binary, initramfs, manifest
  digest and signature, and generated boot code all move; (2) the PE
  TimeDateStamp is wall-clock link time and the LLD RSDS debug GUID
  derives from it. With controls (SOURCE_DATE_EPOCH set to the pin
  commit timestamp 1793077647, a shared registry anchor, Payload U's
  own root PEM, and a fixed build path), two further builds are
  byte-identical (SHA-256
  1bc1c7af33470edc009fa5756d3fe6063573660e07e157d19397afc680a7bb89)
  and every intermediate matches Payload U's own intermediates
  byte-for-byte. Payload U itself can never be byte-reproduced after
  the fact: its CA was generated at build time and its timestamp was
  wall-clock; it differs from the controlled build in exactly 14 bytes
  (timestamp plus RSDS cluster). Release procedure consequence, carried
  to Wave 5: pin the anchor PEM and SOURCE_DATE_EPOCH for every future
  release build. Known wart found on the way: build-unified.sh exits 1
  on a legacy write-build-receipt.py banner step AFTER copying the EFI;
  carried to Wave 5.
- F2 fix (thox-agentd SIGTERM orphans supervised agents): DONE, merged
  in commit 1c06210. Mechanism: sigaction handlers for SIGTERM and
  SIGINT set an async-signal-safe flag; the accept loop is nonblocking
  and polls it; on shutdown the supervisor sends SIGTERM to each
  agent's process group, waits a bounded grace period (3 s default),
  then SIGKILLs survivors; the daemon writes a daemon.stop audit entry
  and removes its control socket. New regression suite
  tests/shutdown.rs: 5 passed. The 9 pre-existing integration tests
  still pass. Coordinator-verified by an independent cargo test run:
  23/23 integration tests pass (9 integration, 5 shutdown, 9 parser
  robustness from Wave 4 item 12, same merge).
- Guest integration: PASS in the Docker demo guest (container
  userspace), precisely labelled: a plain container from
  thoxos-g/userspace:0.1.0, entrypoint overridden, sharing the host
  WSL2 kernel. It is NOT a run on the Ginux kernel; AgentOS has not yet
  run under QEMU/Ginux (Wave 5 item). Adaptation: no systemd in the
  plain container, so thox-agentd ran in its own no-systemd
  development mode (scripts/run-dev.sh pattern; its header names this
  as the mode for the Ginux guest as well), seeded by the shipped
  first-boot-seed.sh unmodified. Proven inside the guest, from the
  audit log: supervisor up with the reporter agent autostarted; signed
  identity verified offline (identity.verify, allow); broker-mediated
  reads granted and audit-logged (tool.fs.read /proc/uptime and
  /etc/os-release, allow); three capability denials enforced and
  audit-logged (fs read outside granted roots, exec not in the
  allowlist, network egress not granted); stop and start lifecycle ok;
  and the F2 path live: SIGTERM to the daemon produced a clean exit 0
  with 1 supervised agent terminated and daemon.shutdown / daemon.stop
  audit entries, no agent processes remaining.

## Wave 4: Hardening prep (complete 2026-10-31, no external spend)

Scope: SBOM; parser robustness; security review scope pack; open-item
re-audit defining Wave 5.

- SBOM: DONE. docs/SBOM-thoxinux-0.9.0.spdx.json (SPDX 2.3, 162
  packages from cargo metadata over the unified kernel workspace and
  the agentos workspace as committed). Root package carries the
  published EFI SHA-256, verified against the release asset.
- Parser robustness: DONE, merged in commit 1c06210. The manifest
  parser was hardened, not only tested: 1 MiB manifest size cap,
  unknown fields rejected at parse time (deny_unknown_fields),
  duplicate entries rejected, top-level JSON object required. New
  suite tests/parser_robustness.rs: 9 passed, covering truncated,
  oversized, malformed, unknown-capability, duplicate, and
  overflow-value inputs; all error, none panic. (A cargo-fuzz run was
  not attempted; the deterministic corpus covers the named classes.)
- Security review scope: DONE. docs/SECURITY-REVIEW-SCOPE.md is
  RFP-ready: assets, six review questions, reviewer deliverables,
  rules of engagement, and the out-of-scope proprietary line. Firm and
  budget remain Tommy's call (hard gate).
- Open-item re-audit (REVIEW-PACK sections 9 and 10), closing state:
  public stub decision CLOSED (D15); public flip CLOSED (D15, Wave 1);
  run2 CLOSED (Wave 1); aw-bits annotation CLOSED (Waves 1 and 3);
  Docker daemon item CLOSED (Wave 2, including the demo path, the SSD
  image and bench, and the guest integration); F2 CLOSED (Wave 3);
  reproducibility CLOSED as reproducible under named controls, with
  Payload U's after-the-fact irreproducibility disclosed (Wave 3);
  parser robustness CLOSED (Wave 4). Still OPEN and founder-gated:
  named spare SSD for physical acceptance; Azure subscription; Phase 3
  firm and budget; Secure Boot signing (Phase 2 work under the D14
  posture). Still OPEN and engineering-owned: see Wave 5.

## Wave 5: defined at Wave 4 close (engineering-owned, no hard gates)

1. Encode the reproducibility controls into the release procedure:
   build scripts take the anchor PEM and SOURCE_DATE_EPOCH by default
   from the pin; fix or retire the legacy write-build-receipt.py
   exit-1 wart so builds exit 0; cut v0.9.1 from a controlled build and
   publish the verification hash beside it. In the same pass, move the
   demo image onto the unified patch series (it currently builds the
   legacy edition series by design of its consumers) or record the
   decision to keep the split, with reasons.
2. make test green decision: resolve the two environment findings as
   repo policy (a .shellcheckrc disposition for SC2329 or a script
   fix; the entrypoint tests documented as root-required or marked),
   so the suite's green state does not depend on who runs it.
3. Assemble a current boot/ssd payload kit from the unified build so
   build_external_ssd.py is exercisable again, and run it end to end
   against image files only.
4. Upstream re-sync evaluation against the pin: diff 36503bda to
   current upstream main for the dispatcher and ABI surfaces the THOX
   patch series touches; recommend re-sync or hold, with a fresh
   syscall audit as the price of any re-sync.
5. AgentOS on the Ginux kernel guest (QEMU): repeat the Wave 3 guest
   loop inside the actual kernel userspace (the run-dev.sh mode exists
   for exactly this), labelled separately from the container proof.
6. ARM64 scoping document (v1.1): what the x86-64 ABI layer means for
   a port, measured effort drivers, decision inputs for Tommy.
7. Installer dry-run hardening: boot/ssd installer exercised in
   dry-run mode against image files and loop devices only; extend the
   refusal-guard test set; guards themselves unchanged.
8. Evidence hygiene: the lifecycle suite's lifecycle-results.json
   hardcodes its profile string as "QEMU TCG" even for KVM runs; make
   the record name the accelerator actually used.

## Wave 5: results (complete 2026-10-31, item 5 closed as a proven kernel blocker)

1. Controlled-build release procedure and v0.9.1: DONE (commits
   bef51fd, 8943889). upstream.env pins GINUX_SOURCE_DATE_EPOCH=
   1793077647 (the pin commit timestamp); build-unified.sh exports
   SOURCE_DATE_EPOCH from the pin unless caller-set, and defaults to
   the pinned in-repo registry anchor (kernel/ginux/registry-anchor/
   thoxos-local-root.pem, cert-only, SHA-256 8ba5d94f...) instead of a
   fresh per-build CA; THOX_BUILD_FRESH_CA=1 is the development
   opt-out. write-build-receipt.py records identity_patch_sha256
   instead of the nonexistent legacy banner patch; builds now exit 0
   (three verification builds, all exit 0). Procedure documented in
   kernel/ginux/docs/RELEASE-BUILD.md. Reproducibility proven with
   one correction to the Wave 3 record: two new-default builds at a
   fixed non-canonical path were byte-identical to each other
   (965791ad...) but differed from the Wave 3 controlled hash in
   exactly 8 bytes, one cluster at offset 1652532-1652539, the first
   8 bytes of the RSDS debug GUID. A third build at the canonical
   Wave 3 path (/mnt/d/thoxinux-build/repro/run-fixed/src) reproduced
   1bc1c7af33470edc009fa5756d3fe6063573660e07e157d19397afc680a7bb89
   exactly. Conclusion: the absolute build path leaks into the EFI
   through the RSDS GUID (a hash over linker debug data embedding
   absolute paths), a channel the Wave 3 strings scan could not see;
   same-path is a hard control and RELEASE-BUILD.md now records it.
   v0.9.1 PUBLISHED as a public pre-release at
   https://github.com/Thox-ai/thoxinux/releases/tag/v0.9.1 with
   GINUX.EFI (the canonical-path bytes, 1bc1c7af...), SHA256SUMS and
   build-receipt.json beside it; the asset was downloaded back
   anonymously and hash-verified. v0.9.1 differs from Payload U only
   in the 14 build-control bytes (TimeDateStamp plus RSDS cluster)
   measured in Wave 3; it was not separately lifecycle-run and the
   release notes say so. Demo image decision: KEEP THE SPLIT. The
   demo PKI is per-build by design (its registry TLS leaf is signed
   by a fresh root embedded in the demo EFI) and cannot sign under
   the pinned unified anchor, whose private key does not exist; the
   legacy series also carries different identity and startup
   semantics, and the edition suite (173 tests) is pinned to it.
   Revisit only as a designed PKI and identity migration.
2. make test green policy: DONE (commit fa0921d). SC2329 at
   scripts/local-ci.sh:101 is a false positive (the function is
   invoked through run_step dispatch, which ShellCheck cannot
   follow); disposition is a scoped userspace/ginux-edition/
   .shellcheckrc disabling SC2329 only, with the reasoning in its
   comments, no script change. The entrypoint environment tests are
   now marked root-required in code (skipif on euid, reason naming
   the /var/log write, usermod and setpriv) and documented in the
   edition DEVELOPMENT.md. Verified: as root, make test exits 0
   (pytest 171 passed, 2 skipped); as the unprivileged user, make
   test exits 0 (163 passed, 10 skipped, the 8 entrypoint tests
   skipping with the stated reason). Green no longer depends on who
   runs it. Coordinator re-verified the root run on the merged tree:
   exit 0, 171 passed, 2 skipped.
3. boot/ssd payload kit: PARTIAL, with the build half blocked on
   host disk space (commit b1e600f). The kit format was recovered
   from install_host.verify_kit (a module-ginux directory: artifacts
   GINUX.EFI, GINUX_LICENSE, GINUX_NOTICE, build-receipt.json,
   SHA256SUMS, plus scripts/run-vm.sh; the kit carries no userspace,
   which the builder clones from its pinned host source). A current
   kit was assembled from the unified build (Payload U artifacts)
   by the committed assembler boot/ssd/assemble_payload_kit.py; the
   kit itself lives on disk at /mnt/d/w5-c-kit (the EFI is already
   the published v0.9.0 asset; binaries stay out of git). One honest
   caveat recorded in the kit receipt: no build-time receipt exists
   for Payload U (the D14 receipt step failed on the legacy banner
   filename after copying the EFI), so the assembler generates a
   receipt of kind wave5-kit-assembly binding only measured hashes.
   The kit passes the real verify_kit. build_external_ssd.py
   prepare: PASS, exit 0 (all four pinned blobs verified, kit staged,
   status prepared-not-built; the same prepare under /mnt/d did not
   finish in 20 minutes on DrvFs, on ext4 it takes seconds). The
   full --build is BLOCKED: command 1 of 2 (cargo test --workspace)
   exited 101 when the KnightHub root filesystem hit 100 percent
   (11 GiB free at start, the debug target alone grew to 11 GiB; ld
   died with bus error, no space left). The 125 GiB gate measures
   only the --out filesystem while the cargo target and Docker
   volumes live on the root; at close-out the root had 0 bytes free.
   No .img was produced by this path and none is claimed. Unblock:
   about 40 GiB free on the root, or relocate the cargo target and
   Docker data root to a /mnt/d-backed volume, then rerun. Carried
   to Wave 6. Also recorded: the Wave 2 edition SSD image file no
   longer exists on disk (logs and summary only); its recorded hash
   stands unverified-again, and the previous output of the pinned
   external builder (2026-10-25) was layout-verified read-only in
   this wave (36,508,287,488 bytes, GPT 1 GiB ESP, 24 GiB root
   x86-64, 1 GiB xbootldr, 8 GiB root ARM-64).
4. Upstream re-sync evaluation: DONE, recommendation HOLD (commit
   1fb3e57, docs/UPSTREAM-RESYNC-EVAL.md). Upstream main is
   759cf2e221b459b0195c3fa7ed909688b755e74e (2026-10-31), 138 commits
   past the pin, 330 files changed (about half of them upstream gate
   evidence data). The dispatcher was restructured: the monolithic
   cpu.rs (44,324 lines at the pin) is now 42,752 lines plus a new
   cpu/ submodule (9 files, 8,237 lines; linux_abi.rs holds all 375
   constants, linux_syscall.rs the dispatch). ABI contract surfaces
   did not move: services/protocol, crates/protocol-state and
   crates/native-abi are unchanged. Patch dry-runs on pristine main:
   thox-identity APPLIES CLEAN; thox-registry-anchor APPLIES CLEAN
   with offsets; thox-kernel-startup CONFLICTS (5 of 8 files);
   thox-qemu-tools CONFLICTS (1 of 4 hunks). Fresh syscall audit at
   main, same method as at the pin, four counts agreeing: 53
   Complete / 257 Partial / 48 Policy-denied / 17 Unsupported of 375;
   the table size and number set are identical to the pin, and all
   29 status changes are re-scoring (the socket family to Partial,
   17 obsolete calls to Unsupported), zero dispatch lost. Decision:
   hold the pin for v0.9.1 and Wave 5; run the re-sync as its own
   wave (Wave 6 item 1) with full lifecycle re-proof, on the monthly
   cadence or sooner on a security fix, a defect hit, or about 150
   more upstream commits.
5. AgentOS on the Ginux kernel guest: BLOCKED on a proven kernel
   defect, AgentOS exonerated (commit f32251c, evidence in
   evidence/wave5-lane-e/). Route: agentos binaries baked into a
   variant demo image (thoxos-g/demo-agentos:0.1.0-w5e from the
   Wave 2 demo image, same EFI lineage) and booted under QEMU/KVM
   on the real Ginux kernel (6.12.0-ginux.0.1; guest EFI SHA-256
   21d12d86631df7947a9bd7389b664106676c6f97a18e44d38d9ddb906b00f7b4,
   which supersedes the af58ecc7 figure in the Wave 2 summary
   because the demo image was rebuilt in this wave's window).
   Progress past the Wave 3 container proof: an ELF blocker was
   found and fixed by build flag only (Ginux's relocatable exec plan
   rejects default Rust binaries, rejection code 7; upstream
   parse_relocatable requires exactly one PF_WRITE PT_LOAD;
   RUSTFLAGS -z norelro fixes the layout; no source or policy
   changes). thox-agentd then ran in-guest: socket present,
   thox-agent list and status OK. The loop could not be completed:
   with the daemon and reporter resident and writing state, the
   domain faults at the next process-lifecycle activity across 17
   attempts in both domains (three kernel signatures recorded
   verbatim in the evidence: fatal exception vector 8 with
   GINUX_KERNEL_PANIC; a Linux user fault at an identical RIP in
   both domains; and a resume FS mismatch ending in domain marked
   failed, including one death inside a 25-second idle window and
   one where systemd started the daemon unit cleanly and the domain
   still failed when the loop unit started). Bisects exonerate
   AgentOS and the harness: fork/exec, redirects, script sizes and
   Python-to-agent exec all pass in-guest, and the system domain
   boots cleanly to graphical.target on the same image until the
   daemon tree is resident. In-guest audit excerpts were never
   captured because the domain died before the audit dump step in
   every attempt; the Wave 3 container audit proof remains a
   container proof and is not restated as this result. Candidate
   unblocks and the rerun harness (harness/w5_session11.py) are
   recorded in the evidence RESULTS.md: an upstream fix to domain
   snapshot/resume bookkeeping for resident state-writing daemons,
   or AgentOS state on non-snapshotted storage if a future edition
   provides it. Carried to Wave 6, gated on the re-sync.
   Secondary finding: the shipped first-boot-seed.sh cannot run
   in the shell domain (bash command substitution returns empty
   there); the baked seed was produced by the same script in the
   variant container with guest paths, unmodified logic.
6. ARM64 scoping: DONE (commit 1fb3e57, docs/ARM64-SCOPING.md).
   Measured at upstream main 759cf2e2: one arch only (arch/x86_64,
   18 files, 60,224 lines, 54 percent of kernel/src), plus 20
   x86-64 assembly files (14,673 lines) and 17 files outside the
   arch tree still referencing x86_64; roughly 75,000 lines define
   the machine contract. The toolchain is not a blocker (Rust
   1.99.0 ships aarch64-unknown-uefi; only build wiring is x86-only)
   and the host test story exists (qemu-system-aarch64 plus AAVMF on
   KnightHub). The aarch64 Linux ABI uses the asm-generic syscall
   table, so the 375-entry table and ledger are re-derived, not
   carried. THOX identity and registry-anchor patches are portable
   as-is; kernel-startup splits. Effort sized relatively per
   component in the doc; the five decision inputs for Tommy are
   listed there, target hardware class first. No dates or
   commitments stated.
7. Installer dry-run hardening: DONE (commit b1e600f). Finding:
   no dry-run mode exists (install_host.py rejects --dry-run at
   argparse, exit 2; the edition install-to-ssd.sh rejects it,
   exit 1); none was added in this wave. The closest non-writing
   paths were exercised: preflight clean; install_host.py
   --stage-root with the real kit exits 0 (staging_only true,
   physical_write false, 9 files); native install refused without
   sudo; and the install-to-ssd.sh refusal matrix as root against
   image files and loop devices only, every case refusing before
   any write (not root; regular file as device; nonexistent
   device; loop without --allow-internal; undersized loop; wrong
   confirmation token, with the backing file hash verified
   unchanged; the running root disk, caught by the mounted
   filesystems guard). boot/ssd tests grew 15 to 32, all passing
   (14 new GuardRefusalTests driving real guard code, 3
   KitAssemblyTests); coordinator re-verified 32 passed on the
   merged tree. Guard logic was not modified anywhere. One guard
   observation documented, not fixed: under WSL the root-disk
   derivation in install-to-ssd.sh never fires (empty PKNAME), and
   the mounted-filesystems guard catches the target instead;
   defence in depth held.
8. Evidence hygiene: DONE (commit 8b11ee7). acceptance_lifecycle.py
   now resolves the accelerator exactly as the run does (QEMU_ACCEL
   env validated, else the same auto-detection as run.sh) and
   lifecycle-results.json records accelerator, accelerator_source
   and a profile string built from the real accelerator and memory
   (invalid QEMU_ACCEL errors before any output is created).
   Re-runs against Payload U: TCG 22/22 with profile "QEMU TCG,
   Q35/OVMF, 1 vCPU, 2 GiB, 48-bit IOMMU"; KVM 22/22 with profile
   "QEMU KVM, Q35/OVMF, 1 vCPU, 2 GiB, 48-bit IOMMU". The records
   now differ correctly; both JSONs are committed under
   evidence/wave5-lifecycle/.

Wave 5 close state: public main and staging main carry all five lane
merges plus the Wave 6 starter item below. Founder-gated items are
unchanged: named spare SSD, Azure subscription, Phase 3 firm and
budget, Secure Boot signing. The ARM64 decision inputs (Wave 5
item 6) are a new founder-facing item, Tommy's call, no gate on
other work.

## Wave 6: defined at Wave 5 close

Starter item EXECUTED at Wave 5 close (commit 48628ea):
write-build-receipt.py now records build provenance (build_path,
source_date_epoch, registry_anchor_sha256) so a published EFI hash
can be reproduced independently from the receipt alone; verified
standalone against a fixture tree (SDE and anchor hash land
exactly), and RELEASE-BUILD.md documents the new fields.

1. Upstream re-sync wave (from the Wave 5 item 4 recommendation):
   rebase the unified series onto upstream main (759cf2e2 or its
   successor at wave start), resolving the kernel-startup conflicts
   against the restructured dispatcher (5 of 8 files) and the one
   qemu-tools hunk; re-run the full lifecycle suite TCG and KVM
   against the re-synced build; publish the fresh audit (53
   Complete figures at main) in docs/COMPATIBILITY.md with the pin
   figures preserved and labelled; re-baseline the controlled build
   (new pin timestamp as SOURCE_DATE_EPOCH, anchor decision
   recorded) and cut v0.9.2 from it.
2. Unblock build_external_ssd.py --build end to end: free about
   40 GiB on the KnightHub root or relocate the cargo target and
   Docker data root to a /mnt/d-backed volume (root was at 0 bytes
   free at Wave 5 close); fix the 125 GiB gate to measure the
   filesystems the build actually consumes; rerun the identical
   command with the Wave 5 payload kit and produce the external
   SSD image file, layout-verified. Image files only; no physical
   writes.
3. AgentOS guest loop retry, gated on item 1's re-synced kernel:
   rerun evidence/wave5-lane-e/harness/w5_session11.py against the
   new build before touching AgentOS code; if the domain
   snapshot/resume fault persists, file the minimal reproduction
   from the Lane E evidence as an upstream-facing defect record in
   docs/. The -z norelro build flag gets documented in the agentos
   build docs either way (Ginux guest binaries require it).
4. Installer dry-run mode: add the additive --dry-run flag to
   install_host.py and install-to-ssd.sh (defaults off, cannot
   write when set, refusal guards run first), with tests in
   boot/ssd/tests/; in the same pass fix the two documented guard
   observations (the free-space gate filesystems from item 2, and
   the install-to-ssd.sh root-disk derivation under WSL).
5. Demo image EFI provenance: the demo image was rebuilt during
   Wave 5 and its EFI hash moved (af58ecc7 to 21d12d86) without a
   ledger entry at the time; add the demo build to the same receipt
   discipline as the release build (build receipt with hashes
   committed beside the image build record) so demo bytes are never
   again identified only by a summary line.
