#!/usr/bin/env python3
"""Bounded real controller boot test on the deployed Azure Linux host."""
import argparse
import hashlib
import json
import os
import pathlib
import selectors
import subprocess
import time


def run(output):
    output.mkdir(parents=True, exist_ok=True)
    command = ["runuser", "-u", "thoxginux", "--", "env", "HOME=/var/lib/thox-ginux", "QEMU_ACCEL=tcg", "GINUX_MEMORY=2G", "/usr/local/bin/thox-ginux"]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    capture = bytearray()
    started = time.monotonic()
    completed = []

    def wait_for(marker, begin, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if marker in capture[begin:]:
                return
            if b"GINUX_KERNEL_PANIC" in capture or b"GINUX_BOOT_PANIC" in capture:
                raise RuntimeError("Ginux panic")
            if process.poll() is not None:
                raise RuntimeError("Guest exited before expected controller marker")
            for key, _ in selector.select(0.5):
                chunk = os.read(key.fd, 65536)
                if chunk:
                    capture.extend(chunk)
        raise TimeoutError("Controller marker timeout")

    outcome = "failed"
    error = None
    try:
        wait_for(b"ginux> ", 0, 120)
        if b"ThoxOS Ginux Research Edition" not in capture:
            raise RuntimeError("THOX research banner missing")
        for command in ("status", "components", "domain list", "help"):
            begin = len(capture)
            process.stdin.write((command + "\n").encode())
            process.stdin.flush()
            wait_for(b"ginux> ", begin, 30)
            completed.append(command)
        process.stdin.write(b"shutdown\n")
        process.stdin.flush()
        process.wait(timeout=30)
        capture.extend(process.stdout.read())
        if process.returncode != 0 or b"GINUX_KERNEL_OK" not in capture:
            raise RuntimeError("Clean kernel shutdown not observed")
        outcome = "passed"
    except (RuntimeError, TimeoutError, subprocess.TimeoutExpired, BrokenPipeError) as exc:
        error = str(exc)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        capture.extend(process.stdout.read())
    finally:
        selector.close()
    (output / "guest-smoke.log").write_bytes(capture)
    result = {"test": "Azure host real Ginux controller boot", "outcome": outcome, "commands": completed, "error": error, "elapsed_seconds": round(time.monotonic() - started, 2), "exit_code": process.returncode, "log_sha256": hashlib.sha256(capture).hexdigest(), "claim_limits": "QEMU TCG controller only; no Linux-domain, GUI, GPU, AVD or native Ginux Azure boot claim"}
    (output / "guest-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0 if outcome == "passed" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    raise SystemExit(run(parser.parse_args().output))
