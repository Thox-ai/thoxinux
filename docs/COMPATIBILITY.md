# Linux Compatibility: ThoxInux at the Pinned Upstream Commit

Audit date: 2026-10-31. Auditor: ThoxInux compatibility audit lane (THOX.ai).
Upstream: gmkurtzer/ginux at commit
`36503bda2d87465765e1b94e65f9d100f27ed5be` (the pin in `UPSTREAM.md`).

## Headline numbers (pinned commit)

| Status | Count |
|---|---|
| Complete | 82 |
| Partial | 245 |
| Policy-denied | 48 |
| Unsupported | 0 |
| Missing | 0 |
| **Total dispatched** | **375** |

These supersede two numbers that circulated earlier and are both wrong for
planning against this pin:

- The original brief's "82 fully / 245 partial" was right for the pin but
  incomplete: it omitted the 48 Policy-denied, which are dispatched and
  deliberately refused, not missing.
- The 53 Complete / 257 Partial / 48 Policy-denied / 17 Unsupported figures
  describe upstream `main` as read on 2026-10-31, not the pin. Upstream moved
  between the pin and that read; its own totals line changed again during the
  audit window. ThoxInux plans only against the pin.

## Method

1. Read the upstream ledger `docs/LINUX-COMPATIBILITY.md` at the pin: its own
   totals line (line 45) reads 82 Complete, 245 Partial, 48 Policy-denied
   of 375.
2. Recounted the ledger's index rows independently (appendix table): 375 rows,
   82 / 245 / 48, zero Unsupported, zero Missing; the stated vocabulary at the
   pin is exactly Complete / Partial / Policy-denied / Missing.
3. Counted dispatch in source: the dispatcher at the pin is the monolithic
   `kernel/src/arch/x86_64/cpu.rs` (about 44,300 lines). There is no
   `kernel/src/arch/x86_64/cpu/linux_syscall.rs` at the pin; that path in the
   brief does not exist. 375 `LINUX_*_SYSCALL` constants, and the constant
   number set equals the ledger's row set exactly (numbers 0 to 462 with 88
   omitted numbers, all inside the Linux-reserved block 336 to 423).
4. Ran upstream's own architecture checker `tools/architecture/check-linux-compat.sh`
   live at the pin: it passed with no findings.

Doc and source agree. The only discrepancies found are three cosmetic name
differences (syscalls 156, 183, 219: ledger names `_sysctl`, `afs_syscall`,
`restart_syscall` differ from constant spellings). Behavioral conformance of
individual syscalls was not re-tested; statuses are upstream's ledger,
cross-checked for internal consistency by the three counts above.

## Non-syscall ABI surface

The ledger also scores 23 non-syscall ABI surfaces: 0 Complete, 20 Partial,
1 Policy-denied (`/proc/sys/kernel/cap_last_cap` read surface), 2 Missing
(`/sys` device topology and cgroup v1/v2 hierarchies are recorded as
intentionally absent at this stage). Details are in the upstream ledger at the
pin.

## What the agent path touches

Per-area status for the surfaces the ThoxOS agent runtime depends on
(ledger section references are to the pinned upstream ledger):

- Process and thread model: Partial. `clone`, `fork`, `vfork`, `execve` and
  `execveat` are present; job control, `ptrace` beyond inspection, and
  personality controls are limited.
- Signals: Partial. Delivery and masks work for the common set; real-time
  signal queueing depth and some `sigreturn` edge cases are incomplete.
- Files and VFS: Partial, broad. The common file syscalls are Complete
  (`read`, `write`, `openat`, `close`, `stat` family); extended attributes,
  some `ioctl` classes, and file-backed shared mappings are Partial.
- Sockets and networking: mixed. `socket`, `bind`, `listen` are Complete;
  `connect` and `accept` are Partial. IPv6 is Partial. Design agent networking
  against the Complete set and treat the connect path as THOX finish work.
- Credentials and identity: Partial with hard edges. The credential-mutation
  syscalls (`setuid` family), `bpf`, and the Landlock trio are Policy-denied
  by design; agents cannot mint authority, which matches the ThoxInux domain
  model.
- seccomp and LSM ABI: Partial. Filters install; some actions and the audit
  ABI are incomplete.
- Memory: Partial. Anonymous mappings are solid; general file-backed
  `MAP_SHARED`, some `mprotect` and `mlock` behaviors, and blocking waits in
  parts of the futex path are pending.

## ThoxInux finish list implied by this audit

1. Complete the `connect`/`accept` path or pin agent networking to the
   Complete subset for v1.0.
2. IPv6 completion if any v1.0 agent surface needs it.
3. Job control and blocking-wait completion for interactive agent shells.
4. File-backed `MAP_SHARED` for model weight mapping patterns.
5. Re-audit at every upstream re-sync (monthly, per `UPSTREAM.md`); the matrix
   moves fast upstream and numbers from any other commit must never be mixed
   into this table.

The full row-level audit record (all 375 rows with statuses, the 23-row ABI
surface table, and the agent-path evidence) is preserved with the run evidence
and in the upstream ledger at the pinned commit.
