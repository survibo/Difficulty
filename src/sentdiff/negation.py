"""
negation.py

MorphToken 리스트를 기반으로 부정 처리 부담(negation processing burden)을 계산한다.
4개 하위 점수(local / construction / embedded / density)의 max를 negation_score로 반환한다.
"""

from __future__ import annotations

from typing import Any

QUOTE_EC = {
    "라고", "이라고",
    "다고", "ㄴ다고", "는다고",
    "냐고", "느냐고",
    "자고",
}

CONDITIONAL_EC = {"면", "으면", "다면", "라면"}

COORDINATE_EC = {"고", "며", "으며", "거나", "든지"}

SUBORDINATE_EC = {
    "서", "어서", "아서",
    "니까", "으니까",
    "므로", "으므로", "기에",
    "지만", "으나", "더라도", "아도", "어도",
    "는데", "은데", "ㄴ데",
}

NOMINAL_BOUND_TAGS = {"ETM", "ETN"}


class NegationAnalyzer:
    """형태소 토큰 리스트를 분석하여 부정 처리 부담 점수를 산출한다."""

    @staticmethod
    def _tag(token: Any) -> str:
        return str(getattr(token, "tag", "") or "")

    @staticmethod
    def _surface(token: Any) -> str:
        return str(getattr(token, "surface", "") or "")

    @staticmethod
    def _lemma(token: Any) -> str:
        return str(getattr(token, "lemma", "") or "")

    @staticmethod
    def _stem_form(value: str) -> str:
        value = str(value or "").strip()
        if value.endswith("다"):
            value = value[:-1]
        return value.strip()

    @staticmethod
    def _is_negation_token(token: Any) -> bool:
        tag = NegationAnalyzer._tag(token)
        lemma = NegationAnalyzer._lemma(token)
        surface = NegationAnalyzer._surface(token)
        form = lemma or surface
        stem = NegationAnalyzer._stem_form(form)
        if tag == "MAG":
            return form in {"안", "못"} or surface in {"안", "못"}
        if tag in {"VX", "VV"}:
            return stem.startswith(("않", "못하", "말"))
        if tag == "VA":
            return stem == "없"
        if tag == "VCN":
            return stem == "아니"
        return False

    def _boundary_kind(self, tokens: list[Any], i: int) -> str:
        token = tokens[i]
        tag = self._tag(token)

        # punctuation
        if tag in {"SP", "SF", "SE"} or tag.startswith("SS"):
            return "punct"

        # ETM/ETN — only nominal boundary when followed by NNB + JX
        # ("할 수 없다" vs "간 것은 아니다")
        if tag in NOMINAL_BOUND_TAGS:
            if i + 2 < len(tokens):
                next1_tag = self._tag(tokens[i + 1])
                next2_tag = self._tag(tokens[i + 2])
                if next1_tag in {"NNB", "NNG"} and next2_tag in {"JX", "JKS", "JKO", "JKC"}:
                    return "nominal"
            return "none"

        # non-EC → no boundary
        if tag != "EC":
            return "none"

        # EC → aux: VX that is immediate, or after inserted particles (JX, JKO, JKC)
        j = i + 1
        while j < len(tokens):
            ntag = self._tag(tokens[j])
            if ntag == "VX":
                return "aux"
            if ntag in {"JX", "JKO", "JKC"}:
                j += 1
                continue
            break

        ec_form = self._surface(token) or self._lemma(token)
        if ec_form in QUOTE_EC:
            return "quote"
        if ec_form in CONDITIONAL_EC:
            return "conditional"
        if ec_form in COORDINATE_EC:
            return "coordinate"
        return "subordinate"

    def _build_negation_units(self, tokens: list[Any]) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []
        current_tokens: list[Any] = []
        prev_link: str | None = None
        hard_seg_id = 0

        def _append_unit() -> None:
            nonlocal current_tokens, prev_link, hard_seg_id
            if not current_tokens:
                return
            units.append({
                "tokens": current_tokens.copy(),
                "neg_count": sum(
                    1 for t in current_tokens if self._is_negation_token(t)
                ),
                "prev_link": prev_link,
                "hard_segment_id": hard_seg_id,
            })

        for i, token in enumerate(tokens):
            kind = self._boundary_kind(tokens, i)

            if kind in ("none", "aux"):
                current_tokens.append(token)
                continue

            _append_unit()

            if kind in ("punct", "coordinate", "subordinate"):
                current_tokens = []
                prev_link = None
                hard_seg_id += 1
            elif kind in ("quote", "conditional", "nominal"):
                current_tokens = []
                prev_link = kind
            else:
                current_tokens = []

        _append_unit()
        return units

    def analyze(self, tokens: list[Any]) -> dict[str, Any]:
        units = self._build_negation_units(tokens)

        total_neg = sum(u["neg_count"] for u in units)
        max_local = max((u["neg_count"] for u in units), default=0)

        # local
        local_score = min(1.0, max(0.0, (max_local - 1) / 2))

        # segment-level density
        seg_neg_counts: dict[int, int] = {}
        for u in units:
            sid = u["hard_segment_id"]
            seg_neg_counts[sid] = seg_neg_counts.get(sid, 0) + u["neg_count"]
        max_seg_neg = max(seg_neg_counts.values(), default=0)
        density_score = 0.5 * min(1.0, max(0, max_seg_neg - 1) / 3)

        # construction / embedded — segment-aware link tracking
        construction_hits = 0
        embedded_links = 0
        current_seg: int | None = None
        last_neg_seen = False
        links_since_last_neg: set[str] = set()

        for u in units:
            sid = u["hard_segment_id"]

            if sid != current_seg:
                current_seg = sid
                last_neg_seen = False
                links_since_last_neg = set()

            link = u["prev_link"]
            if link in {"quote", "nominal", "conditional"}:
                links_since_last_neg.add(link)

            if u["neg_count"] > 0:
                if last_neg_seen:
                    if "conditional" in links_since_last_neg:
                        construction_hits += 1
                    if links_since_last_neg & {"quote", "nominal"}:
                        embedded_links += 1
                last_neg_seen = True
                links_since_last_neg = set()

        construction_score = 1.0 if construction_hits > 0 else 0.0
        embedded_score = min(1.0, embedded_links / 2)

        final = max(local_score, construction_score, embedded_score, density_score)

        return {
            "negation_count_total": total_neg,
            "negation_count_local_max": max_local,
            "negation_embedded_links": embedded_links,
            "negation_construction_hits": construction_hits,
            "local_negation_score": local_score,
            "construction_negation_score": construction_score,
            "embedded_negation_score": embedded_score,
            "negation_density_score": density_score,
            "negation_score": final,
        }


__all__ = [
    "QUOTE_EC",
    "CONDITIONAL_EC",
    "COORDINATE_EC",
    "SUBORDINATE_EC",
    "NOMINAL_BOUND_TAGS",
    "NegationAnalyzer",
]
