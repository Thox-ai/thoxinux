import os, signal
pid=int(open('/opt/agentos/daemon.pid').read().strip())
os.kill(pid, signal.SIGTERM)
print(f"sigterm-sent-to-{pid}")
