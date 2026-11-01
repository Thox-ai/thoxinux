"""Tests for the hosted-routing relay (runtime/thox_ai_relay.py)."""

from __future__ import annotations

import io
import json
import shutil
import ssl
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))

import thox_ai_relay as relay  # noqa: E402

BASE = {
    "THOX_RELAY_UPSTREAM": "https://example.openai.azure.com/openai/v1/",
    "THOX_RELAY_AUTH": "api-key",
    "THOX_RELAY_API_KEY": "secret-key",
    "THOX_RELAY_MODEL": "gpt-test",
    "THOX_RELAY_LISTEN": "127.0.0.1:0",
}


def config(**overrides):
    values = dict(BASE)
    values.update(overrides)
    return relay.load_config(values)


def test_config_normalizes_upstream():
    cfg = config()
    assert cfg.upstream == "https://example.openai.azure.com/openai/v1"
    assert cfg.port == 0 and cfg.host == "127.0.0.1"


@pytest.mark.parametrize("key,value,match", [
    ("THOX_RELAY_UPSTREAM", "http://plain.example/v1", "https"),
    ("THOX_RELAY_UPSTREAM", "https://user:secret@example.test/v1", "credentials"),
    ("THOX_RELAY_UPSTREAM", "https://example.test/v1?key=secret", "query"),
    ("THOX_RELAY_UPSTREAM", "https://example.test/v1#secret", "fragment"),
    ("THOX_RELAY_AUTH", "basic", "THOX_RELAY_AUTH"),
    ("THOX_RELAY_API_KEY", "", "API_KEY"),
    ("THOX_RELAY_MODEL", "", "MODEL"),
    ("THOX_RELAY_LISTEN", "0.0.0.0:11434", "loopback"),
    ("THOX_RELAY_LISTEN", "nonsense", "HOST:PORT"),
    ("THOX_RELAY_RATE_PER_MIN", "0", "RATE"),
])
def test_config_rejects(key, value, match):
    with pytest.raises(relay.RelayError, match=match):
        config(**{key: value})


def test_env_file_parsing(tmp_path):
    f = tmp_path / "ai-relay.env"
    f.write_text('# comment\nTHOX_RELAY_MODEL="m"\n\nTHOX_RELAY_AUTH=bearer\n')
    assert relay.read_env_file(str(f)) == {"THOX_RELAY_MODEL": "m", "THOX_RELAY_AUTH": "bearer"}
    f.write_text("not an assignment\n")
    with pytest.raises(relay.RelayError, match="KEY=VALUE"):
        relay.read_env_file(str(f))


def test_rewrite_substitutes_hosted_alias_and_blocks_streaming():
    cfg = config()
    body = json.dumps({"model": "thox-hosted", "messages": [{"role": "user", "content": "hi"}]}).encode()
    assert json.loads(relay.rewrite_request(body, cfg))["model"] == "gpt-test"
    explicit = json.dumps({"model": "other", "messages": []}).encode()
    assert json.loads(relay.rewrite_request(explicit, cfg))["model"] == "other"
    with pytest.raises(ValueError, match="streaming"):
        relay.rewrite_request(json.dumps({"messages": [], "stream": True}).encode(), cfg)
    with pytest.raises(ValueError, match="messages"):
        relay.rewrite_request(b'{"model": "x"}', cfg)


def test_auth_headers_per_scheme():
    assert relay.auth_headers(config(THOX_RELAY_AUTH="api-key")) == {"api-key": "secret-key"}
    assert relay.auth_headers(config(THOX_RELAY_AUTH="bearer")) == {"Authorization": "Bearer secret-key"}
    assert relay.auth_headers(config(THOX_RELAY_AUTH="x-api-key")) == {"x-api-key": "secret-key"}


def test_token_bucket_limits_then_refills():
    now = [0.0]
    bucket = relay.TokenBucket(2, clock=lambda: now[0])
    assert bucket.take() and bucket.take()
    assert not bucket.take()
    now[0] += 30.0  # half a minute refills one token at 2/min
    assert bucket.take()


class FakeResponse(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def running():
    """A relay on an ephemeral port whose upstream calls are captured, not sent."""
    seen = []

    def opener(request, timeout):
        seen.append(request)
        if request.full_url.endswith("/chat/completions"):
            payload = json.loads(request.data)
            if payload["model"] == "fail":
                raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {},
                                             io.BytesIO(b'{"error": {"message": "bad key"}}'))
            reply = {"choices": [{"message": {"role": "assistant", "content": f"echo:{payload['model']}"}}]}
            return FakeResponse(json.dumps(reply).encode())
        raise AssertionError("unexpected upstream call")

    cfg = config(THOX_RELAY_RATE_PER_MIN="3")
    server = relay.serve(cfg, opener=opener)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}", seen
    server.shutdown()
    server.server_close()


