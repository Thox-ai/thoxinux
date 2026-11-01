# Upstream Re-sync Evaluation: Pin 36503bda to Upstream Main 759cf2e2

Evaluation date: 2026-10-31. Evaluator: ThoxInux Wave 5, Lane B (THOX.ai).
Upstream: gmkurtzer/ginux. This document evaluates a re-sync; it does not
perform one. No pin in this repository changes on the basis of this
document alone.

| Point | Commit | Date |
|---|---|---|
| THOX pin (current base) | `36503bda2d87465765e1b94e65f9d100f27ed5be` | 2026-10-26 |
| Upstream main HEAD at evaluation | `759cf2e221b459b0195c3fa7ed909688b755e74e` | 2026-10-31 |

Commits between pin and main HEAD: 138, in about five days. Of those,
67 touch `kernel/src` and 53 touch the arch tree. Upstream is moving at
roughly 25 to 30 commits per day; any main snapshot is stale within
hours, which is why every number below is labelled with the commit it
was measured at.

## 1. Overall drift (pin 36503bda to main 759cf2e2)

- 330 files changed, 79,061 insertions, 30,892 deletions
  (`git diff --shortstat`).
- By file count, about half of the changed files are upstream's own
  gate-result evidence data under `docs/feedback-hardening/` and
  `hdae/gates-done/`, not code. The code drift is concentrated in
  `kernel/src` (7.8 percent of changed files) and its arch subtree.
- No commit subject in the range names a security fix, CVE, or
  vulnerability (subject scan for secur, vuln, cve, overflow, bounds:
  zero matches). Nothing in the range forces the security fast-track
  in `UPSTREAM.md`.

## 2. The dispatcher surface

At the pin, the syscall dispatcher is the monolithic
`kernel/src/arch/x86_64/cpu.rs`: 44,324 lines, holding the 375
`LINUX_*_SYSCALL` constant definitions and the dispatch match in one
file.

At main `759cf2e2` the dispatcher has been restructured:

| File at main 759cf2e2 | Lines | Role |
|---|---|---|
| `kernel/src/arch/x86_64/cpu.rs` | 42,752 | Still the entry and core; diff vs pin alone is 14,390 insertions, 15,962 deletions |
| `kernel/src/arch/x86_64/cpu/linux_abi.rs` | 872 | NEW. Holds all 375 syscall constant definitions |
| `kernel/src/arch/x86_64/cpu/linux_syscall.rs` | 1,560 | NEW. The dispatch match (344 constant references) |
| `kernel/src/arch/x86_64/cpu/linux_signal.rs` | 2,523 | NEW. Signal delivery split out of cpu.rs |
| `kernel/src/arch/x86_64/cpu/linux_futex.rs` | 691 | NEW |
| `kernel/src/arch/x86_64/cpu/linux_poll.rs` | 959 | NEW |
| `kernel/src/arch/x86_64/cpu/linux_time.rs` | 630 | NEW |
| `kernel/src/arch/x86_64/cpu/linux_random.rs` | 121 | NEW |
| `kernel/src/arch/x86_64/cpu/architecture.rs` | 578 | NEW |
| `kernel/src/arch/x86_64/cpu/execution.rs` | 303 | NEW |

The `cpu/` submodule directory (9 files, 8,237 lines) and
`kernel/src/arch/x86_64/smp.rs` do not exist at the pin. Consequence
for the THOX series: the patch context for the dispatcher no longer
exists in its pinned shape; see section 4.

## 3. Drift on the surfaces the THOX series touches

Per-file diff, pin `36503bda` to main `759cf2e2`:

| File | Drift pin to main | Note |
|---|---|---|
| `Makefile` | 27 insertions, 1 deletion | Small |
| `kernel/linux-probe.S` | 22 insertions, 9 deletions | Small |
| `kernel/linux-system-init.S` | unchanged | Byte-identical |
| `kernel/src/address_space.rs` | 532 insertions, 153 deletions | Moderate |
| `kernel/src/arch/x86_64/cpu.rs` | 14,390 insertions, 15,962 deletions | Restructured, see section 2 |
| `kernel/src/lib.rs` | 128 insertions, 34 deletions | Moderate |
| `kernel/src/linux_socket.rs` | 288 insertions, 200 deletions | Moderate |
| `kernel/src/linux_stack.rs` | does not exist upstream | Created by the THOX series |
| `control-plane/runtime/src/main.rs` | unchanged | Byte-identical |
| `tools/qemu/common.sh` | unchanged | Byte-identical |
| `tools/qemu/run.sh` | 15 insertions, 2 deletions | Header rewritten |
| `services/network/src/registry.rs` | 98 insertions, 53 deletions | Moderate |

