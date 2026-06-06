"""
MCP server: 한국어 문장 난이도 측정 도구

사용법:
  python scripts/mcp_server.py

Claude Desktop 설정 (claude_desktop_config.json):
  {
    "mcpServers": {
      "korean-difficulty": {
        "command": "python",
        "args": ["scripts/mcp_server.py"],
        "env": {
          "API_URL": "https://difficulty-production.up.railway.app"
        }
      }
    }
  }

환경변수:
  API_URL: Railway 배포 URL (기본값: https://difficulty-production.up.railway.app)
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Any

API_URL = os.environ.get("API_URL", "https://difficulty-production.up.railway.app")


def call_score_api(sentence: str) -> dict[str, Any]:
    payload = json.dumps({"sentence": sentence, "custom_words": {}}).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/score",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_score_paragraph_api(paragraph: str) -> dict[str, Any]:
    payload = json.dumps({"paragraph": paragraph, "custom_words": {}}).encode("utf-8")
    req = urllib.request.Request(
        f"{API_URL}/api/score-paragraph",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Minimal MCP stdio server (JSON-RPC 2.0)
# ---------------------------------------------------------------------------

def send_message(msg: dict[str, Any]) -> None:
    line = json.dumps(msg, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def handle_request(msg: dict[str, Any]) -> None:
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {}) or {}

    if method == "initialize":
        send_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "korean-difficulty", "version": "1.0.0"},
                "capabilities": {"tools": {}},
            },
        })

    elif method == "notifications/initialized":
        pass

    elif method == "tools/list":
        send_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": [
                    {
                        "name": "score_sentence",
                        "description": "한국어 문장의 난이도를 측정합니다. "
                                       "어휘, 구조, 부정 보너스 점수를 반환합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "sentence": {
                                    "type": "string",
                                    "description": "난이도를 측정할 한국어 문장",
                                }
                            },
                            "required": ["sentence"],
                        },
                    },
                    {
                        "name": "score_paragraph",
                        "description": "한국어 문단(4문장 이상)의 난이도를 측정합니다. "
                                       "문장 종합 + 정보 밀도 + 개념 반복도를 반환합니다.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "paragraph": {
                                    "type": "string",
                                    "description": "난이도를 측정할 한국어 문단 (최소 4문장)",
                                }
                            },
                            "required": ["paragraph"],
                        },
                    },
                ]
            },
        })

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {}) or {}

        try:
            if tool_name == "score_sentence":
                sentence = arguments.get("sentence", "")
                if not sentence:
                    raise ValueError("sentence is required")
                data = call_score_api(sentence)
                result_text = _format_score(data)
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                    },
                })

            elif tool_name == "score_paragraph":
                paragraph = arguments.get("paragraph", "")
                if not paragraph:
                    raise ValueError("paragraph is required")
                data = call_score_paragraph_api(paragraph)
                result_text = _format_paragraph_score(data)
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                    },
                })

            else:
                send_message({
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"},
                })

        except Exception as e:
            send_message({
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(e)},
            })

    else:
        send_message({
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"},
        })


def _format_score(data: dict[str, Any]) -> str:
    return (
        f"최종 점수: {data['score_10']:.1f}/10\n"
        f"  - 어휘: {data['lexical_score_10']:.1f}/10\n"
        f"  - 구조: {data['structure_score_10']:.1f}/10\n"
        f"  - 부정 보너스: {data['negation_score_10']:.1f}/10\n"
        f"신뢰도: {data['reliability']:.2f}\n"
        f"어휘 단위 수: {data.get('lexical_unit_count', 0)}\n"
        f"구조 내용어 수: {data.get('structure_content_token_count', 0)}\n"
        f"미등록 어휘 단위 수: {data.get('unknown_lexical_unit_count', 0)}"
    )


def _format_paragraph_score(data: dict[str, Any]) -> str:
    return (
        f"문단 최종 점수: {data.get('paragraph_score_10', 0):.1f}/10\n"
        f"  - 문장 종합: {data.get('sentence_aggregate', 0):.1f}/10\n"
        f"  - 정보 밀도: {data.get('information_density', 0):.1f}/10\n"
        f"  - 개념 반복도: {data.get('concept_repetition', 0):.1f}/10"
    )


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            handle_request(msg)
        except json.JSONDecodeError:
            send_message({
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error"},
            })


if __name__ == "__main__":
    main()
