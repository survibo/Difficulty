"""
python scripts/test_server.py

간단한 HTML UI로 문장 난도 측정을 테스트할 수 있는 HTTP 서버.
루트의 index.html을 서빙한다.
"""

from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.pipeline import SentenceScorer

INDEX_HTML = ROOT / "index.html"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            data = INDEX_HTML.read_bytes()
            self._ok("text/html; charset=utf-8", data)
        else:
            self._err(404, "Not Found")

    def do_POST(self) -> None:
        if self.path == "/api/score":
            self._handle_score()
        else:
            self._err(404, "Not Found")

    def _handle_score(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            sentence = data.get("sentence", "")
            result = SCORER.score(sentence)
            self._ok("application/json", json.dumps(result, ensure_ascii=False, default=str).encode("utf-8"))
        except Exception as e:
            self._err(500, str(e))

    def _ok(self, content_type: str, data: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _err(self, code: int, msg: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write(f"[{self.date_time_string()}] {args[0]} {args[1]} {args[2]}\n")


def main() -> None:
    global SCORER
    print("Loading pipeline...", end=" ", flush=True)
    SCORER = SentenceScorer()
    print("OK")

    port = int(os.environ.get("PORT", "8800"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server: http://0.0.0.0:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    SCORER: SentenceScorer = None  # type: ignore[assignment]
    main()
