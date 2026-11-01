import json, socket
SOCK = "/opt/agentos/state/run/agentd.sock"
def call(obj):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(10)
    s.connect(SOCK)
    s.sendall((json.dumps(obj) + "\n").encode())
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    s.close()
    print(json.dumps(obj), "->", data.decode().strip(), flush=True)
call({"cmd": "tool", "agent": "reporter", "tool": "fs.read", "params": {"path": "/root/agentos-secret.txt"}})
call({"cmd": "tool", "agent": "reporter", "tool": "exec", "params": {"program": "/usr/bin/id", "args": []}})
call({"cmd": "tool", "agent": "reporter", "tool": "net.http_get", "params": {"url": "http://127.0.0.1:9/"}})
call({"cmd": "tool", "agent": "reporter", "tool": "fs.read", "params": {"path": "/proc/uptime"}})
