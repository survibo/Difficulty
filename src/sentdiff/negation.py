"""
negation.py

MorphToken 리스트를 기반으로 부정 처리 부담(negation processing burden)을 계산한다.
local / construction / embedded는 최고점에 나머지 점수의 40%를 더해 결합한다.
density는 중복 가산하지 않고, 결합 점수보다 클 때만 최종 점수로 사용한다.
"""

from __future__ import annotations

from typing import Any

from .morph import base_sejong_tag
from .patterns import (
    CONDITIONAL_EC, COORDINATE_EC, QUOTE_EC, PatternMatch, PatternMatcher,
)

SUBORDINATE_EC = {
    "서", "어서", "아서",
    "니까", "으니까",
    "므로", "으므로", "기에",
    "지만", "으나", "더라도", "아도", "어도",
    "는데", "은데", "ㄴ데",
}

NOMINAL_BOUND_TAGS = {"ETM", "ETN"}
CONSTRUCTION_SCORE = 0.4


class NegationAnalyzer:
    """형태소 토큰 리스트를 분석하여 부정 처리 부담 점수를 산출한다."""

    def __init__(self) -> None:
        self._pattern_matcher = PatternMatcher()

    @staticmethod
    def _tag(token: Any) -> str:
        return base_sejong_tag(getattr(token, "tag", ""))

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
    def _is_negation_token(token: Any,
                            tokens: list[Any] | None = None,
                            i: int = -1) -> bool:
        tag = NegationAnalyzer._tag(token)
        lemma = NegationAnalyzer._lemma(token)
        surface = NegationAnalyzer._surface(token)
        form = lemma or surface
        stem = NegationAnalyzer._stem_form(form)
        if tag == "MAG":
            return form in {"안", "못"} or surface in {"안", "못"}
        if tag in {"VX", "VV"}:
            return stem.startswith(("않", "아니하", "못하", "말"))
        if tag == "VA":
            if stem == "없":
                if tokens is not None and i >= 0 and i + 2 < len(tokens):
                    n1_tag = NegationAnalyzer._tag(tokens[i + 1])
                    n2_tag = NegationAnalyzer._tag(tokens[i + 2])
                    n2_lemma = NegationAnalyzer._lemma(tokens[i + 2])
                    if n1_tag == "ETM" and n2_lemma == "한" and n2_tag == "NNB":
                        return False
                return True
            return False
        if tag == "VCN":
            return stem == "아니"
        return False

    def _boundary_kind(self, tokens: list[Any], i: int) -> str:
        for match in self._pattern_matcher.match_boundaries(tokens):
            if match.token_start == i:
                return match.kind.removeprefix("boundary_")
        return "none"

    def _build_negation_units(
        self, tokens: list[Any], boundary_matches: list[PatternMatch] | None = None,
    ) -> list[dict[str, Any]]:
        units: list[dict[str, Any]] = []
        current_tokens: list[Any] = []
        current_neg: int = 0
        prev_link: str | None = None
        hard_seg_id = 0
        neg_before_boundary: bool = False

        if boundary_matches is None:
            boundary_matches = self._pattern_matcher.match_boundaries(tokens)
        boundary_kinds = {
            match.token_start: match.kind.removeprefix("boundary_")
            for match in boundary_matches
        }

        for i, token in enumerate(tokens):
            kind = boundary_kinds.get(i, "none")

            if kind in ("none", "aux"):
                current_tokens.append(token)
                if self._is_negation_token(token, tokens, i):
                    current_neg += 1
                continue

            if current_tokens:
                units.append({
                    "tokens": current_tokens.copy(),
                    "neg_count": current_neg,
                    "prev_link": prev_link,
                    "hard_segment_id": hard_seg_id,
                    "neg_before_boundary": neg_before_boundary,
                })

            if kind in ("punct", "coordinate", "subordinate"):
                current_tokens = []
                current_neg = 0
                prev_link = None
                hard_seg_id += 1
                neg_before_boundary = False
            elif kind == "conditional":
                neg_before_boundary = (current_neg > 0)
                current_tokens = []
                current_neg = 0
                prev_link = kind
            elif kind in ("quote", "nominal"):
                neg_before_boundary = False
                current_tokens = []
                current_neg = 0
                prev_link = kind
            else:
                current_tokens = []
                current_neg = 0

        if current_tokens:
            units.append({
                "tokens": current_tokens.copy(),
                "neg_count": current_neg,
                "prev_link": prev_link,
                "hard_segment_id": hard_seg_id,
                "neg_before_boundary": neg_before_boundary,
            })

        return units

    def analyze(
        self, tokens: list[Any], boundary_matches: list[PatternMatch] | None = None,
    ) -> dict[str, Any]:
        if boundary_matches is None:
            boundary_matches = self._pattern_matcher.match_boundaries(tokens)
        units = self._build_negation_units(tokens, boundary_matches)

        total_neg = sum(u["neg_count"] for u in units)
        max_local = max((u["neg_count"] for u in units), default=0)

        # local — 단순 부정은 0, 이중은 0.4, 삼중부터 1.0으로 급등
        local_score = min(1.0, (max_local - 1) ** 2 / 2.5) if max_local >= 2 else 0.0

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
        pending_construction: bool = False

        for u in units:
            sid = u["hard_segment_id"]

            if sid != current_seg:
                current_seg = sid
                last_neg_seen = False
                links_since_last_neg = set()
                pending_construction = False

            link = u["prev_link"]
            if link in {"quote", "nominal", "conditional"}:
                links_since_last_neg.add(link)

            # A single negation in a conditional consequence is ordinary
            # negation. Count construction burden only when negation appears
            # on both sides of the conditional boundary.
            if link == "conditional" and u.get("neg_before_boundary", False):
                pending_construction = True

            if u["neg_count"] > 0:
                if pending_construction:
                    construction_hits += 1
                    pending_construction = False
                if last_neg_seen:
                    if links_since_last_neg & {"quote", "nominal"}:
                        embedded_links += 1
                last_neg_seen = True
                links_since_last_neg = set()

        construction_score = CONSTRUCTION_SCORE if construction_hits > 0 else 0.0
        embedded_score = min(1.0, embedded_links / 2)

        semantic_scores = sorted(
            (local_score, construction_score, embedded_score),
            reverse=True,
        )
        semantic_score = min(1.0, semantic_scores[0] + 0.4 * sum(semantic_scores[1:]))
        final = max(semantic_score, density_score)

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
            "boundary_matches": [
                {
                    "kind": match.kind.removeprefix("boundary_"),
                    "label": match.label,
                    "start": match.start,
                    "end": match.end,
                    "token_start": match.token_start,
                    "token_end": match.token_end,
                }
                for match in boundary_matches
            ],
        }


__all__ = [
    "QUOTE_EC",
    "CONDITIONAL_EC",
    "COORDINATE_EC",
    "SUBORDINATE_EC",
    "NOMINAL_BOUND_TAGS",
    "NegationAnalyzer",
]
