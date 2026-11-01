#!/bin/bash
# Smoke PHASE 2: identical flow, but state/config on native ext4 ($HOME),
# because phase 1 proved Unix sockets cannot bind on drvfs (/mnt/d, 9p).
set -u
BIN=/mnt/d/thoxinux-build/agentos/target/debug
SMOKE_HOME=$HOME/thox-agentos-smoke
export THOX_AGENTOS_HOME="$SMOKE_HOME/state"
export THOX_AGENTOS_CONFIG="$SMOKE_HOME/config"
rm -rf "$SMOKE_HOME"; mkdir -p "$SMOKE_HOME"
echo "== seed (native-fs home) =="
/mnt/d/thoxinux-build/agentos/scripts/first-boot-seed.sh "$BIN"; echo "seed_exit=$?"
echo "== start thox-agentd in background =="
"$BIN/thox-agentd" --state-dir "$THOX_AGENTOS_HOME" --agents-dir "$THOX_AGENTOS_CONFIG/agents" --trust-dir "$THOX_AGENTOS_CONFIG/trust" > "$SMOKE_HOME/daemon.out" 2>&1 &
DPID=$!
echo "daemon_pid=$DPID"
for i in $(seq 1 50); do [ -S "$THOX_AGENTOS_HOME/run/agentd.sock" ] && break; sleep 0.2; done
ls -l "$THOX_AGENTOS_HOME/run/agentd.sock"
sleep 7
echo "== daemon output so far =="; cat "$SMOKE_HOME/daemon.out"
AG="$BIN/thox-agent --state-dir $THOX_AGENTOS_HOME"
echo "== thox-agent list =="; $AG list; echo "exit=$?"
echo "== thox-agent status =="; $AG status; echo "exit=$?"
echo "== thox-agent status reporter =="; $AG status reporter; echo "exit=$?"
echo "== thox-agent logs reporter --lines 5 =="; $AG logs reporter --lines 5; echo "exit=$?"
echo "== thox-agent audit --lines 10 =="; $AG audit --lines 10; echo "exit=$?"
echo "== thox-agent model show =="; $AG model show; echo "exit=$?"
echo "== thox-agent reload =="; $AG reload; echo "exit=$?"
echo "== thox-agent stop reporter =="; $AG stop reporter; echo "exit=$?"
sleep 1
echo "== thox-agent status reporter (after stop) =="; $AG status reporter; echo "exit=$?"
echo "== thox-agent start reporter =="; $AG start reporter; echo "exit=$?"
sleep 6
echo "== thox-agent logs reporter --lines 3 (after restart) =="; $AG logs reporter --lines 3; echo "exit=$?"
echo "== thox-agent audit --lines 20 (final) =="; $AG audit --lines 20; echo "exit=$?"
echo "== stop daemon pid $DPID =="
kill $DPID; wait $DPID 2>/dev/null; echo "daemon_wait_exit=$?"
sleep 1
echo "== processes after daemon stop =="
ps aux | grep -E "thox-(agentd|reporter)" | grep -v grep || echo "none running"
echo "== daemon output final =="; cat "$SMOKE_HOME/daemon.out"
echo "SMOKE2_DONE"
