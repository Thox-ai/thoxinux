"""Tests for the ThoxOS userspace `thox` command (rootfs/overlay/usr/local/bin/thox)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[1]
THOX_PATH = ROOT / "rootfs" / "overlay" / "usr" / "local" / "bin" / "thox"


def load_thox():
    loader = importlib.machinery.SourceFileLoader("thox_cli", str(THOX_PATH))
    spec = importlib.util.spec_from_loader("thox_cli", loader)
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolves annotations through sys.modules, so register first.
    sys.modules["thox_cli"] = module
    loader.exec_module(module)
    return module


thox = load_thox()


@pytest.fixture()
def ai_env(tmp_path: Path) -> Path:
    path = tmp_path / "ai.env"
    path.write_text(
        '# endpoint\nTHOX_AI_BASE_URL="http://127.0.0.1:9/v1"\nTHOX_AI_MODEL=qwen-test\n'
        "THOX_AI_TIMEOUT=5\n"
    )
    return path


class Recorder(BaseHTTPRequestHandler):
    """Mock OpenAI-compatible endpoint. Behaviour is chosen per test."""

    reply_status = 200
    reply_body = b""
    seen: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length))
        Recorder.seen.append(
            {"path": self.path, "auth": self.headers.get("Authorization"), "body": body}
        )
        self.send_response(Recorder.reply_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(Recorder.reply_body)))
        self.end_headers()
        self.wfile.write(Recorder.reply_body)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture()
def endpoint() -> Iterator[str]:
    Recorder.seen = []
    server = HTTPServer(("127.0.0.1", 0), Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()


class TestConfig:
    def test_file_values_load(self, ai_env: Path) -> None:
        cfg = thox.load_ai_config({}, str(ai_env))
        assert cfg.base_url == "http://127.0.0.1:9/v1"
        assert cfg.model == "qwen-test"
        assert cfg.timeout == 5.0
        assert cfg.api_key is None

    def test_environment_overrides_file(self, ai_env: Path) -> None:
        cfg = thox.load_ai_config({"THOX_AI_MODEL": "other", "HOME": "/x"}, str(ai_env))
        assert cfg.model == "other"

    @pytest.mark.parametrize(
        ("env", "message"),
        [
            ({"THOX_AI_BASE_URL": ""}, "not set"),
            ({"THOX_AI_BASE_URL": "ftp://host/v1"}, "http"),
            ({"THOX_AI_BASE_URL": "http://host/v1?x=1"}, "query"),
            ({"THOX_AI_MODEL": ""}, "MODEL"),
            ({"THOX_AI_TIMEOUT": "soon"}, "number"),
            ({"THOX_AI_TIMEOUT": "0"}, "between"),
        ],
    )
    def test_validation(self, ai_env: Path, env: dict, message: str) -> None:
        with pytest.raises(thox.ThoxError, match=message):
            thox.load_ai_config(env, str(ai_env))

    def test_api_key_file_must_be_private(self, tmp_path: Path) -> None:
        path = tmp_path / "ai.env"
        path.write_text("THOX_AI_BASE_URL=http://h/v1\nTHOX_AI_MODEL=m\nTHOX_AI_API_KEY=secret\n")
        os.chmod(path, 0o644)
        with pytest.raises(thox.ThoxError, match="chmod 600"):
            thox.load_ai_config({}, str(path))
        os.chmod(path, 0o600)
        assert thox.load_ai_config({}, str(path)).api_key == "secret"

    def test_malformed_line_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "ai.env"
        path.write_text("this is not an assignment\n")
        with pytest.raises(thox.ThoxError, match="KEY=VALUE"):
            thox.read_key_value_file(str(path))

    def test_shipped_ai_env_parses(self) -> None:
        values = thox.read_key_value_file(str(ROOT / "rootfs/overlay/etc/thoxos/ai.env"))
        assert values["THOX_AI_BASE_URL"] == "http://10.0.2.2:11434/v1"
        assert "THOX_AI_MODEL" not in values  # no model ships in the image


class TestResponses:
    def test_parse_success(self) -> None:
        body = json.dumps({"choices": [{"message": {"content": " hi \n"}}]}).encode()
        assert thox.parse_chat_response(body) == "hi"

    @pytest.mark.parametrize(
        ("body", "message"),
        [
            (b"<html>", "not JSON"),
            (b"[]", "unexpected"),
            (json.dumps({"error": {"message": "model not found"}}).encode(), "model not found"),
            (json.dumps({"choices": []}).encode(), "no choices"),
            (json.dumps({"choices": [{"message": {}}]}).encode(), "no message content"),
        ],
    )
    def test_parse_failures(self, body: bytes, message: str) -> None:
        with pytest.raises(thox.ThoxError, match=message):
            thox.parse_chat_response(body)


class TestAsk:
    def test_round_trip(self, endpoint: str) -> None:
        Recorder.reply_status = 200
        Recorder.reply_body = json.dumps(
            {"choices": [{"message": {"content": "ThoxOS runs on Ginux."}}]}
        ).encode()
        cfg = thox.AIConfig(base_url=endpoint, model="m1", api_key="k", timeout=5)
        assert thox.ask(cfg, "  what kernel?  ") == "ThoxOS runs on Ginux."
        request = Recorder.seen[0]
        assert request["path"] == "/v1/chat/completions"
        assert request["auth"] == "Bearer k"
        assert request["body"]["model"] == "m1"
        assert request["body"]["stream"] is False
        assert request["body"]["messages"][-1] == {"role": "user", "content": "what kernel?"}

    def test_http_error_is_reported(self, endpoint: str) -> None:
        Recorder.reply_status = 500
        Recorder.reply_body = b'{"error":"boom"}'
        cfg = thox.AIConfig(base_url=endpoint, model="m1", api_key=None, timeout=5)
        with pytest.raises(thox.ThoxError, match="HTTP 500"):
            thox.ask(cfg, "hello")

    def test_unreachable_endpoint(self) -> None:
        cfg = thox.AIConfig(base_url="http://127.0.0.1:9/v1", model="m", api_key=None, timeout=2)
        with pytest.raises(thox.ThoxError, match="cannot reach"):
            thox.ask(cfg, "hello")

    def test_prompt_limits(self) -> None:
        cfg = thox.AIConfig(base_url="http://127.0.0.1:9/v1", model="m", api_key=None, timeout=2)
        with pytest.raises(thox.ThoxError, match="empty"):
            thox.ask(cfg, "   ")
        with pytest.raises(thox.ThoxError, match="exceeds"):
            thox.ask(cfg, "x" * (thox.MAX_PROMPT_CHARS + 1))


class TestMain:
    def test_ask_end_to_end(self, endpoint: str, capsys: pytest.CaptureFixture[str]) -> None:
        Recorder.reply_status = 200
        Recorder.reply_body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
        env = {"THOX_AI_BASE_URL": endpoint, "THOX_AI_MODEL": "m"}
        assert thox.main(["ask", "--model", "override", "ping"], env=env) == 0
        assert capsys.readouterr().out.strip() == "ok"
        assert Recorder.seen[0]["body"]["model"] == "override"

    def test_missing_model_exit_code(self, capsys: pytest.CaptureFixture[str]) -> None:
        env = {"THOX_AI_BASE_URL": "http://127.0.0.1:9/v1", "THOX_AI_MODEL": ""}
        assert thox.main(["ask", "hi"], env=env) == 2
        assert "THOX_AI_MODEL" in capsys.readouterr().err

    def test_status_never_fails_on_ai_config(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert thox.main(["status"], env={"THOX_AI_BASE_URL": "nope"}) == 0
        output = capsys.readouterr().out
        assert "kernel" in output and "ai        not configured" in output
