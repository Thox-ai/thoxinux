# Wave 5 Lane E: AgentOS loop inside the Ginux kernel guest

## Verdict

BLOCKED at the Ginux kernel domain layer. The Wave 3 loop was not completed
inside the Ginux guest in this lane, and this note is the deliverable: a
precise blocker record with the full attempt matrix and the isolated trigger.

The short form: thox-agentd and its reporter agent demonstrably start and
serve inside the guest (socket up, agent list and status verified in the
shell domain, attempt 2). But at this upstream Ginux revision, a domain
cannot hold the resident, state-writing daemon tree across subsequent
process lifecycle activity. Every configuration tried, across both domain
types and three parentage patterns, ends in one of three kernel fault
signatures within seconds to a few steps of the daemon becoming resident.
AgentOS itself is exonerated by the host test suite (23/23), by the Wave 3
container loop, and by the in-guest bisect results recorded below.

This result is separate from the Wave 3 Docker container proof. The Wave 3
proof ran on the host WSL2 kernel and does not count here; nothing in this
note upgrades it.

## Environment and guest identity

- Host: KnightHub (WSL2), Docker 29.1.3, /dev/kvm present.
- QEMU 10.2.1, machine q35, accel=kvm, cpu host,+smep,+smap,+umip, 1 vCPU,
  2 GiB RAM, OVMF_CODE_4M.fd (OVMF 2025.11), virtio-blk volume on a
  WSL-native ext4 state directory.
- Guest kernel: Ginux 6.12.0-ginux.0.1 x86_64, booted from GINUX.EFI,
  SHA-256 21d12d86631df7947a9bd7389b664106676c6f97a18e44d38d9ddb906b00f7b4
  (verified by sha256sum inside the base demo image; the image's own
  GINUX.EFI.sha256 file agrees).
- Guest userspace: ThoxOS 0.1.0 Ginux Edition, Rocky Linux 10 base,
  image thoxos/userspace:0.1.0 (variant, see route), pulled by the guest
  from the edition TLS registry and layer-verified in the boot transcripts.
- Domains used: the thoxos-shell domain (init /usr/local/bin/thox-shell,
  no systemd) and the system domain (init /sbin/init, systemd 257).
- Brand reference: THOX green 05A451 (TXF).

## Route used to inject AgentOS (approach 2: baked variant image)

The Wave 2 SSD image route was not used: the image file is gone from disk
(logs and summary remain), and that path in any case boots a Debian host
kernel first and runs Ginux nested, so a payload disk there reaches the
wrong layer. The demo path boots GINUX.EFI directly.

1. Built thox-agentd, thox-agent, thox-reporter from userspace/agentos with
   cargo on KnightHub (build clean; cargo test 23/23: 9 integration,
   9 parser robustness, 5 shutdown; logs cargo-host.log).
2. Rebuilt the binaries with RUSTFLAGS "-C link-arg=-Wl,-z,norelro"
   (build flag only; no source change). Reason: the Ginux relocatable exec
   plan rejects default Rust binaries with rejection code 7
   (UnsupportedExecutable in published_rootfs ProcessPlanFailure); the
   upstream parser (kernel/src/linux_elf.rs parse_relocatable) requires
   exactly one PF_EXEC and exactly one PF_WRITE PT_LOAD, and default Rust
   linking emits two writable LOAD segments. A C control binary, including
   one using thread-local storage, executes in the guest, which cleared
   PT_TLS as a suspect. Resulting SHA-256:
   thox-agent cd129ed0483b56ff31ddaeb8afe2b8300cba9786dc081bce1a845a38fbd802b5
   thox-agentd ebc3486a96e8751060d904aa4ca6901c2b2cae8c8d3b3318a4d8113b265e8333
   thox-reporter 7fdd1c387516cfb8df1a9886d4c170b59582cfdc783a8ebc1b74d069e8ed98d7
3. Baked the binaries, the agentos scripts, and a pre-seeded config into a
   variant userspace OCI image (thoxos-g/userspace-agentos:0.1.0-w5e),
   re-seeded a registry store with skopeo using the edition's own seed
   procedure, and built a derived demo image thoxos-g/demo-agentos:0.1.0-w5e
   FROM thoxos-g/demo:0.1.0 (same EFI, same registry CA). The guest pulls
   the variant image (10 layers) from the TLS registry at domain start.
   Build reproduction: payload/build-variant.sh, payload/Dockerfile.userspace,
   payload/Dockerfile.demo, payload/seed-manifest.json.
