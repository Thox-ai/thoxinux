#!/usr/bin/env python3
"""Wave 5 Lane E evidence run, mode B: pre-steps as individual lines,
then the daemon loop in five medium lines (a single ~1.9 KB line was
rejected by the domain with E2BIG). Each line is awaited by prompt;
the verdict is read from the transcript, not from echoed markers.
Transcript written to argv[1].
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, "/usr/lib/thoxos-g")
import thoxos_g
P = b"# "
PRE = [
    "grep PRETTY_NAME /etc/os-release",
    "uname -srm",
    "thox version",
    "thox status",
    "ls /opt/agentos-bin",
    "export THOX_AGENTOS_HOME=/opt/agentos/state",
    "export THOX_AGENTOS_CONFIG=/opt/agentos/config",
    "sh /opt/agentos-src/scripts/first-boot-seed.sh /opt/agentos-bin > /opt/agentos/seed.log 2>&1; echo seed-exit=$?",
    "cat /opt/agentos/seed.log; echo seedlog-done",
    "python3 /opt/agentos/manifest.py; echo manifest-done",
]
AG = "/opt/agentos-bin/thox-agent --state-dir /opt/agentos/state"
LOOP_LINES = [
    # L1: start daemon, capture pid, socket + daemon.out check
    "mkdir -p /opt/agentos/state/run; /opt/agentos-bin/thox-agentd --state-dir /opt/agentos/state --agents-dir /opt/agentos/config/agents --trust-dir /opt/agentos/config/trust > /opt/agentos/daemon.out 2>&1 & echo $! > /opt/agentos/daemon.pid; /usr/bin/sleep 4; /usr/bin/ls -l /opt/agentos/state/run/agentd.sock; /usr/bin/cat /opt/agentos/daemon.out; echo L1-DONE",
    # L2: list, status, reporter STATUS via logs, audit (identity + grants)
    f"{AG} list; {AG} status reporter; /usr/bin/sleep 7; {AG} logs reporter --lines 5; {AG} audit --lines 10; echo L2-DONE",
    # L3: denial probes + audit
    f"echo guest-secret-outside-grants > /root/agentos-secret.txt; /usr/bin/python3 /opt/agentos/deny.py; {AG} audit --lines 20; echo L3-DONE",
    # L4: stop / start lifecycle
    f"{AG} stop reporter; /usr/bin/sleep 1; {AG} status reporter; {AG} start reporter; /usr/bin/sleep 7; {AG} logs reporter --lines 3; echo L4-DONE",
    # L5: SIGTERM the daemon (F2 path), verify no processes, dump outputs
    "/usr/bin/python3 /opt/agentos/term.py; /usr/bin/sleep 3; /usr/bin/python3 /opt/agentos/procscan.py; /usr/bin/cat /opt/agentos/daemon.out; /usr/bin/cat /opt/agentos/state/audit.log; echo L5-DONE",
]
POST = [
    "cat /opt/agentos/state/audit.log; echo postaudit-done",
    "echo GUEST_LOOP_DONE",
]
def run_line(session, command, timeout):
    session.send_line(command)
    try:
        session.expect([P], timeout)
        print(f"e2e: line done: {command[:70]}...", file=sys.stderr)
        return True
    except thoxos_g.ThoxosGError as e:
        print(f"e2e: line TIMEOUT: {command[:70]}...: {e}", file=sys.stderr)
        return False
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
            for cmd in PRE:
                run_line(session, cmd, 180)
            for cmd in LOOP_LINES:
                if not run_line(session, cmd, 600):
                    break
            else:
                for cmd in POST:
                    run_line(session, cmd, 180)
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
