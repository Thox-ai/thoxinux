#!/bin/bash
# Wave 5 Lane E: AgentOS loop inside the ACTUAL Ginux kernel guest.
# Environment: thoxos-shell domain (init=/usr/local/bin/thox-shell, no
# systemd) on the Ginux kernel (GINUX.EFI under QEMU/KVM on KnightHub),
# Rocky Linux 10 userspace (ThoxOS 0.1.0 Ginux Edition) with AgentOS
# baked into the userspace OCI image. This is NOT the Wave 3 Docker
# container proof (that shared the host WSL2 kernel).
# Adaptation: no systemd in the shell domain, so thox-agentd runs in
# its own no-systemd development mode (scripts/run-dev.sh pattern),
# seeded by the shipped scripts/first-boot-seed.sh unmodified.
set -u
export THOX_AGENTOS_HOME=/opt/agentos/state
export THOX_AGENTOS_CONFIG=/opt/agentos/config
BIN=/opt/agentos-bin
AG="$BIN/thox-agent --state-dir $THOX_AGENTOS_HOME"
echo "=== [ginux-guest] identity ==="
head -n 4 /etc/os-release; uname -srm; id
echo "=== [ginux-guest] thox version ==="; thox version; echo "exit=$?"
echo "=== [ginux-guest] thox status ==="; thox status; echo "exit=$?"
echo "=== [ginux-guest] agentos payload ==="; ls -l /opt/agentos-bin /opt/agentos-src/scripts /opt/agentos
echo "=== [ginux-guest] seed reporter (scripts/first-boot-seed.sh) ==="
sh /opt/agentos-src/scripts/first-boot-seed.sh "$BIN"; echo "seed_exit=$?"
echo "=== [ginux-guest] reporter manifest (identity_token truncated) ==="
python3 -c "import json; m=json.load(open('/opt/agentos/config/agents/reporter.json')); m['identity_token']=m['identity_token'][:24]+'...[truncated]'; print(json.dumps(m, indent=2))"
echo "=== [ginux-guest] start thox-agentd (background, no systemd) ==="
"$BIN/thox-agentd" --state-dir "$THOX_AGENTOS_HOME" --agents-dir "$THOX_AGENTOS_CONFIG/agents" --trust-dir "$THOX_AGENTOS_CONFIG/trust" > /opt/agentos/daemon.out 2>&1 &
DPID=$!
echo "daemon_pid=$DPID"
for i in $(seq 1 50); do [ -S "$THOX_AGENTOS_HOME/run/agentd.sock" ] && break; sleep 0.2; done
ls -l "$THOX_AGENTOS_HOME/run/agentd.sock" 2>&1; echo "socket_wait_done"
sleep 7
echo "=== [ginux-guest] daemon output so far ==="; cat /opt/agentos/daemon.out 2>&1
echo "=== [ginux-guest] thox-agent list ==="; $AG list; echo "exit=$?"
echo "=== [ginux-guest] thox-agent status reporter ==="; $AG status reporter; echo "exit=$?"
echo "=== [ginux-guest] thox-agent logs reporter --lines 5 ==="; $AG logs reporter --lines 5; echo "exit=$?"
echo "=== [ginux-guest] thox-agent audit --lines 10 ==="; $AG audit --lines 10; echo "exit=$?"
echo "=== [ginux-guest] capability denial probes ==="
echo "guest-secret-outside-grants" > /root/agentos-secret.txt
python3 /opt/agentos/deny.py; echo "deny_probe_exit=$?"
echo "=== [ginux-guest] thox-agent audit --lines 20 ==="; $AG audit --lines 20; echo "exit=$?"
echo "=== [ginux-guest] thox-agent stop reporter ==="; $AG stop reporter; echo "exit=$?"
sleep 1
echo "=== [ginux-guest] thox-agent status reporter (after stop) ==="; $AG status reporter; echo "exit=$?"
echo "=== [ginux-guest] thox-agent start reporter ==="; $AG start reporter; echo "exit=$?"
sleep 6
echo "=== [ginux-guest] thox-agent logs reporter --lines 3 (after restart) ==="; $AG logs reporter --lines 3; echo "exit=$?"
echo "=== [ginux-guest] SIGTERM daemon (F2 shutdown path) ==="
kill $DPID; echo "kill_exit=$?"
for i in $(seq 1 50); do [ -d /proc/$DPID ] || break; sleep 0.2; done
[ -d /proc/$DPID ] && echo "daemon_still_present_after_10s" || echo "daemon_process_gone"
echo "=== [ginux-guest] processes after daemon stop ==="
python3 - <<'PY'
import os
found=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():
        continue
    try:
        with open(f'/proc/{pid}/cmdline','rb') as f:
            cmd=f.read().replace(b'\x00',b' ').decode('utf-8','replace').strip()
    except OSError:
        continue
    if 'thox-agentd' in cmd or 'thox-reporter' in cmd:
        found.append((pid,cmd))
print(found if found else "none running")
PY
echo "=== [ginux-guest] daemon output final ==="; cat /opt/agentos/daemon.out 2>&1
echo "=== [ginux-guest] audit.log file (raw) ==="; cat "$THOX_AGENTOS_HOME/audit.log" 2>&1
echo "GUEST_RUN_DONE"
