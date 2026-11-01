# Quick start

Five minutes from clone to a supervised, audited agent. Every command here was run and verified on 2026-10-31 (Ubuntu 24.04.5, rustc 1.99.1).

## 1. Test

```sh
cargo test
```

Expected: 9 integration tests pass, covering identity refusal, capability denial, audit append, supervisor restart, and model swap rollback.

## 2. Run the development stack

```sh
scripts/run-dev.sh
```

This builds debug binaries, seeds a throwaway home under `target/dev-home` (issuer key pair, trust store entry, signed reporter manifest), and starts thox-agentd in the foreground. The reporter agent autostarts.

## 3. Talk to it

From a second terminal in the repo root:

```sh
export THOX_AGENTOS_HOME="$PWD/target/dev-home/state"
alias thox-agent="$PWD/target/debug/thox-agent --state-dir $THOX_AGENTOS_HOME"

thox-agent list                 # reporter: running
thox-agent logs reporter        # STATUS lines from real OS state, via the broker
thox-agent audit                # every broker and supervisor decision
thox-agent stop reporter
thox-agent start reporter
```

## 4. Swap the kernel model

The model slot records name, source, and digest. No weights live in this repo.

```sh
cat > /tmp/model.json <<'EOF'
{"name":"my-kernel-model","source":"hf:example/my-model","digest":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","format":"gguf"}
EOF
thox-agent model swap /tmp/model.json
thox-agent model show
thox-agent model rollback       # back to the previous model, if one was active
```

For a local model file, set `source` to the file path: the swap verifies the file SHA-256 against `digest` and refuses a mismatch, leaving the active model untouched.

## 5. Install for real

```sh
scripts/install.sh              # user install plus systemd user unit
scripts/install.sh --system     # Omarchy/Arch track: /usr/local/bin plus system unit
```

Then `systemctl --user enable --now thox-agentd` (user) or `systemctl enable --now thox-agentd` (system). See the user guide for the system layout and first-boot seeding on an OS image.
