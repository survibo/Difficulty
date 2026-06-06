"""
python scripts/test_server.py

간단한 HTML UI로 문장 난도 측정을 테스트할 수 있는 HTTP 서버.
루트의 index.html을 서빙한다.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

try:
    from sentdiff.lexical import LexiconEntry, LexiconScorer
    from sentdiff.paragraph import ParagraphScorer
    from sentdiff.pipeline import SentenceScorer
except Exception:
    print("IMPORT ERROR", flush=True)
    traceback.print_exc()
    sys.exit(1)

INDEX_HTML = ROOT / "index.html"

SCORER: SentenceScorer | None = None
PARAGRAPH_SCORER: ParagraphScorer | None = None


def _get_scorer() -> SentenceScorer:
    global SCORER
    if SCORER is None:
        print("Loading pipeline...", end=" ", flush=True)
        SCORER = SentenceScorer()
        print("OK", flush=True)
    return SCORER


def _get_paragraph_scorer() -> ParagraphScorer:
    global PARAGRAPH_SCORER
    if PARAGRAPH_SCORER is None:
        PARAGRAPH_SCORER = ParagraphScorer(_get_scorer())
    return PARAGRAPH_SCORER


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            data = INDEX_HTML.read_bytes()
            self._ok("text/html; charset=utf-8", data)
        else:
            self._err(404, "Not Found")

    def do_POST(self) -> None:
        if self.path == "/api/score":
            self._handle_score()
        elif self.path == "/api/score-paragraph":
            self._handle_score_paragraph()
        else:
            self._err(404, "Not Found")

    def _score_with_custom_words(self, custom_words: dict, score_fn: Any) -> dict:
        scorer = _get_scorer()
        ls = scorer._lexical_scorer

        saved_exact: dict[tuple[str, str], list[LexiconEntry]] = {}
        saved_lemma: dict[str, list[LexiconEntry]] = {}
        for lemma, difficulty in custom_words.items():
            entry = LexiconEntry(entry_id=-1, lemma=lemma, pos="NNG", difficulty=float(difficulty))

            # Save and remove ALL exact-map entries for this lemma
            # (exact match by (lemma, pos) takes priority over lemma-only fallback,
            #  so we must clear all POS variants to let the override take effect.)
            exact_keys = [k for k in ls._exact_map if k[0] == lemma]
            for k in exact_keys:
                saved_exact[k] = ls._exact_map.pop(k)

            # Add override entry for generic NNG key — covers any POS lookup
            ls._exact_map[(lemma, "NNG")] = [entry]

            # Save and override lemma_map
            if lemma in ls._lemma_map:
                saved_lemma[lemma] = ls._lemma_map[lemma]
            ls._lemma_map[lemma] = [entry]

        try:
            return score_fn()
        finally:
            for lemma in custom_words:
                # Remove all override exact entries for this lemma
                override_keys = [k for k in ls._exact_map if k[0] == lemma]
                for k in override_keys:
                    ls._exact_map.pop(k, None)

                # Restore saved exact entries for this lemma
                for k, v in saved_exact.items():
                    if k[0] == lemma:
                        ls._exact_map[k] = v

                # Restore lemma_map
                if lemma in saved_lemma:
                    ls._lemma_map[lemma] = saved_lemma[lemma]
                else:
                    ls._lemma_map.pop(lemma, None)

    def _handle_score(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            sentence = data.get("sentence", "")
            custom_words = data.get("custom_words", {})

            result = self._score_with_custom_words(
                custom_words,
                lambda: _get_scorer().score(sentence),
            )

            self._ok("application/json", json.dumps(result, ensure_ascii=False, default=str).encode("utf-8"))
        except Exception as e:
            self._err(500, str(e))

    def _handle_score_paragraph(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            paragraph = data.get("paragraph", "")
            custom_words = data.get("custom_words", {})

            result = self._score_with_custom_words(
                custom_words,
                lambda: _get_paragraph_scorer().score(paragraph),
            )

            self._ok("application/json", json.dumps(result, ensure_ascii=False, default=str).encode("utf-8"))
        except ValueError as e:
            self._err(400, str(e))
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
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        try:
            msg = fmt % args
        except Exception:
            msg = f"{fmt} | args={args!r}"
        sys.stderr.write(f"[{self.date_time_string()}] {msg}\n")


def main() -> None:
    port = int(os.environ.get("PORT", "8800"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"Server ready on port {port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
