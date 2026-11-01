#!/usr/bin/env python3
"""Wave 5 Lane E evidence run, system domain: boots the SAME derived
demo image in system mode (init /sbin/init, systemd) and lets the
baked agentos-w5e.service run the AgentOS loop (driver2.py) under
systemd supervision. Output reaches the serial console via
StandardOutput=journal+console; the transcript is the evidence.
No interactive login is used.
"""
from __future__ import annotations
import os, sys
sys.path.insert(0, "/usr/lib/thoxos-g")
import thoxos_g
def main() -> int:
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/w5-sys.txt"
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
            thoxos_g.run_boot_sequence(session, config, shell=False)
            print("e2e: system domain start sent; waiting for LOOP_DONE_MARKER", file=sys.stderr)
            try:
                session.expect([b"DRIVER_DONE"], 1500)
                print("e2e: LOOP_DONE_MARKER seen on the system domain console", file=sys.stderr)
            except thoxos_g.ThoxosGError as e:
                print(f"e2e: LOOP_DONE_MARKER timeout: {e}", file=sys.stderr)
            try:
                session.expect([b"login:"], 120)
                print("e2e: login prompt present after the run", file=sys.stderr)
            except thoxos_g.ThoxosGError:
                print("e2e: no login prompt seen (transcript is the verdict)", file=sys.stderr)
            return 0
        finally:
            session.terminate(); transcript.close()
if __name__ == "__main__":
    sys.exit(main())
