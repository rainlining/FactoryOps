from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest
from factoryops_agent_service.approved_action_resume import (
    BusinessActionHttpClient,
    BusinessActionUnavailable,
)
from jsonschema import Draft202012Validator, FormatChecker


class Handler(BaseHTTPRequestHandler):
    mode = "success"
    observed: ClassVar[dict[str, object]] = {}

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        type(self).observed = {
            "path": self.path,
            "token": self.headers.get("X-FactoryOps-Service-Token"),
            "content_type": self.headers.get("Content-Type"),
            "body": self.rfile.read(length),
        }
        if type(self).mode == "timeout":
            time.sleep(0.2)
            return
        if type(self).mode == "error":
            self.send_response(409)
            self.end_headers()
            return
        if type(self).mode == "redirect":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:1/token-leak")
            self.end_headers()
            return
        body = (
            b"not-json"
            if type(self).mode == "malformed"
            else json.dumps(
                {
                    "approval_key": "APK-TEST",
                    "action": "HOLD_BATCH",
                    "incident_id": "QI-TEST",
                    "batch_id": "BATCH-1",
                    "status": "EXECUTED",
                    "executed_at": "2026-08-21T02:00:00Z",
                    "replayed": False,
                }
            ).encode()
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def log_message(self, format, *args):
        pass


@pytest.fixture
def server():
    Handler.mode = "success"
    Handler.observed = {}
    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}"
    finally:
        instance.shutdown()
        thread.join()
        instance.server_close()


def test_http_client_sends_only_key_token_and_empty_body(server: str):
    receipt = BusinessActionHttpClient(server, "secret").execute("APK-TEST")
    schema = json.loads(
        (
            Path(__file__).parents[3]
            / "contracts/approved_action_receipt/v1.0.0/schema.json"
        ).read_text()
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(receipt)
    assert receipt["status"] == "EXECUTED"
    assert Handler.observed == {
        "path": "/internal/api/v1/approvals/APK-TEST/execute",
        "token": "secret",
        "content_type": "application/json",
        "body": b"{}",
    }


@pytest.mark.parametrize("mode", ["error", "malformed", "timeout", "redirect"])
def test_http_client_classifies_failures_without_retry(server: str, mode: str):
    Handler.mode = mode
    client = BusinessActionHttpClient(
        server, "secret", timeout_seconds=0.05 if mode == "timeout" else 1
    )
    with pytest.raises(BusinessActionUnavailable):
        client.execute("APK-TEST")
    assert Handler.observed["path"].endswith("/APK-TEST/execute")


@pytest.mark.parametrize("timeout", [0, -1, 31])
def test_http_client_rejects_unsafe_timeout(timeout: float):
    with pytest.raises(ValueError, match="timeout"):
        BusinessActionHttpClient("http://127.0.0.1", "secret", timeout_seconds=timeout)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://factoryops.internal",
        "http://user@factoryops.internal",
        "http://factoryops.internal/path",
        "http://factoryops.internal?query=1",
        "http://factoryops.internal#fragment",
    ],
)
def test_http_client_requires_a_bare_trusted_http_origin(url: str):
    with pytest.raises(ValueError, match="origin"):
        BusinessActionHttpClient(url, "secret")
