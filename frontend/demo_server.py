from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class DemoHandler(SimpleHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/api/snapshot":
            payload = (ROOT / "demo_snapshot.json").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/scenario":
            payload = (ROOT / "demo_scenario.json").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/api/inspection-image":
            image = ROOT.parent.parent.parent / "dataset" / "sheet_metal" / "sheet_metal" / "test_private" / "000_regular.png"
            payload = image.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def do_POST(self):  # noqa: N802
        self.send_error(405, "Read-only demo server")

    def do_PUT(self):  # noqa: N802
        self.send_error(405, "Read-only demo server")

    def do_DELETE(self):  # noqa: N802
        self.send_error(405, "Read-only demo server")


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 4173), DemoHandler)
    print("FactoryOps demo server: http://127.0.0.1:4173/dashboard.html")
    server.serve_forever()