ABI-adjacent surfaces:

- `services/protocol/` (protocol service), `crates/protocol-state/`,
  and `crates/native-abi/`: unchanged between pin and main. The
  service protocol did not move.
- `services/` overall: only the network service changed (its `main.rs`
  and `registry.rs`, 114 insertions, 59 deletions across the service).
- `crates/` overall: only `crates/kernel-policy` changed
  (94 insertions).
- `docs/LINUX-COMPATIBILITY.md`: 43 insertions, 38 deletions. The
  totals line changed; section 5 covers what that change means.
- Shared syscall numbers table: the constant set is identical. The
  375 definitions moved from `cpu.rs` (pin) to `cpu/linux_abi.rs`
  (main); the number set (0 to 462, same 88 omitted numbers in the
  Linux-reserved block) is set-equal to the pin and to the ledger rows
  at both commits.

## 4. Patch dry-run onto upstream main

Method: pristine checkout of upstream main `759cf2e2` in a scratch
tree; `git apply --check` for each patch, run both individually and in
series order (`thox-kernel-startup`, `thox-identity`,
`thox-qemu-tools`, `thox-registry-anchor`). Both runs give the same
verdicts. `git apply` reports the first failing hunk per file, so a
file marked failed has at least the stated failures; later hunks in
that file are untestable until the earlier ones are resolved.

| Patch | Files | Hunks | Verdict at main 759cf2e2 |
|---|---|---|---|
| `thox-kernel-startup.patch` | 8 | 34 | CONFLICTS |
| `thox-identity.patch` | 1 | 1 | APPLIES CLEAN |
| `thox-qemu-tools.patch` | 2 | 4 | CONFLICTS |
| `thox-registry-anchor.patch` | 1 | 2 | APPLIES CLEAN (with line offsets) |

Detail:

- `thox-kernel-startup.patch`: 5 of 8 target files fail.
  `Makefile` (failing hunk at pinned line 17), `kernel/linux-probe.S`
  (line 127), `kernel/src/address_space.rs` (hunk at line 1042 fails;
  another hunk applies 35 lines off), `kernel/src/arch/x86_64/cpu.rs`
  (hunk at line 4575 fails; the file was restructured, section 2),
  `kernel/src/linux_socket.rs` (6 hunks apply with offsets, then the
  hunk at line 644 fails; the patch carries 17 socket hunks, so the
  remaining socket hunks are untestable until that one is resolved).
  Clean targets: `kernel/linux-system-init.S`,
  `kernel/src/lib.rs` (applies with a 78-line offset), and the new
  file `kernel/src/linux_stack.rs`.
- `thox-identity.patch`: applies clean, no offsets. Its target file
  is one of the three byte-identical files in the range.
- `thox-qemu-tools.patch`: `tools/qemu/common.sh` applies clean
  (2 hunks, target unchanged upstream); `tools/qemu/run.sh` fails
  (hunk at line 8; upstream rewrote the script header).
- `thox-registry-anchor.patch`: applies clean with offsets (hunks land
  1 and 36 lines off) despite the registry drift in section 3.

Summary: half the series (identity, registry anchor) survives five
days of upstream drift untouched. The core patch, kernel-startup,
does not: its most important target was restructured upstream, so a
re-sync means re-expressing the cpu.rs hunks against the new
`cpu/` submodule layout, not resolving textual conflicts line by line.

## 5. Fresh syscall audit at upstream main

Method: identical to `docs/COMPATIBILITY.md` at the pin. (1) Read the
totals line of upstream's ledger `docs/LINUX-COMPATIBILITY.md`.
(2) Recount the ledger's syscall index rows independently.
(3) Count the dispatch constants in source and compare the number set
to the ledger rows. (4) Run upstream's own checker
`tools/architecture/check-linux-compat.sh`.

Results at main `759cf2e2` (2026-10-31):