4. Pre-seed adaptation, documented honestly: the shipped
   first-boot-seed.sh cannot complete inside the guest. Run in-guest it
   aborts with "cd: /..: Function not implemented", exit 1, zero side
   effects, because bash command substitution returns empty in the shell
   domain (measured independently: $(echo hi) yields an empty string), so
   its REPO_ROOT expansion is empty. The script itself is unmodified. The
   baked config was produced by running the same shipped script in the
   variant userspace container (Linux kernel) with THOX_AGENTOS_HOME and
   THOX_AGENTOS_CONFIG pointed at the guest paths; it produced
   agents/reporter.json, keys/issuer.key (mode 0600), trust/thox.pub, and a
   manifest with command [/opt/agentos-bin/thox-reporter], socket
   /opt/agentos/state/run/agentd.sock, grants fs_read [/proc, /etc,
   /usr/lib], fs_write [], exec_allow [], network_egress false, token
   length 198 (preseed.log). The private key and the full token are not in
   this evidence pack; transcripts show only the 24 character truncated
   token form that the guest tooling itself prints.

## What was proven inside the actual guest

- Guest identity in every transcript: PRETTY_NAME "ThoxOS 0.1.0 Ginux
  Edition", uname "Ginux 6.12.0-ginux.0.1 x86_64", thox status kernel line
  "Ginux 6.12.0-ginux.0.1 (#1)".
- Attempt 2 (shell domain, direct norelro binaries, interactive lines):
  thox-agentd started, the socket /opt/agentos/state/run/agentd.sock was
  present, thox-agent list returned OK, thox-agent status reporter
  returned OK. The domain then faulted during the following sleep step
  (session-evidence2.log; transcript superseded by later runs).
- Attempt 4 (shell domain, mode B lines): the daemon line, the
  list/status/logs/audit line, and the denial probe line all completed;
  the domain faulted during the stop/start line (session-evidence4.log).
- Bisects inside the guest:
  - Python imports (os, runpy, signal, socket, stat, subprocess, time):
    fine (diag7, diag11 m1).
  - Python fork/exec of /bin/true: fine; with stdout redirected to a file:
    fine (diag11 m2, m3).
  - Script file size is not the trigger: 512, 1024, 1536 and 2048 byte
    Python scripts all run (diag10).
  - Python exec of thox-agent (--help): fine (diag12).
  - Reading the driver files from the baked image: fine, and the image
    copies are byte-identical to the payload by SHA-256.
  - System domain without AgentOS activity boots cleanly through
    basic.target, multi-user.target and graphical.target on the same
    variant image (transcript-system1.txt through transcript-system3.txt).

## The blocker: fault signatures

All three signatures are the Ginux kernel's own console output, captured in
the transcripts in this pack.

1. Kernel panic on snapshot/fork during exec:
   "ginux: fatal exception vector: 8"
   "ginux: exception instruction: 1828873799"
   "ginux: exception Linux snapshot/fork/pid: 9 14 <pid>"
   "GINUX_KERNEL_PANIC"
   Seen when a Python driver process was exec'd after the pre-steps
   (attempts 5 and 6, diag7 step 4, diag9 step 4), at the identical
   instruction value in every occurrence.
2. User fault in the parent process at a fixed address, followed by an
   FS resume mismatch:
   "ginux: Linux user fault vector/error/address/rip:14 6 18446744073709551497 549756868485"
   The RIP 549756868485 is identical in the shell domain (diag11 m4,
   Python parent exec of thox-agentd) and in the system domain
   (transcript-system1.txt, Python service starting the daemon), which
   isolates the trigger to the daemon exec/residency, not to the driver.
3. FS resume mismatch and domain failure:
   "ginux: Linux resume FS mismatch expected/returned/saved/restored: 549764910720 549761119936 549774136576 1"
   "ginux: Linux runtime child completion failed at stage 17"
   "ginux: Linux init execution failed; domain marked failed"
   Seen with the daemon resident across shell command cycles (attempts 1
   and 2), during a post-launch idle window (attempt 9: the domain died
   inside the 25 second settle wait, before the driver line was sent),
   and in the system domain after the daemon service had started
   (transcript-system3.txt).
4. Supporting signature (attempt 8): with the daemon mid-startup, a
   pidfile redirect failed with "Function not implemented" (ENOSYS) and
   every later line failed with "ginux: Linux child exec precondition
   rejected" and thox-shell "[Errno 11] Resource temporarily unavailable:
   '/bin/bash'" (transcript-evidence8.txt).

## Attempt matrix