def post(url, payload):
    req = urllib.request.Request(url + "/v1/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def test_relay_forwards_with_credential_and_model(running):
    url, seen = running
    status, body = post(url, {"model": "thox-hosted", "messages": [{"role": "user", "content": "hi"}]})
    assert status == 200
    assert body["choices"][0]["message"]["content"] == "echo:gpt-test"
    sent = seen[-1]
    assert sent.full_url == "https://example.openai.azure.com/openai/v1/chat/completions"
    assert sent.get_header("Api-key") == "secret-key"


def test_relay_maps_upstream_errors(running):
    url, _ = running
    status, body = post(url, {"model": "fail", "messages": []})
    assert status == 401
    assert "bad key" in body["error"]["message"]


def test_relay_models_and_health(running):
    url, _ = running
    with urllib.request.urlopen(url + "/v1/models", timeout=5) as resp:
        ids = [m["id"] for m in json.loads(resp.read())["data"]]
    assert ids == ["thox-hosted", "gpt-test"]
    with urllib.request.urlopen(url + "/healthz", timeout=5) as resp:
        assert json.loads(resp.read())["status"] == "ok"


def test_relay_rate_limit(running):
    url, _ = running
    codes = [post(url, {"messages": []})[0] for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429


def test_relay_rejects_bad_bodies(running):
    url, _ = running
    req = urllib.request.Request(url + "/v1/chat/completions", data=b"not json", method="POST")
    with pytest.raises(urllib.error.HTTPError) as info:
        urllib.request.urlopen(req, timeout=5)
    assert info.value.code == 400


@pytest.fixture
def tls_certificate(tmp_path):
    """Temporary local test identity; no provider key or external service is used."""
    if shutil.which("openssl") is None:
        pytest.skip("local HTTPS redirect regression needs openssl")
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        "-keyout", str(key), "-out", str(cert),
    ], check=True, capture_output=True)
    return cert, key


@pytest.mark.parametrize("auth", relay.AUTH_SCHEMES)
def test_real_https_redirect_never_reaches_credential_sink(tls_certificate, monkeypatch, auth):
    """Exercise urllib's real redirect handling, including POST-to-GET redirects."""
    cert, key = tls_certificate
    sink_seen, upstream_seen = [], []
    redirect_code = [302]

    class Sink(BaseHTTPRequestHandler):
        def do_GET(self):
            sink_seen.append(dict(self.headers))
            self.send_response(200)
            self.end_headers()

        do_POST = do_GET

        def log_message(self, *args):
            pass

    sink = ThreadingHTTPServer(("127.0.0.1", 0), Sink)

    class Redirect(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            upstream_seen.append(dict(self.headers))
            if redirect_code[0] == 200:
                data = b'{"choices":[{"message":{"content":"local TLS success"}}]}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(redirect_code[0])
            self.send_header("Location", f"https://127.0.0.1:{sink.server_port}/credential-sink")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *args):
            pass

    upstream = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(cert), str(key))
    for server in (upstream, sink):
        server.socket = context.wrap_socket(server.socket, server_side=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()

    create_context = ssl.create_default_context
    monkeypatch.setattr(relay.ssl, "create_default_context", lambda: create_context(cafile=str(cert)))
    cfg = config(THOX_RELAY_UPSTREAM=f"https://127.0.0.1:{upstream.server_port}/v1",
                 THOX_RELAY_AUTH=auth)
    server = relay.serve(cfg)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for code in (301, 302, 303, 307, 308):
            redirect_code[0] = code
            status, body = post(f"http://127.0.0.1:{server.server_port}", {"messages": []})
            assert status == 502
            assert "redirect refused" in body["error"]["message"]
            assert cfg.api_key not in json.dumps(body)
        redirect_code[0] = 200
        status, body = post(f"http://127.0.0.1:{server.server_port}", {"messages": []})
        assert status == 200
        assert body["choices"][0]["message"]["content"] == "local TLS success"
        assert len(upstream_seen) == 6
        assert all(any(cfg.api_key in v for v in headers.values()) for headers in upstream_seen)
        assert sink_seen == []
    finally:
        for running_server in (server, upstream, sink):
            running_server.shutdown()
            running_server.server_close()
