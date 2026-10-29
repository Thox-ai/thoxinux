#!/usr/bin/env python3
"""QEMU regression for the real measured embedded Linux init and SSD state."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import time

ROOT = Path(__file__).resolve().parent
VOLUME = ROOT / 'lifecycle-volume.raw'

def boot(label, commands, expected_boot):
    output = bytearray()
    env = os.environ.copy()
    env['GINUX_VOLUME_IMAGE'] = str(VOLUME)
    env['GINUX_VOLUME_SIZE'] = '64G'
    proc = subprocess.Popen([str(ROOT / 'ginux/tools/qemu/run.sh')], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    poll = selectors.DefaultSelector()
    poll.register(proc.stdout, selectors.EVENT_READ)
    def wait(cursor, marker=b'ginux> ', timeout=40):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if b'GINUX_KERNEL_PANIC' in output or b'GINUX_BOOT_PANIC' in output:
                raise RuntimeError('kernel panic')
            if marker in output[cursor:]:
                return bytes(output[cursor:]).decode('utf8', 'replace')
            if proc.poll() is not None:
                raise RuntimeError('unexpected QEMU exit')
            for key, _ in poll.select(0.2):
                block = os.read(key.fd, 65536)
                if block:
                    output.extend(block)
                    (ROOT / f'lifecycle-{label}.log').write_bytes(output)
        raise TimeoutError(f'{label}: waiting for {marker!r}')
    try:
        startup = wait(0)
        assert expected_boot in startup, startup
        for command, expected in commands:
            cursor = len(output)
            proc.stdin.write((command + '\n').encode())
            proc.stdin.flush()
            response = wait(cursor)
            print(label + ': ' + command, flush=True)
            assert expected in response, f'{command}: missing {expected!r}: {response}'
        cursor = len(output)
        proc.stdin.write(b'shutdown\n')
        proc.stdin.flush()
        wait(cursor, b'GINUX_KERNEL_OK')
        assert proc.wait(timeout=15) == 0
        output.extend(proc.stdout.read())
        assert b'THOX_DIAG' not in output
        return {'boot': label, 'result': 'passed', 'commands': len(commands)}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        output.extend(proc.stdout.read())
        (ROOT / f'lifecycle-{label}.log').write_bytes(output)
        poll.close()

if VOLUME.exists():
    VOLUME.unlink()
state = lambda value: ('domain status thoxprobe', 'State:       ' + value)
commands = [
    ('domain new thoxprobe', 'thoxprobe: created'),
    ('domain set thoxprobe image=embedded://minimal-system-v0 init=/sbin/init memory-mib=128 autostart=false', 'settings accepted'),
    ('domain start thoxprobe', 'running'), state('running'),
    ('ps', '100'),
    ('domain stop thoxprobe', 'stopped'), state('stopped'),
    ('domain start thoxprobe', 'running'), state('running'),
    ('domain restart thoxprobe', 'running'), state('running'),
    ('domain fail thoxprobe', 'failed'), state('failed'),
    ('domain start thoxprobe', 'running'), state('running'),
    ('domain stop thoxprobe', 'stopped'), state('stopped'),
]
results = [boot('cold', commands, 'persistent storage initialized')]
results.append(boot('recovered', [state('configured'),
    ('domain start thoxprobe', 'running'), state('running'),
    ('domain stop thoxprobe', 'stopped'), state('stopped')], 'persistent storage recovered'))
(ROOT / 'lifecycle-results.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results))
