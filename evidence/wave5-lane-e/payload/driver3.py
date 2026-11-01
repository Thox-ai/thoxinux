#!/usr/bin/env python3
# Wave 5 Lane E guest driver, hybrid edition: the daemon was launched
# by the interactive shell (the parent pattern proven in evidence
# attempt 2); this process performs every remaining Wave 3 loop step.
# It never execs thox-agentd (a Python parent exec of the daemon
# faults the Ginux domain at a fixed RIP, measured in diag11 and in
# the system-domain attempt); it execs thox-agent (proven safe in
# diag12), runs the denial probes in-process over the broker socket,
# and stops the daemon with SIGTERM by pid (F2 shutdown path).
import os, runpy, signal, stat, subprocess, sys, time
STATE = "/opt/agentos/state"
BIN = "/opt/agentos-bin"
AG = [f"{BIN}/thox-agent", "--state-dir", STATE]
def show(label):
    print(f"=== [ginux-guest] {label} ===", flush=True)
def run(cmd, **kw):
    print("+ " + " ".join(cmd), flush=True)
    r = None
    for attempt in range(60):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)
            break
        except OSError as e:
            # The Ginux domain rejects child execs while the process
            # tree is busy (EAGAIN, measured); retry until it lands.
            print(f"exec retry {attempt}: {e}", flush=True)
            time.sleep(0.5)
    if r is None:
        raise RuntimeError(f"could not exec {cmd[0]} after retries")
    if r.stdout:
        print(r.stdout, end="", flush=True)
    if r.stderr:
        print(r.stderr, end="", flush=True)
    print(f"exit={r.returncode}", flush=True)
    return r
def proc_state(pid):
    try:
        with open(f"/proc/{pid}/stat") as f:
            return f.read().rsplit(") ", 1)[1].split()[0]
    except OSError:
        return None
def find_daemon_pid():
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                cmd = f.read().replace(b"\x00", b" ").decode("utf-8", "replace")
        except OSError:
            continue
        if "thox-agentd" in cmd:
            return int(pid)
    return None
def main():
    time.sleep(5)
    dpid = None
    for _ in range(60):
        dpid = find_daemon_pid()
        if dpid is not None:
            break
        time.sleep(0.5)
    print(f"daemon_pid={dpid} state={proc_state(dpid) if dpid else None}", flush=True)
    sock = f"{STATE}/run/agentd.sock"
    ok = False
    for _ in range(150):
        try:
            if stat.S_ISSOCK(os.stat(sock).st_mode):
                ok = True
                break
        except OSError:
            pass
        time.sleep(0.2)
    print(f"socket_present={ok} path={sock}", flush=True)
    show("daemon output so far")
    try:
        print(open("/opt/agentos/daemon.out").read(), end="", flush=True)
    except OSError:
        print("(daemon stdout is on the journal/console in systemd mode)", flush=True)
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
    os.kill(dpid, signal.SIGTERM)
    final = None
    for _ in range(75):
        st = proc_state(dpid)
        if st is None or st in ("Z", "X"):
            final = st
            break
        time.sleep(0.2)
    print(f"daemon_state_after_term={final}", flush=True)
    time.sleep(1)
    show("processes after daemon stop")
    runpy.run_path("/opt/agentos/procscan.py")
    show("daemon output final")
    try:
        print(open("/opt/agentos/daemon.out").read(), end="", flush=True)
    except OSError:
        print("(daemon stdout is on the journal/console in systemd mode)", flush=True)
    show("audit.log file (raw)")
    print(open(f"{STATE}/audit.log").read(), end="", flush=True)
    print("DRIVER_DONE", flush=True)
    return 0
if __name__ == "__main__":
    sys.exit(main())
