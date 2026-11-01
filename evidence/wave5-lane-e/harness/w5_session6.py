#!/usr/bin/env python3
"""Wave 5 Lane E evidence run, mode C: pre-steps as individual lines,
then the ENTIRE agentos loop inside one Python driver process
(/opt/agentos/driver.py). Rationale, measured in attempts 1-4: the
Ginux shell domain faults with an FS-resume mismatch when the init
shell resumes across many command cycles with the daemon resident;
one Python driver means the domain init resumes only once, after the
daemon has received SIGTERM and exited. The verdict is read from the
transcript, not from echoed markers. Transcript written to argv[1].
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
]
DRIVER = ["python3 /opt/agentos/driver.py; echo driver-exit=$?"]
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
            ok = True
            for cmd in DRIVER:
                if not run_line(session, cmd, 900):
                    ok = False
                    break
            if ok:
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
