#!/usr/bin/env python3
# Copyright (c) 2026 THOX.ai LLC. Licensed under the Apache License, Version 2.0.
"""thox-ai-relay: loopback OpenAI-compatible relay for hosted THOX AI routing.

On a ThoxOS Ginux Edition host without a local model (an Azure VM, for
example), `thox ask` on the host and inside ThoxOS on Ginux (10.0.2.2 is the
host loopback) still reaches 127.0.0.1:11434. This relay listens there and
forwards chat completions to a hosted OpenAI-compatible endpoint the operator
configures (Azure OpenAI v1, Anthropic's OpenAI SDK compatibility endpoint,
or any /v1/chat/completions server), adding the credential so no guest or user
ever holds it.

Configuration: /etc/thoxos/ai-relay.env (mode 0640, root:thoxos-ai)

    THOX_RELAY_UPSTREAM=https://example.openai.azure.com/openai/v1
    THOX_RELAY_AUTH=api-key          # api-key | bearer | x-api-key
    THOX_RELAY_API_KEY=...
    THOX_RELAY_MODEL=gpt-4.1-mini    # used for model "thox-hosted" or an empty model
    THOX_RELAY_LISTEN=127.0.0.1:11434
    THOX_RELAY_RATE_PER_MIN=30
    THOX_RELAY_TIMEOUT=120

Routes: POST /v1/chat/completions (non-streaming), GET /v1/models, GET /healthz.
Bodies and keys are never logged. The relay refuses to listen off loopback
and refuses upstream redirects; configure the final HTTPS endpoint directly.
Only the Python standard library is used.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Mapping, Optional, Sequence

CONFIG_FILE = "/etc/thoxos/ai-relay.env"
HOSTED_ALIAS = "thox-hosted"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
AUTH_SCHEMES = ("api-key", "bearer", "x-api-key")


class RelayError(Exception):
    """Configuration error reported at startup."""


@dataclass(frozen=True)
class RelayConfig:
    upstream: str
    auth: str
    api_key: str
    model: str
    host: str
    port: int
    rate_per_min: int
    timeout: float


def read_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with open(path, encoding="utf-8") as handle:
            lines = handle.readlines()
    except FileNotFoundError as error:
        raise RelayError(f"{path} not found; the relay is configured there") from error
    except OSError as error:
        raise RelayError(f"cannot read {path}: {error.strerror}") from error
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep or not key.strip().replace("_", "").isalnum():
            raise RelayError(f"{path}:{number}: expected KEY=VALUE")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_config(values: Mapping[str, str]) -> RelayConfig:
    upstream = values.get("THOX_RELAY_UPSTREAM", "").strip().rstrip("/")
    parsed = urllib.parse.urlparse(upstream)
    if parsed.scheme != "https" or not parsed.hostname:
        raise RelayError("THOX_RELAY_UPSTREAM must be an https:// URL ending before /chat/completions")
    if parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise RelayError("THOX_RELAY_UPSTREAM must not contain credentials, a query or a fragment")
    auth = values.get("THOX_RELAY_AUTH", "bearer").strip().lower()
    if auth not in AUTH_SCHEMES:
        raise RelayError(f"THOX_RELAY_AUTH must be one of {', '.join(AUTH_SCHEMES)}")
    api_key = values.get("THOX_RELAY_API_KEY", "").strip()
    if not api_key or any(ch in api_key for ch in "\r\n"):
        raise RelayError("THOX_RELAY_API_KEY is empty or malformed")
    model = values.get("THOX_RELAY_MODEL", "").strip()
    if not model:
        raise RelayError("THOX_RELAY_MODEL is required (the upstream model or deployment name)")
    listen = values.get("THOX_RELAY_LISTEN", "127.0.0.1:11434").strip()
    host, _, port_text = listen.rpartition(":")
    host = host.strip("[]")
    try:
        if not ipaddress.ip_address(host).is_loopback:
            raise RelayError(f"THOX_RELAY_LISTEN={listen} is not a loopback address")
        port = int(port_text)
    except ValueError as error:
        raise RelayError(f"THOX_RELAY_LISTEN={listen} is not HOST:PORT") from error
    if not 0 <= port <= 65535:  # 0 picks a free port (tests)
        raise RelayError("THOX_RELAY_LISTEN port out of range")
    try:
        rate = int(values.get("THOX_RELAY_RATE_PER_MIN", "30"))
        timeout = float(values.get("THOX_RELAY_TIMEOUT", "120"))
    except ValueError as error:
        raise RelayError("THOX_RELAY_RATE_PER_MIN and THOX_RELAY_TIMEOUT must be numbers") from error
    if not 1 <= rate <= 6000 or not 1 <= timeout <= 3600:
        raise RelayError("THOX_RELAY_RATE_PER_MIN must be 1-6000 and THOX_RELAY_TIMEOUT 1-3600")
    return RelayConfig(upstream, auth, api_key, model, host, port, rate, timeout)


class TokenBucket:
    """Requests per minute shared by every caller of this relay."""

    def __init__(self, per_minute: int, clock=time.monotonic) -> None:
        self.capacity = float(per_minute)
        self.tokens = float(per_minute)
        self.rate = per_minute / 60.0
        self.clock = clock
        self.updated = clock()
        self.lock = threading.Lock()

    def take(self) -> bool:
        with self.lock:
            now = self.clock()
            self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
            self.updated = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


def auth_headers(config: RelayConfig) -> dict[str, str]:
    if config.auth == "api-key":
        return {"api-key": config.api_key}
    if config.auth == "x-api-key":
        return {"x-api-key": config.api_key}
    return {"Authorization": f"Bearer {config.api_key}"}


def rewrite_request(body: bytes, config: RelayConfig) -> bytes:
    """Validate a chat request and substitute the hosted model where asked."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"request body is not JSON: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("messages"), list):
        raise ValueError("request must be a JSON object with a messages list")
    if payload.get("stream"):
        raise ValueError("streaming is not supported by the relay; send stream=false")
    model = str(payload.get("model") or "").strip()
    if not model or model == HOSTED_ALIAS:
        payload["model"] = config.model
    payload["stream"] = False
    return json.dumps(payload).encode("utf-8")


class RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Never forward a credential-bearing request to a redirected endpoint."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_handler(config: RelayConfig, bucket: TokenBucket, opener=None):
    context = ssl.create_default_context()
    upstream_opener = urllib.request.build_opener(
        RefuseRedirects(), urllib.request.HTTPSHandler(context=context))
    open_url = opener or (lambda req, timeout: upstream_opener.open(req, timeout=timeout))

    class Handler(BaseHTTPRequestHandler):
        server_version = "thox-ai-relay/0.2.0"
        sys_version = ""

        def log_message(self, fmt: str, *args) -> None:  # no bodies, no headers
            sys.stderr.write("thox-ai-relay: %s %s\n" % (self.address_string(), fmt % args))

        def send_json(self, status: int, payload: dict) -> None:
            data = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def error(self, status: int, message: str) -> None:
            self.send_json(status, {"error": {"message": message, "type": "thox_relay_error"}})

        def do_GET(self) -> None:  # noqa: N802 - http.server naming
            path = self.path.split("?", 1)[0]
            if path == "/healthz":
                self.send_json(200, {"status": "ok", "route": "hosted", "upstream_host":
                                     urllib.parse.urlparse(config.upstream).netloc})
            elif path in ("/v1/models", "/models"):
                self.send_json(200, {"object": "list", "data": [
                    {"id": HOSTED_ALIAS, "object": "model", "owned_by": "thox-relay"},
                    {"id": config.model, "object": "model", "owned_by": "upstream"},
                ]})
            else:
                self.error(404, "not found")

        def do_POST(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path not in ("/v1/chat/completions", "/chat/completions"):
                self.error(404, "not found")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.error(400, "invalid Content-Length")
                return
            if length <= 0 or length > MAX_REQUEST_BYTES:
                self.error(413 if length > MAX_REQUEST_BYTES else 400, "request body missing or too large")
                return
            if not bucket.take():
                self.error(429, "relay rate limit reached; try again shortly")
                return
            try:
                body = rewrite_request(self.rfile.read(length), config)
            except ValueError as error:
                self.error(400, str(error))
                return
            headers = {"Content-Type": "application/json", "Accept": "application/json",
                       "User-Agent": "thox-ai-relay/0.2.0", **auth_headers(config)}
            request = urllib.request.Request(config.upstream + "/chat/completions", data=body,
                                             headers=headers, method="POST")
            try:
                with open_url(request, config.timeout) as response:
                    data = response.read(MAX_RESPONSE_BYTES + 1)
                    status = response.status
            except urllib.error.HTTPError as error:
                if 300 <= error.code < 400:
                    error.close()
                    self.error(502, "upstream redirect refused; configure the final HTTPS endpoint")
                    return
                detail = error.read(4096).decode("utf-8", "replace")
                message = detail
                try:
                    message = json.loads(detail).get("error", {}).get("message", detail)
                except (json.JSONDecodeError, AttributeError):
                    pass
                self.error(error.code if 400 <= error.code < 600 else 502, f"upstream: {message}"[:600])
                return
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                self.error(502, f"upstream unreachable: {getattr(error, 'reason', error)}")
                return
            if len(data) > MAX_RESPONSE_BYTES:
                self.error(502, "upstream response too large")
                return
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def serve(config: RelayConfig, opener=None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((config.host, config.port), make_handler(config, TokenBucket(config.rate_per_min), opener))
    server.daemon_threads = True
    return server


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Loopback relay for hosted THOX AI routing")
    parser.add_argument("--config", default=CONFIG_FILE)
    parser.add_argument("--check", action="store_true", help="validate the configuration and exit")
    args = parser.parse_args(argv)
    try:
        config = load_config(read_env_file(args.config))
    except RelayError as error:
        print(f"thox-ai-relay: {error}", file=sys.stderr)
        return 2
    if args.check:
        print(f"thox-ai-relay: configuration ok ({config.auth} auth, model {config.model}, "
              f"listen {config.host}:{config.port})")
        return 0
    try:
        server = serve(config)
    except OSError as error:
        print(f"thox-ai-relay: cannot listen on {config.host}:{config.port}: {error.strerror}", file=sys.stderr)
        return 1
    print(f"thox-ai-relay: listening on {config.host}:{config.port}, forwarding to "
          f"{urllib.parse.urlparse(config.upstream).netloc}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
