#!/usr/bin/env python3
"""Wave 5 Lane E evidence run: the Wave 3 AgentOS loop inside the actual
Ginux kernel guest. Boots the thoxos-shell domain (AgentOS variant
userspace with a pre-seeded config, init thox-shell, no systemd) under
QEMU/KVM via the derived demo image, then drives the loop one console
line at a time (the pattern measured to work in this domain; bash
script files and bash command substitution do not). Each step records
whether its marker appeared; the verdict is read from the transcript.
Transcript written to argv[1].
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, "/usr/lib/thoxos-g")
import thoxos_g
P = b"# "
# (command, marker, timeout) ; marker None = just wait for prompt
STEPS = [
    ("grep PRETTY_NAME /etc/os-release", b'PRETTY_NAME="ThoxOS 0.1.0 Ginux Edition"', 120),
    ("uname -srm", b"Ginux 6.12.0-ginux.0.1 x86_64", 120),
    ("thox version", b"0.1.0", 120),
    ("thox status", b"kernel    Ginux 6.12.0-ginux.0.1", 120),
    ("ls /opt/agentos-bin", b"thox-reporter", 120),
    # in-guest attempt at the shipped seed (expected to fail: measured
    # bash command-substitution failure in this domain; config is the
    # pre-seeded one baked into the image, this attempt has no side
    # effects because the script aborts at its REPO_ROOT line)
    ("export THOX_AGENTOS_HOME=/opt/agentos/state", None, 30),
    ("export THOX_AGENTOS_CONFIG=/opt/agentos/config", None, 30),
    ("sh /opt/agentos-src/scripts/first-boot-seed.sh /opt/agentos-bin > /opt/agentos/seed.log 2>&1; echo seed-exit=$?", b"seed-exit=", 180),
    ("cat /opt/agentos/seed.log; echo seedlog-done", b"seedlog-done", 60),
    ("ls /opt/agentos/config/agents; echo cfg-done", b"reporter.json", 60),
    ("python3 /opt/agentos/manifest.py; echo manifest-done", b"manifest-done", 60),
    ("mkdir -p /opt/agentos/state/run; echo mkdir-done", b"mkdir-done", 60),
    ("/opt/agentos-bin/thox-agentd --state-dir /opt/agentos/state --agents-dir /opt/agentos/config/agents --trust-dir /opt/agentos/config/trust > /opt/agentos/daemon.out 2>&1 & echo $! > /opt/agentos/daemon.pid; echo daemon-launched", b"daemon-launched", 120),
    ("sleep 3; echo slept3", b"slept3", 60),
    ("ls -l /opt/agentos/state/run/agentd.sock; echo sock-check-done", b"sock-check-done", 60),
    ("cat /opt/agentos/daemon.out; echo dout1-done", b"dout1-done", 60),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state list; echo list-exit=$?", b"list-exit=", 120),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state status reporter; echo status-exit=$?", b"status-exit=", 120),
    ("sleep 7; echo slept7", b"slept7", 60),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state logs reporter --lines 5; echo logs-exit=$?", b"logs-exit=", 120),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state audit --lines 10; echo audit-exit=$?", b"audit-exit=", 120),
    ("echo guest-secret-outside-grants > /root/agentos-secret.txt; echo secret-done", b"secret-done", 60),
    ("python3 /opt/agentos/deny.py; echo deny-exit=$?", b"deny-exit=", 180),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state audit --lines 20; echo audit2-exit=$?", b"audit2-exit=", 120),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state stop reporter; echo stop-exit=$?", b"stop-exit=", 120),
    ("sleep 1; echo slept-stop", b"slept-stop", 60),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state status reporter; echo status2-exit=$?", b"status2-exit=", 120),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state start reporter; echo start-exit=$?", b"start-exit=", 120),
    ("sleep 7; echo slept7b", b"slept7b", 60),
    ("/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state logs reporter --lines 3; echo logs2-exit=$?", b"logs2-exit=", 120),
    ("python3 /opt/agentos/term.py; echo term-done", b"term-done", 60),
    ("sleep 3; echo slept-term", b"slept-term", 60),
    ("python3 /opt/agentos/procscan.py; echo scan-done", b"scan-done", 60),
    ("cat /opt/agentos/daemon.out; echo dout2-done", b"dout2-done", 60),
    ("cat /opt/agentos/state/audit.log; echo auditraw-done", b"auditraw-done", 60),
    ("echo GUEST_LOOP_DONE", b"GUEST_LOOP_DONE", 60),
]
def main() -> int:
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/w5-transcript.txt"
    config = thoxos_g.load_config(os.environ)
    os.makedirs(config.state_dir, exist_ok=True)
    stripper = thoxos_g.AnsiStripper()
    transcript = open(transcript_path, "wb")
    def echo(data: bytes) -> None:
        transcript.write(stripper.feed(data)); transcript.flush()
    with thoxos_g.SingleInstance(config.lock_path):
        argv = thoxos_g.assemble(config)
        print("e2e: qemu argv: " + " ".join(argv), file=sys.stderr)
        _, variables = thoxos_g.resolve_firmware(config)
        thoxos_g.prepare_state(config, variables)
        session = thoxos_g.ConsoleSession(argv, echo)
        try:
            thoxos_g.run_boot_sequence(session, config, shell=True)
            session.expect([b"thox ask"], config.boot_timeout)
            session.expect([P], 300)
            for command, marker, timeout in STEPS:
                session.send_line(command)
                if marker is None:
                    session.expect([P], timeout)
                    print(f"e2e: sent  {command}", file=sys.stderr)
                    continue
                try:
                    idx = session.expect([marker, P], timeout)
                    print(f"e2e: {'ok  ' if idx==0 else 'prompt-only'}  {command}", file=sys.stderr)
                    if idx == 0:
                        session.expect([P], timeout)
                except thoxos_g.ThoxosGError as e:
                    print(f"e2e: TIMEOUT {command}: {e}", file=sys.stderr)
            session.send_line("exit")
            try:
                session.expect([b"ginux> "], 120)
                print("e2e: shell exit returned to the controller", file=sys.stderr)
            except thoxos_g.ThoxosGError:
                print("e2e: no controller return on exit", file=sys.stderr)
            return 0
        finally:
            session.terminate(); transcript.close()
if __name__ == "__main__":
    sys.exit(main())
