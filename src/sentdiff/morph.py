"""
morph.py

Kiwi 기반 형태소 분석을 문장 난이도 계산에 필요한 공통 토큰 형태로 변환한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .normalize import normalize_text


@dataclass(frozen=True)
class MorphToken:
    surface: str
    lemma: str
    tag: str
    pos: str
    start: int
    end: int
    is_content: bool


def sejong_tag_to_pos(tag: Any) -> str:
    """
    Kiwi/Sejong 계열 형태소 태그를 사전 품사명으로 변환한다.
    """
    t = normalize_text(tag)

    if not t:
        return ""

    if t.startswith("NN"):
        return "명사"
    if t == "NP":
        return "대명사"
    if t == "NR":
        return "수사"
    if t == "VV":
        return "동사"
    if t == "VA":
        return "형용사"
    if t in {"VCP", "VCN"}:
        return "지정사"
    if t == "VX":
        return "보조용언"
    if t == "MAG":
        return "부사"
    if t == "MAJ":
        return "접속부사"
    if t == "MM":
        return "관형사"
    if t == "XR":
        return "어근"
    if t == "SL":
        return "외국어"
    if t == "SH":
        return "한자"
    if t == "SN":
        return "숫자"
    if t.startswith("J"):
        return "조사"
    if t.startswith("E"):
        return "어미"
    if t in {"XPN", "XSN", "XSV", "XSA"}:
        return "접사"
    if t == "IC":
        return "감탄사"
    if t.startswith("S"):
        return "기호"
    if t.startswith("N"):
        return "명사"

    return t


def token_to_lemma_candidate(surface: Any, tag: Any) -> str:
    """
    형태소 분석 결과를 사전 lookup용 lemma 후보로 변환한다.
    """
    form = normalize_text(surface)
    t = normalize_text(tag)

    if not form:
        return ""

    if t in {"VV", "VA"} and not form.endswith("다"):
        return form + "다"

    return form


def _base_tag(tag: str) -> str:
    """Kiwi 접미사(-I 등) 제거한 기본 품사 태그를 반환한다."""
    return tag.split("-")[0] if "-" in tag else tag


def is_excluded_lexical_tag(tag: Any) -> bool:
    """
    lexical difficulty 계산에서 제외할 기능 표지를 판정한다.
    """
    t = normalize_text(tag)

    if not t:
        return True

    base = _base_tag(t)

    if base in {"SL", "SH"}:
        return False

    return (
        base == "VX"
        or base in {"XSV", "XSA", "XPN", "XSN"}
        or base.startswith("J")
        or base.startswith("E")
        or base.startswith("S")
    )


def is_content_tag(tag: Any) -> bool:
    """
    문장 난이도 어휘 점수에서 내용어 후보로 볼 품사인지 판정한다.
    """
    t = normalize_text(tag)

    if not t or is_excluded_lexical_tag(t):
        return False

    base = _base_tag(t)

    return base.startswith("NN") or base in {
        "NP",
        "NR",
        "VV",
        "VA",
        "MAG",
        "XR",
        "SL",
        "SH",
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _token_to_morph_token(token: Any) -> MorphToken:
    surface = normalize_text(getattr(token, "form", ""))
    tag = normalize_text(getattr(token, "tag", ""))
    start = _safe_int(getattr(token, "start", 0), default=0)

    token_end = getattr(token, "end", None)
    if token_end is None:
        token_len = _safe_int(getattr(token, "len", len(surface)), default=len(surface))
        end = start + token_len
    else:
        end = _safe_int(token_end, default=start + len(surface))

    return MorphToken(
        surface=surface,
        lemma=token_to_lemma_candidate(surface, tag),
        tag=tag,
        pos=sejong_tag_to_pos(tag),
        start=start,
        end=end,
        is_content=is_content_tag(tag),
    )


class KiwiMorphAnalyzer:
    """
    Kiwi 1-best 분석 결과를 MorphToken 리스트로 변환한다.
    """

    def __init__(self, kiwi: Any | None = None) -> None:
        if kiwi is not None:
            self._kiwi = kiwi
            return

        try:
            from kiwipiepy import Kiwi
        except ImportError as exc:
            raise ImportError(
                "kiwipiepy가 설치되어 있지 않습니다. "
                "현재 venv에서 `python -m pip install kiwipiepy`를 실행하세요."
            ) from exc

        self._kiwi = Kiwi()

    def analyze(self, sentence: Any) -> list[MorphToken]:
        text = normalize_text(sentence)
        if not text:
            return []

        analyzed = self._kiwi.analyze(text, top_n=1)
        if not analyzed:
            return []

        tokens = analyzed[0][0]
        return [_token_to_morph_token(token) for token in tokens]

    def content_tokens(self, sentence: Any) -> list[MorphToken]:
        return [token for token in self.analyze(sentence) if token.is_content]

    def get_polysemy(self, surface: str) -> int:
        if not normalize_text(surface):
            return 1
        results = self._kiwi.analyze(surface, top_n=5)
        if not results:
            return 1
        tags: set[str] = set()
        for tokens, _ in results:
            if tokens:
                tags.add(tokens[0].tag)
        return max(1, len(tags))


__all__ = [
    "MorphToken",
    "KiwiMorphAnalyzer",
    "sejong_tag_to_pos",
    "token_to_lemma_candidate",
    "is_excluded_lexical_tag",
    "is_content_tag",
]