| Status | Pin 36503bda | Main 759cf2e2 |
|---|---|---|
| Complete | 82 | 53 |
| Partial | 245 | 257 |
| Policy-denied | 48 | 48 |
| Unsupported | 0 | 17 |
| Missing | 0 | 0 |
| **Total dispatched** | **375** | **375** |

All four checks agree at main: the ledger totals line (line 46), the
independent row recount (375 rows: 53 / 257 / 48 / 17), the constant
count (375 definitions in `cpu/linux_abi.rs`, number set 0 to 462,
set-equal to the ledger rows), and the upstream checker, which passes
and prints the same totals. The table size did not change: still 375,
same number set at both commits.

Interpretation, and it matters: the fall in Complete from 82 to 53 is
a re-scoring, not a loss of dispatch. Zero syscalls were added or
removed, and exactly 29 entries changed status, all of them out of
Complete:

- 12 Complete to Partial: the socket family (numbers 41, 44, 45, 46,
  47, 49, 50, 51, 52, 53, 54, 55: `socket`, `sendto`, `recvfrom`,
  `sendmsg`, `recvmsg`, `bind`, `listen`, `getsockname`,
  `getpeername`, `socketpair`, `setsockopt`, `getsockopt`). Upstream's
  status rule at main requires positive, negative, and edge-case
  conformance tests for Complete; the ledger text for these entries
  describes substantially more behavior at main than at the pin, so
  the entries grew and their grade tightened at the same time.
- 17 Complete to Unsupported: obsolete calls reclassified as
  intentionally returning `-ENOSYS` (for example `uselib` 134,
  `_sysctl` 156, `create_module` 174).

Non-syscall ABI surfaces are unchanged in distribution at main:
23 surfaces, 0 Complete, 20 Partial, 1 Policy-denied, 2 Missing,
identical counts to the pin.

Planning consequence: a re-sync would replace the published pin
numbers (82 Complete) with stricter numbers (53 Complete) even though
the underlying behavior improved. That is honest, and it must be
planned as a communications-visible change, not discovered after the
fact.

## 6. What a re-sync would cost, and what it buys

Cost:

- Rebase `thox-kernel-startup.patch` against the restructured
  dispatcher (section 4): the cpu.rs work must be re-expressed
  against `cpu.rs` plus the `cpu/` submodules. This is the dominant
  cost; the other conflict (one `run.sh` hunk) is minor, and two
  patches carry over untouched.
- Full re-proof under the rule in `UPSTREAM.md`: controlled rebuild
  with the reproducibility controls, `prepare_source.py` verification
  against the new pin, this audit redone at the new pin (done here
  for main, reusable only if the pin lands on `759cf2e2` itself),
  the 22-command lifecycle suite under both TCG and KVM, and the
  demo and SSD image paths rebuilt and re-verified.
- Wave 5 items already encoded against the current pin (release
  procedure controls, payload kit assembly, AgentOS guest proof)
  would restart against the new base if the re-sync lands first.

Buys:

- 138 commits of upstream work, including the dispatcher
  modularization itself (future rebases get cheaper: the THOX cpu.rs
  hunks would target smaller files), deeper socket, futex, poll,
  signal, and time behavior inside the Partial entries, and the
  virtio queue-size fix at main HEAD (merge of PR #10).
- A shorter eventual rebase: drift compounds at roughly 25 to 30
  commits a day, and the next evaluation will face a larger gap.

## 7. Recommendation

HOLD at the pin `36503bda` for the v0.9.1 release and the remaining
Wave 5 items; run the re-sync as its own dedicated wave immediately
after Wave 5 exits, targeting whatever main is at that start date and
re-running this evaluation's audit at the chosen commit first.

Reasoning: the drift is large in lines but shallow in contract: the
syscall table, the service protocol, and the ABI crates did not move
at all, and no security fix in the range triggers the fast-track.
Against that, the one patch that matters most conflicts with a
restructured dispatcher, so a re-sync now is a rebase plus a full
lifecycle re-proof inserted into the middle of a wave that is already
proving things against the current pin. The monthly re-sync review in
`UPSTREAM.md` comes due in late November 2026 in any case; the
dedicated-wave re-sync should land on that cadence or sooner if any
of these triggers fire first: an upstream security fix, a fix for a
defect ThoxInux has actually hit, or upstream drift past roughly
another 150 commits from `759cf2e2`.
