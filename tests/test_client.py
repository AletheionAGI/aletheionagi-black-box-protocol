from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from aletheion_black_box.client import ApiClient, error_code


class Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        body = json.loads(self.rfile.read(length))
        if body.get("fail"):
            payload = {"error": {"code": "idempotency_replay_unavailable"}}
            self.send_response(409)
        else:
            payload = {
                "ok": True,
                "authorization_received": bool(self.headers.get("authorization")),
            }
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Correlation-ID", "correlation:server")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def log_message(self, format: str, *args: object) -> None:
        del format, args


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_captures_json_and_correlation_without_headers(self) -> None:
        client = ApiClient(f"http://127.0.0.1:{self.server.server_port}", 2)
        result = client.request("POST", "/test", api_key="private-key", body={"value": 1})
        self.assertEqual(result.status, 200)
        self.assertEqual(result.correlation_id, "correlation:server")
        self.assertEqual(result.request_body, {"value": 1})
        self.assertFalse(hasattr(result, "headers"))

    def test_returns_structured_http_errors(self) -> None:
        client = ApiClient(f"http://127.0.0.1:{self.server.server_port}", 2)
        result = client.request("POST", "/test", api_key="private-key", body={"fail": True})
        self.assertEqual(result.status, 409)
        self.assertEqual(error_code(result), "idempotency_replay_unavailable")


if __name__ == "__main__":
    unittest.main()
