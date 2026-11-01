#!/usr/bin/env python3
"""End-to-end ThoxOS shell session on the Ginux kernel.

Boots the `thoxos-shell` domain (same ThoxOS image, init thox-shell, no
systemd), waits for the shell prompt, runs commands, and checks each output.
Writes the console transcript (escape sequences removed) to argv[1] and exits 0
only when every step produced its expected output.

    docker run --rm -v "$PWD/tests/e2e:/e2e:ro" -v "$PWD/build/e2e:/out" \
        thoxos-g/demo:0.1.0 exec python3 -I /e2e/shell_session.py /out/shell-transcript.txt

Steps: `cat /etc/os-release`, `uname -srm`, `thox status`, `thox version`,
`id thox`, then `exit`, which stops the domain.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, "/usr/lib/thoxos-g")

import thoxos_g  # noqa: E402

SHELL_PROMPT = b"# "
STEPS = [
    ("grep PRETTY_NAME /etc/os-release", b'PRETTY_NAME="ThoxOS 0.1.0 Ginux Edition"'),
    ("uname -srm", b"x86_64"),
    ("thox status", b"os        ThoxOS 0.1.0 Ginux Edition"),
    ("thox version", b"\n0.1.0\r"),
    ("id thox", b"uid=1000(thox)"),
]


def main() -> int:
    transcript_path = sys.argv[1] if len(sys.argv) > 1 else "/tmp/thoxos-shell-e2e.txt"
    config = thoxos_g.load_config(os.environ)
    os.makedirs(config.state_dir, exist_ok=True)
    stripper = thoxos_g.AnsiStripper()
    transcript = open(transcript_path, "wb")

    def echo(data: bytes) -> None:
        transcript.write(stripper.feed(data))
        transcript.flush()

    with thoxos_g.SingleInstance(config.lock_path):
        argv = thoxos_g.assemble(config)
        _, variables = thoxos_g.resolve_firmware(config)
        thoxos_g.prepare_state(config, variables)
        session = thoxos_g.ConsoleSession(argv, echo)
        try:
            thoxos_g.run_boot_sequence(session, config, shell=True)
            session.expect([b"thox ask"], config.boot_timeout)  # motd printed by thox-shell
            session.expect([SHELL_PROMPT], 300)
            for command, expected in STEPS:
                session.send_line(command)
                session.expect([expected], 300)
                session.expect([SHELL_PROMPT], 300)
                print(f"e2e: ok  {command}", file=sys.stderr)
            session.send_line("exit")
            session.expect([b"ginux> "], 300)
            print("e2e: all steps passed; shell exit returned to the controller", file=sys.stderr)
            return 0
        except thoxos_g.ThoxosGError as error:
            print(f"e2e: FAIL {error}", file=sys.stderr)
            return 1
        finally:
            session.terminate()
            transcript.close()


if __name__ == "__main__":
    sys.exit(main())
