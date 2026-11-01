#!/usr/bin/env python3
# Wave 5 Lane E guest driver, phase 2 of 2: the Wave 3 AgentOS loop
# (daemon up, reporter identity verified, broker-mediated reads,
# three capability denials, stop/start, SIGTERM shutdown) inside one
# Python process, so the domain init resumes only once, after the
# daemon has exited. AgentOS binaries invoked exactly as in Wave 3.
import os, runpy, signal, stat, subprocess, sys, time
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
    show("start thox-agentd (no systemd, run-dev.sh pattern)")
    os.makedirs(f"{STATE}/run", exist_ok=True)
    dout = open("/opt/agentos/daemon.out", "wb")
    daemon = subprocess.Popen(
        [f"{BIN}/thox-agentd", "--state-dir", STATE, "--agents-dir", f"{CONFIG}/agents",
         "--trust-dir", f"{CONFIG}/trust"],
        stdout=dout, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    print(f"daemon_pid={daemon.pid}", flush=True)
    sock = f"{STATE}/run/agentd.sock"
    ok = False
    for _ in range(50):
        try:
            if stat.S_ISSOCK(os.stat(sock).st_mode):
                ok = True
                break
        except OSError:
            pass
        time.sleep(0.2)
    print(f"socket_present={ok} path={sock}", flush=True)
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
    runpy.run_path("/opt/agentos/procscan.py")
    show("daemon output final")
    print(open("/opt/agentos/daemon.out").read(), end="", flush=True)
    show("audit.log file (raw)")
    print(open(f"{STATE}/audit.log").read(), end="", flush=True)
    print("DRIVER_DONE", flush=True)
    return 0
if __name__ == "__main__":
    sys.exit(main())
