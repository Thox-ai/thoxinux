#!/bin/bash
# Smoke: seed reporter, start thox-agentd, exercise thox-agent CLI, stop daemon.
set -u
cd "$(dirname "$0")"
export THOX_AGENTOS_HOME="$PWD/target/dev-home/state"
export THOX_AGENTOS_CONFIG="$PWD/target/dev-home/config"
rm -rf target/dev-home
echo "== thox-agentd --help =="
target/debug/thox-agentd --help; echo "help_exit=$?"
echo "== thox-agent (no args, usage expected) =="
target/debug/thox-agent 2>&1; echo "usage_exit=$?"
echo "== seed (scripts/first-boot-seed.sh target/debug) =="
scripts/first-boot-seed.sh "$PWD/target/debug"; echo "seed_exit=$?"
echo "== start thox-agentd in background =="
target/debug/thox-agentd --state-dir "$THOX_AGENTOS_HOME" --agents-dir "$THOX_AGENTOS_CONFIG/agents" --trust-dir "$THOX_AGENTOS_CONFIG/trust" > target/dev-home/daemon.out 2>&1 &
DPID=$!
echo "daemon_pid=$DPID"
for i in $(seq 1 50); do [ -S "$THOX_AGENTOS_HOME/run/agentd.sock" ] && break; sleep 0.2; done
ls -l "$THOX_AGENTOS_HOME/run/agentd.sock"
sleep 7
echo "== daemon output so far =="
cat target/dev-home/daemon.out
AG="target/debug/thox-agent --state-dir $THOX_AGENTOS_HOME"
echo "== thox-agent list =="; $AG list; echo "exit=$?"
echo "== thox-agent status =="; $AG status; echo "exit=$?"
echo "== thox-agent status reporter =="; $AG status reporter; echo "exit=$?"
echo "== thox-agent logs reporter --lines 5 =="; $AG logs reporter --lines 5; echo "exit=$?"
echo "== thox-agent audit --lines 10 =="; $AG audit --lines 10; echo "exit=$?"
echo "== thox-agent model show =="; $AG model show; echo "exit=$?"
echo "== thox-agent stop reporter =="; $AG stop reporter; echo "exit=$?"
sleep 1
echo "== thox-agent status reporter (after stop) =="; $AG status reporter; echo "exit=$?"
echo "== thox-agent start reporter =="; $AG start reporter; echo "exit=$?"
sleep 6
echo "== thox-agent logs reporter --lines 3 (after restart) =="; $AG logs reporter --lines 3; echo "exit=$?"
echo "== stop daemon pid $DPID =="
kill $DPID; wait $DPID 2>/dev/null; echo "daemon_wait_exit=$?"
echo "== daemon output final =="
cat target/dev-home/daemon.out
echo "SMOKE_DONE"
