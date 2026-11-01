#!/usr/bin/env python3
# Fork-stage probe: unbuffered os.write markers around three forks.
# F1: subprocess.run /bin/true (console stdio inherited via capture)
# F2: subprocess.run /bin/true with stdout redirected to a file
# F3: Popen(thox-agentd) + socket poll + SIGTERM + wait (daemon fork)
import os, stat, subprocess, sys, time
def mark(s):
    os.write(1, f"MARK {s}\n".encode())
mark("S0 start")
r = subprocess.run(["/bin/true"], capture_output=True)
mark(f"F1 true rc={r.returncode}")
with open("/opt/agentos/forkprobe.log", "w") as log:
    r = subprocess.run(["/bin/true"], stdout=log, stderr=subprocess.STDOUT)
mark(f"F2 true-file rc={r.returncode}")
os.makedirs("/opt/agentos/state/run", exist_ok=True)
dout = open("/opt/agentos/daemon.out", "wb")
d = subprocess.Popen(["/opt/agentos-bin/thox-agentd", "--state-dir", "/opt/agentos/state",
                      "--agents-dir", "/opt/agentos/config/agents",
                      "--trust-dir", "/opt/agentos/config/trust"],
                     stdout=dout, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
mark(f"F3 daemon pid={d.pid}")
sock = "/opt/agentos/state/run/agentd.sock"
ok = False
for _ in range(50):
    try:
        if stat.S_ISSOCK(os.stat(sock).st_mode):
            ok = True; break
    except OSError:
        pass
    time.sleep(0.2)
mark(f"F3 socket={ok}")
time.sleep(3)
try:
    data = open("/opt/agentos/daemon.out").read()
    os.write(1, ("DAEMONOUT-BEGIN\n" + data + "DAEMONOUT-END\n").encode())
except OSError as e:
    mark(f"daemon.out read failed {e}")
import signal
d.send_signal(signal.SIGTERM)
try:
    rc = d.wait(timeout=15)
except subprocess.TimeoutExpired:
    rc = None
mark(f"F3 daemon_exit={rc}")
mark("S9 done")
