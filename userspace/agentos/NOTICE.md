# NOTICE: thox-agentos

thox-agentos is an original THOX.ai work, Copyright (C) 2026 THOX.ai LLC,
licensed under the Apache License, Version 2.0 (see LICENSE in this
directory and the monorepo root LICENSE).

Adopted into the ThoxInux monorepo on 2026-10-31 from the THOX agent-OS
operation workspace (~/workspace/thoxos-ginux-agentic-os-20261031/thox-agentos/),
with one fix applied during adoption verification (daemon binds its control
socket before autostarting agents; see .agents/HANDOFF.md and the run's
AGENTOS-REPORT.md). Verification at adoption: cargo build clean with zero
warnings, 9 of 9 integration tests passing, live daemon smoke passing on
KnightHub (WSL2) with state on a native filesystem.

Platform scope: Linux and Unix only, by design (Unix domain sockets, Unix
process model). The state directory must live on a native Linux filesystem;
drvfs and other mounts without Unix-socket support cannot host the daemon
socket.
