#!/usr/bin/env python3
"""Diagnostic 7: discriminate the deterministic panic at python3 driver
exec. Steps ordered least-likely-to-kill first; markers tell us which
step the domain died on (transcript is the verdict)."""
from __future__ import annotations
import os, sys
sys.path.insert(0, "/usr/lib/thoxos-g")
import thoxos_g
P = b"# "
STEPS = [
    "python3 -c \"import subprocess; r = subprocess.run(['/opt/agentos-bin/thox-agent', '--help']); print('agent-help-rc', r.returncode)\"; echo pa-exit=$?",
    "python3 -c \"import subprocess; r = subprocess.run(['/opt/agentos-bin/thox-reporter', '--help']); print('reporter-help-rc', r.returncode)\"; echo pr-exit=$?",
]
def main() -> int:
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/w5-diag12.txt"
    config = thoxos_g.load_config(os.environ)
    os.makedirs(config.state_dir, exist_ok=True)
    stripper = thoxos_g.AnsiStripper()
    transcript = open(transcript_path, "wb")
    def echo(data: bytes) -> None:
        transcript.write(stripper.feed(data)); transcript.flush()
    with thoxos_g.SingleInstance(config.lock_path):
        argv = thoxos_g.assemble(config)
        _, variables = thoxos_g.resolve_firmware(config)
        thoxos_g.prepare_state(config, variables)
        session = thoxos_g.ConsoleSession(argv, echo)
        try:
            thoxos_g.run_boot_sequence(session, config, shell=True)
            session.expect([b"thox ask"], config.boot_timeout)
            session.expect([P], 300)
            for command in STEPS:
                session.send_line(command)
                try:
                    session.expect([P], 180)
                    print(f"diag12: prompt after: {command[:60]}", file=sys.stderr)
                except thoxos_g.ThoxosGError as e:
                    print(f"diag12: TIMEOUT after: {command[:60]}: {e}", file=sys.stderr)
                    break
            session.send_line("exit")
            try:
                session.expect([b"ginux> "], 60)
            except thoxos_g.ThoxosGError:
                print("diag12: no controller return", file=sys.stderr)
            return 0
        finally:
            session.terminate(); transcript.close()
if __name__ == "__main__":
    sys.exit(main())
