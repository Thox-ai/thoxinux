#!/usr/bin/env python3
# Wave 5 Lane E guest driver, phase 1 of 2: identity, payload, the
# in-guest seed attempt, and the reporter manifest. Written to make
# exactly ONE fork (the seed attempt): everything else is done
# in-process, because the Ginux shell domain has faulted under
# fork/exec churn (kernel panic, fatal exception vector 8, at the
# start of the previous single-driver attempt, and FS-resume
# mismatches in earlier multi-cycle attempts).
import os, runpy, subprocess, sys
BIN = "/opt/agentos-bin"
def show(label):
    print(f"=== [ginux-guest] {label} ===", flush=True)
def main():
    show("identity (in-process)")
    with open("/etc/os-release") as f:
        print("".join(f.readlines()[:4]), end="", flush=True)
    u = os.uname()
    print(f"{u.sysname} {u.release} {u.machine}", flush=True)
    print(f"uid={os.getuid()} gid={os.getgid()} groups={os.getgroups()}", flush=True)
    show("agentos payload (in-process)")
    for d in ["/opt/agentos-bin", "/opt/agentos-src/scripts", "/opt/agentos"]:
        print(f"{d}: {sorted(os.listdir(d))}", flush=True)
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
    runpy.run_path("/opt/agentos/manifest.py")
    print("DRIVER1_DONE", flush=True)
    return 0
if __name__ == "__main__":
    sys.exit(main())
