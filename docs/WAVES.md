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