Shell domain (thoxos-shell, no systemd):
- A1, ld.so wrapper invocation: daemon launch line completed; domain
  faulted immediately after (signature 3).
- A2, direct norelro binaries, one step per line: high-water mark. Daemon
  up, socket verified, list and status OK; faulted at the next sleep
  (signature 3).
- A3, one step per line with marker matching: harness sequence completed
  at prompt level; no audit content captured; not counted as loop proof.
- A4, five medium lines (mode B): daemon line, list/status/logs/audit
  line and denial line completed; faulted during the stop/start line
  (signature 3).
- A5, single Python driver (driver.py): kernel panic at driver exec
  (signature 1).
- A6, two lean Python drivers (driver1.py, driver2.py): kernel panic at
  the first driver exec, identical instruction (signature 1).
- A7, POSIX sh script file (loop.sh): bash (Rocky /bin/sh is bash) exits a
  script file silently after its first external command; the loop body
  never executed; the domain still failed at shell exit (signature 3).
- A8, hybrid with pidfile (bash launch, driver3.py): pidfile redirect
  ENOSYS; all later lines rejected (signature 4).
- A9, hybrid with retries (bash launch, /proc pid discovery, exec retry
  loop): domain died during the post-launch settle window before the
  driver was sent (signature 3).

System domain (systemd):
- S1, oneshot service running the Python driver (driver2.py, daemon
  Popen): systemd reached multi-user; the service started; user fault at
  the fixed RIP of signature 2; domain failed.
- S2, oneshot service running a bash script (loop-sys.sh): the service
  finished instantly with no output (bash script files are inert in this
  guest); the domain faulted at the next checkpoint (signature 3).
- S3, systemd-native daemon unit (agentos-daemon.service, Started OK)
  plus a separate Python loop unit (agentos-loop.service): the loop unit
  started; FS resume mismatch; domain failed before any driver output
  (signature 3).

Diagnostics (shell domain): diag7 (imports and small scripts fine,
driver1 panic), diag8 (fork probe driver9: user fault and FS mismatch
before its first marker), diag9 (procscan fine; driver1 panic),
diag10 (size sweep all fine), diag11 (m1 to m3 fine; m4 daemon Popen
fault, signature 2), diag12 (Python to thox-agent fine; Python to
thox-reporter wedges in its broker connect retry, which is expected
behaviour with no daemon socket present).

## Conclusion and what would unblock this item

The loop's steps are individually proven in the guest; the composition is
what the current Ginux revision does not survive. The common condition of
every fatal attempt is a resident thox-agentd plus reporter tree, which
writes audit and state files under /opt/agentos/state on the snapshotted
domain rootfs, while further process lifecycle events occur (a shell
command cycle, a service start, a child return to init, or in A9 no
driven event at all inside 25 seconds). No upstream guard and no agentos
capability policy was modified in this lane; the only build change is the
norelro link flag recorded above.

Candidate unblock paths for a future wave, in order of promise:
1. An upstream Ginux fix for domain snapshot/resume bookkeeping with a
   resident, state-writing daemon tree (the FS mismatch fields in
   signature 3 are the starting point for the kernel lane).
2. AgentOS state on storage outside the snapshotted rootfs, if a future
   edition provides a non-snapshotted mount or a second volume for
   domain state; /opt/agentos/state is the first thing to move.
3. Re-run this lane's harness set (harness/w5_session11.py is the most
   complete) on the next Ginux revision before changing any AgentOS code.

## Evidence index

- transcripts/: guest serial console transcripts for attempts 5, 6, 7, 8,
  9, diagnostics 7, 9, 10, 11, 12, and system domain attempts S1, S2, S3.
- logs/: harness session logs for every attempt, cargo-host.log (build and
  23/23 tests), cargo-norelro.log, preseed.log.
- harness/: the console session harnesses used (w5_session*, w5_diag*).
- payload/: the drivers and probes (driver.py, driver1.py, driver2.py,
  driver3.py, driver9.py, loop.sh, loop-sys.sh, guest-run.sh, deny.py,
  procscan.py, manifest.py, term.py, m1.py to m4.py), the variant build
  files (build-variant.sh, Dockerfile.userspace, Dockerfile.demo), the
  systemd units (agentos-daemon.service, agentos-loop.service),
  payload-sha256.txt, and seed-manifest.json (the OCI manifest of the
  variant userspace image served to the guest).
- Wave 3 container proof, for separation: /mnt/d/thoxinux-build/wave3-guest/
  on KnightHub (not part of this result).
