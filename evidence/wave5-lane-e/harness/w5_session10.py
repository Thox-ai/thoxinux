#!/usr/bin/env python3
"""Wave 5 Lane E evidence run, hybrid mode: PRE identity/seed/manifest
lines (proven pattern), ONE line launching thox-agentd in the
background from the interactive shell (proven pattern, attempt 2),
then ONE Python driver (driver3.py) for every remaining loop step:
thox-agent calls via subprocess (proven safe, diag12), denial probes
in-process over the broker socket, SIGTERM to the daemon by pid.
The domain init resumes with the daemon resident only twice.
Transcript written to argv[1]; the verdict is read from it.
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
LAUNCH = "mkdir -p /opt/agentos/state/run; /opt/agentos-bin/thox-agentd --state-dir /opt/agentos/state --agents-dir /opt/agentos/config/agents --trust-dir /opt/agentos/config/trust > /opt/agentos/daemon.out 2>&1 & echo $! > /opt/agentos/daemon.pid; echo daemon-launched"
DRIVER3 = "python3 /opt/agentos/driver3.py; echo driver3-exit=$?"
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
            if run_line(session, LAUNCH, 300) and run_line(session, DRIVER3, 900):
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
