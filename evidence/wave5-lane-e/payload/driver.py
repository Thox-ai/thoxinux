#!/usr/bin/env python3
# Wave 5 Lane E guest driver: the Wave 3 guest-run.sh loop, driven by a
# single Python process inside the Ginux shell domain. Python is used
# because bash in this domain cannot run it reliably (measured: script
# files exit after the first external command, command substitution
# returns empty, long lines hit E2BIG, mixed background/foreground
# lines hit child-exec precondition rejections). thox-shell itself is
# a Python process driving subprocesses, the pattern the domain
# handles. All AgentOS binaries are invoked exactly as in Wave 3.
import os, runpy, signal, socket, stat, subprocess, sys, time

STATE = "/opt/agentos/state"
CONFIG = "/opt/agentos/config"
BIN = "/opt/agentos-bin"
AG = [f"{BIN}/thox-agent", "--state-dir", STATE]

def show(label):
    print(f"=== [ginux-guest] {label} ===", flush=True)

def run(cmd, **kw):
    print("+ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)
    if r.stdout:
        print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", flush=True)
    print(f"exit={r.returncode}", flush=True)
    return r

def main():
    show("identity")
    with open("/etc/os-release") as f:
        print("".join(f.readlines()[:4]), end="", flush=True)
    run(["/usr/bin/uname", "-srm"])
    run(["/usr/bin/id"])
    run(["/usr/local/bin/thox", "version"])
    run(["/usr/local/bin/thox", "status"])
    show("agentos payload")
    run(["/usr/bin/ls", "-l", "/opt/agentos-bin", "/opt/agentos-src/scripts", "/opt/agentos"])
    show("seed attempt (shipped first-boot-seed.sh, in-guest)")
    with open("/opt/agentos/seed.log", "w") as log:
        r = subprocess.run(["/bin/sh", "/opt/agentos-src/scripts/first-boot-seed.sh", BIN],
                           stdout=log, stderr=subprocess.STDOUT, timeout=120)
    print(f"seed_exit={r.returncode}", flush=True)
    with open("/opt/agentos/seed.log") as f:
        print(f.read(), end="", flush=True)
    print("note: seed aborts in this domain (bash command substitution returns empty); "
          "the config in /opt/agentos/config was produced by the same shipped script, "
          "unmodified, in the userspace container and baked into this image.", flush=True)
    show("reporter manifest (identity_token truncated)")
    run(["/usr/bin/python3", "/opt/agentos/manifest.py"])
    show("start thox-agentd (no systemd, run-dev.sh pattern)")
    os.makedirs(f"{STATE}/run", exist_ok=True)
    dout = open("/opt/agentos/daemon.out", "wb")
    daemon = subprocess.Popen(
        [f"{BIN}/thox-agentd", "--state-dir", STATE, "--agents-dir", f"{CONFIG}/agents",
         "--trust-dir", f"{CONFIG}/trust"],
        stdout=dout, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    print(f"daemon_pid={daemon.pid}", flush=True)
    sock = f"{STATE}/run/agentd.sock"
    for _ in range(50):
        try:
            if stat.S_ISSOCK(os.stat(sock).st_mode):
                break
        except OSError:
            pass
        time.sleep(0.2)
    run(["/usr/bin/ls", "-l", sock])
    time.sleep(3)
    show("daemon output so far")
    print(open("/opt/agentos/daemon.out").read(), end="", flush=True)
    show("thox-agent list")
    run(AG + ["list"])
    show("thox-agent status reporter")
    run(AG + ["status", "reporter"])
    time.sleep(7)
    show("thox-agent logs reporter --lines 5 (broker-mediated STATUS)")
    run(AG + ["logs", "reporter", "--lines", "5"])
    show("thox-agent audit --lines 10 (identity verify + broker allow)")
    run(AG + ["audit", "--lines", "10"])
    show("capability denial probes (direct broker requests as reporter)")
    with open("/root/agentos-secret.txt", "w") as f:
        f.write("guest-secret-outside-grants\n")
    runpy.run_path("/opt/agentos/deny.py")
    print("deny_probe_done", flush=True)
    show("thox-agent audit --lines 20 (denials logged)")
    run(AG + ["audit", "--lines", "20"])
    show("thox-agent stop reporter")
    run(AG + ["stop", "reporter"])
    time.sleep(1)
    show("thox-agent status reporter (after stop)")
    run(AG + ["status", "reporter"])
    show("thox-agent start reporter")
    run(AG + ["start", "reporter"])
    time.sleep(7)
    show("thox-agent logs reporter --lines 3 (after restart)")
    run(AG + ["logs", "reporter", "--lines", "3"])
    show("SIGTERM daemon (F2 shutdown path)")
    daemon.send_signal(signal.SIGTERM)
    try:
        rc = daemon.wait(timeout=15)
    except subprocess.TimeoutExpired:
        print("daemon did not exit in 15 s", flush=True)
        rc = None
    print(f"daemon_exit={rc}", flush=True)
    time.sleep(1)
    show("processes after daemon stop")
    run(["/usr/bin/python3", "/opt/agentos/procscan.py"])
    show("daemon output final")
    print(open("/opt/agentos/daemon.out").read(), end="", flush=True)
    show("audit.log file (raw)")
    print(open(f"{STATE}/audit.log").read(), end="", flush=True)
    print("DRIVER_DONE", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
