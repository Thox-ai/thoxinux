#!/usr/bin/env python3
"""QEMU regression for the real measured embedded Linux init and SSD state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-dir', required=True, type=Path)
parser.add_argument('--efi', required=True, type=Path)
parser.add_argument('--output-dir', required=True, type=Path)
args = parser.parse_args()
SOURCE = args.source_dir.resolve()
ROOT = args.output_dir.resolve()
if ROOT.exists():
    parser.error('Choose a new output directory; preserve prior state/evidence')


def resolve_accelerator():
    """Return the accelerator upstream tools/qemu/run.sh will actually use.

    run.sh takes QEMU_ACCEL when it is set and accepts only tcg or kvm.
    Otherwise common.sh default_accelerator picks kvm on Linux x86_64
    when /dev/kvm is readable and writable, and tcg everywhere else.
    Mirror that selection exactly so the record names the real run,
    instead of a hardcoded accelerator.
    """
    requested = os.environ.get('QEMU_ACCEL')
    if requested is not None:
        accelerator = requested.strip().lower()
        if accelerator not in ('tcg', 'kvm'):
            parser.error('QEMU_ACCEL must be tcg or kvm')
        return accelerator, 'QEMU_ACCEL environment variable'
    if (platform.system() == 'Linux' and platform.machine() == 'x86_64'
            and os.access('/dev/kvm', os.R_OK | os.W_OK)):
        return 'kvm', 'auto-detected: /dev/kvm readable and writable on Linux x86_64'
    return 'tcg', 'auto-detected: no usable /dev/kvm, upstream default'


def memory_label():
    """Format the GINUX_MEMORY value run.sh will use (its default is 1G)."""
    raw = os.environ.get('GINUX_MEMORY', '1G').strip()
    if raw.endswith('G'):
        return raw[:-1] + ' GiB'
    if raw.endswith('M'):
        return raw[:-1] + ' MiB'
    return raw


ACCELERATOR, ACCELERATOR_SOURCE = resolve_accelerator()
expected_efi = SOURCE / 'build/esp/EFI/BOOT/BOOTX64.EFI'
if args.efi.read_bytes() != expected_efi.read_bytes():
    parser.error('Provided EFI must match the built EFI used by upstream run.sh')
ROOT.mkdir(parents=True)
EFI_SHA = hashlib.sha256(args.efi.read_bytes()).hexdigest()
VOLUME = ROOT / 'lifecycle-volume.raw'

def boot(label, commands, expected_boot):
    output = bytearray()
    env = os.environ.copy()
    env['GINUX_VOLUME_IMAGE'] = str(VOLUME)
    env['GINUX_VOLUME_SIZE'] = '64G'
    proc = subprocess.Popen([str(SOURCE / 'tools/qemu/run.sh')], stdin=subprocess.PIPE,
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
        # Accepted THOX build-profile banners. The Azure candidate line
        # printed the first; the unified ThoxInux series prints the
        # second (thox-identity patch). Either proves a THOX payload;
        # the exact profile is recorded in lifecycle-results.json.
        thox_profiles = ('THOX Azure Compute Edition (QEMU/TCG)',
                         'ThoxInux unified (standalone UEFI)')
        assert any(profile in startup for profile in thox_profiles), startup
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
record = {'test': 'real embedded minimal-system-v0 lifecycle', 'efi_sha256': EFI_SHA,
          'upstream': '36503bda2d87465765e1b94e65f9d100f27ed5be',
          'accelerator': ACCELERATOR,
          'accelerator_source': ACCELERATOR_SOURCE,
          'profile': f'QEMU {ACCELERATOR.upper()}, Q35/OVMF, 1 vCPU, {memory_label()}, 48-bit IOMMU',
          'harness': 'pinned upstream tools/qemu/run.sh with explicit hardware environment',
          'results': results,
          'logs': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                   for name in ['lifecycle-cold.log', 'lifecycle-recovered.log']},
          'claim_limits': ['Local QEMU proof; not Azure-host, Docker, KVM, AVD or physical acceptance',
                           'Embedded init only; no arbitrary Linux workload qualification']}
(ROOT / 'lifecycle-results.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(results))
