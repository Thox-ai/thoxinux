import os
found=[]
for pid in os.listdir('/proc'):
    if not pid.isdigit():
        continue
    try:
        with open(f'/proc/{pid}/cmdline','rb') as f:
            cmd=f.read().replace(b'\x00',b' ').decode('utf-8','replace').strip()
    except OSError:
        continue
    if 'thox-agentd' in cmd or 'thox-reporter' in cmd or 'agentos-realbin' in cmd:
        found.append((pid,cmd))
print(found if found else "none running")
