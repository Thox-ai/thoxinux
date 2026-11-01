#!/bin/sh
# ThoxInux Wave 5 Lane E guest loop, POSIX sh edition. Runs the Wave 3
# AgentOS loop inside the Ginux shell domain as ONE sh process:
# /bin/sh script files execute fully in this domain (the shipped seed
# script reached its line 17), a shell parent launching thox-agentd is
# the pattern that worked in evidence attempt 2, and the domain init
# resumes only once, when this script exits with the daemon stopped.
# No command substitution (returns empty in this domain), no bashisms.
STATE=/opt/agentos/state
CONFIG=/opt/agentos/config
BIN=/opt/agentos-bin
AG="$BIN/thox-agent --state-dir $STATE"
echo "=== [ginux-guest] identity ==="
grep PRETTY_NAME /etc/os-release
uname -srm
id
echo "=== [ginux-guest] seed attempt (shipped first-boot-seed.sh, in-guest) ==="
THOX_AGENTOS_HOME=$STATE THOX_AGENTOS_CONFIG=$CONFIG sh /opt/agentos-src/scripts/first-boot-seed.sh $BIN > /opt/agentos/seed.log 2>&1
echo "seed-exit=$?"
cat /opt/agentos/seed.log
echo "note: seed aborts in this domain (sh command substitution returns empty); the config in /opt/agentos/config was produced by the same shipped script, unmodified, in the userspace container and baked into this image."
echo "=== [ginux-guest] reporter manifest (identity_token truncated) ==="
python3 /opt/agentos/manifest.py
echo "=== [ginux-guest] start thox-agentd (no systemd, run-dev.sh pattern) ==="
mkdir -p $STATE/run
$BIN/thox-agentd --state-dir $STATE --agents-dir $CONFIG/agents --trust-dir $CONFIG/trust > /opt/agentos/daemon.out 2>&1 &
DPID=$!
echo "daemon-pid=$DPID"
sleep 4
ls -l $STATE/run/agentd.sock
cat /opt/agentos/daemon.out
echo "=== [ginux-guest] thox-agent list ==="
$AG list
echo "list-exit=$?"
echo "=== [ginux-guest] thox-agent status reporter ==="
$AG status reporter
echo "status-exit=$?"
sleep 7
echo "=== [ginux-guest] thox-agent logs reporter --lines 5 ==="
$AG logs reporter --lines 5
echo "=== [ginux-guest] thox-agent audit --lines 10 ==="
$AG audit --lines 10
echo "=== [ginux-guest] capability denial probes ==="
echo guest-secret-outside-grants > /root/agentos-secret.txt
python3 /opt/agentos/deny.py
echo "deny-exit=$?"
echo "=== [ginux-guest] thox-agent audit --lines 20 ==="
$AG audit --lines 20
echo "=== [ginux-guest] thox-agent stop reporter ==="
$AG stop reporter
sleep 1
$AG status reporter
echo "=== [ginux-guest] thox-agent start reporter ==="
$AG start reporter
sleep 7
$AG logs reporter --lines 3
echo "=== [ginux-guest] SIGTERM daemon (F2 shutdown path) ==="
kill -TERM $DPID
wait $DPID
echo "daemon-exit=$?"
sleep 1
echo "=== [ginux-guest] processes after daemon stop ==="
python3 /opt/agentos/procscan.py
echo "=== [ginux-guest] daemon output final ==="
cat /opt/agentos/daemon.out
echo "=== [ginux-guest] audit.log raw ==="
cat $STATE/audit.log
echo "LOOP_DONE"
