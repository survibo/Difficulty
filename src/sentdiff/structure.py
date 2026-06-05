"""
structure.py

MorphToken 리스트의 POS 태그 패턴을 기반으로 문장 구조 복잡도를 계산한다.
8개 지표(length / predicate / embedding / connective / logical / modifier / repetition / structural_span)를
weighted sum한 structure_score를 반환한다.
negation 점수는 별도 negation.py의 NegationAnalyzer가 처리한다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

LOGICAL_MARKERS: dict[str, float] = {
    "즉": 1.0, "곧": 0.8,
    "다시 말해": 1.0, "다시 말하면": 1.0, "말하자면": 0.8,
    "예컨대": 0.8, "예를 들어": 0.8,
    "따라서": 1.0, "그러므로": 1.0,
    "그렇기 때문에": 1.0, "그 때문에": 0.9, "그 결과": 0.9,
    "결과적으로": 0.9, "이로 인해": 0.9, "이 때문에": 0.9,
    "왜냐하면": 1.0,
    "그러나": 1.0, "하지만": 1.0, "그렇지만": 1.0,
    "반면": 0.9, "반대로": 0.9, "오히려": 0.8,
    "그럼에도": 0.9, "그럼에도 불구하고": 1.0, "비록": 0.8, "물론": 0.7,
    "만약": 1.0, "만일": 1.0, "가령": 0.8,
    "또한": 0.7, "더불어": 0.7, "아울러": 0.7,
    "나아가": 0.8, "게다가": 0.7, "한편": 0.8, "동시에": 0.7,
    "결국": 0.9, "요컨대": 1.0, "종합하면": 1.0,
    "정리하면": 0.9, "결론적으로": 1.0, "뿐 아니라": 0.8,
"뿐만 아니라": 0.9,
"아니라": 0.5,
}

STRONG_LOGICAL_ENDINGS: dict[str, float] = {
    "므로": 1.0, "으므로": 1.0, "기에": 0.9, "때문에": 1.0,
    "면": 0.8, "으면": 0.8, "다면": 1.0, "라면": 1.0, "거든": 0.8,
    "지만": 1.0, "으나": 0.9, "더라도": 1.0,
    "아도": 0.9, "어도": 0.9, "을지라도": 1.0,
    "려고": 0.7, "으려고": 0.7, "도록": 0.8,
    "는데": 0.6, "은데": 0.6, "ㄴ데": 0.6,
}

DERIVATIONAL_SUFFIXES: set[str] = {
    "적", "성", "화", "론", "주의",
}

ADVERBIAL_EC_FORMS: set[str] = {"게", "도록", "듯이"}

REPETITION_EXCLUDE_LEMMAS: set[str] = {
    "것", "수", "때", "말", "점", "등", "바", "데",
}
REPETITION_MIN_DIFFICULTY: float = 0.05

_STRUCTURAL_SPAN_MARKER_TAGS: set[str] = {"ETM", "ETN", "EC"}
_BOUNDARY_TAGS: set[str] = {"EC", "ETM", "ETN", "EF", "SF", "SP", "SE"}
_LENGTH_MIN: float = 5.0
_LENGTH_MAX: float = 24.0


@dataclass(frozen=True)
class StructureConfig:
    predicate_full_score_at: int = 7
    embedding_full_score_at: int = 5
    connective_full_score_at: int = 4
    logical_full_score_at: int = 4
    modifier_full_score_at: int = 3
    derivational_full_score_at: int = 3
    structural_span_full_score_at: float = 20.0
    repetition_full_score_at: float = 3.5

   # 8개 지표 고정 가중치 (합 1.0)
    weight_length: float = 0.15
    weight_predicate: float = 0.18
    weight_embedding: float = 0.15
    weight_connective: float = 0.05
    weight_logical: float = 0.08
    weight_modifier: float = 0.10
    weight_structural_span: float = 0.22
    weight_repetition: float = 0.07


class StructureScorer:
    def __init__(self, config: StructureConfig | None = None) -> None:
        self.config = config or StructureConfig()

    @staticmethod
    def _safe_ratio(value: int, full_score_at: int) -> float:
        if full_score_at <= 0:
            return 0.0
        return max(0.0, min(1.0, value / full_score_at))

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
    def _is_content(token: Any) -> bool:
        return bool(getattr(token, "is_content", False))

    def _compute_length_score(self, content_count: int) -> float:
        if content_count <= _LENGTH_MIN:
            return 0.0
        raw = (content_count - _LENGTH_MIN) / _LENGTH_MAX
        return min(1.0, raw)

    @staticmethod
    def _match_weighted(
        token: Any, table: dict[str, float]
    ) -> float:
        surface = str(getattr(token, "surface", "") or "")
        lemma = str(getattr(token, "lemma", "") or "")
        if surface in table:
            return table[surface]
        if lemma in table:
            return table[lemma]
        return 0.0

    def _first_non_punctuation_index(self, tokens: list[Any]) -> int | None:
        for i, token in enumerate(tokens):
            tag = self._tag(token)
            if tag in {"SP", "SF", "SE"} or tag.startswith("SS"):
                continue
            return i
        return None

    @staticmethod
    def _is_aux_ec(tokens: list[Any], i: int) -> bool:
        tag = str(getattr(tokens[i], "tag", "") or "")
        if tag != "EC":
            return False
        for j in range(i + 1, min(i + 4, len(tokens))):
            if str(getattr(tokens[j], "tag", "") or "") == "VX":
                return True
        return False

    def _max_noun_chain(self, tokens: list[Any]) -> int:
        max_chain = 0
        current = 0

        for token in tokens:
            tag = self._tag(token)

            if tag in {"NNG", "NNP", "NNB", "XR"}:
                current = current + 1 if current > 0 else 1
                max_chain = max(max_chain, current)
            elif tag == "XSN" and current > 0:
                continue
            else:
                current = 0

        return max_chain

    def _compute_structural_span(self, tokens: list[Any]) -> dict[str, float | int]:
        segment_content_count = 0
        spans: list[int] = []

        for i, token in enumerate(tokens):
            tag = self._tag(token)

            if self._is_content(token):
                segment_content_count += 1

            if tag in _STRUCTURAL_SPAN_MARKER_TAGS and segment_content_count > 0:
                spans.append(segment_content_count)

            if tag in _BOUNDARY_TAGS and not self._is_aux_ec(tokens, i):
                segment_content_count = 0

        if not spans:
            return {"score": 0.0, "raw": 0.0, "normalized": 0.0, "count": 0}

        raw_span = sum(spans)
        normalized = raw_span / self.config.structural_span_full_score_at
        score = min(1.0, normalized)

        return {
            "score": round(score, 4),
            "raw": round(raw_span, 4),
            "normalized": round(normalized, 4),
            "count": len(spans),
        }

    def _compute_repetition_score(
        self,
        scored_words_full: list[dict[str, Any]],
        polysemy_map: dict[str, int],
    ) -> dict[str, Any]:
        surface_counts: Counter[str] = Counter()
        surface_difficulty: dict[str, float] = {}
        surface_lemma: dict[str, str] = {}

        for sw in scored_words_full:
            surface = sw.get("surface", "")
            surface_counts[surface] += 1
            surface_difficulty.setdefault(surface, sw.get("difficulty", 0.3))
            surface_lemma.setdefault(surface, sw.get("lemma", ""))

        raw = 0.0
        details: list[dict[str, Any]] = []
        for surface, count in surface_counts.items():
            lemma = surface_lemma.get(surface, "")
            if lemma in REPETITION_EXCLUDE_LEMMAS:
                continue
            if count <= 1:
                continue
            difficulty = max(REPETITION_MIN_DIFFICULTY, surface_difficulty.get(surface, 0.3))
            polysemy = polysemy_map.get(surface, 1)
            contribution = (count - 1) * difficulty * polysemy
            raw += contribution
            details.append({
                "surface": surface,
                "lemma": lemma,
                "count": count,
                "difficulty": round(difficulty, 4),
                "polysemy": polysemy,
                "contribution": round(contribution, 4),
            })

        score = min(1.0, raw / self.config.repetition_full_score_at)
        return {
            "raw": round(raw, 4),
            "score": round(score, 4),
            "repetition_count": sum(d["count"] - 1 for d in details),
            "details": details,
        }

    def score_tokens(self, tokens: list[Any], sentence: str = "",
                     scored_words_full: list[dict[str, Any]] | None = None,
                     polysemy_map: dict[str, int] | None = None) -> dict[str, Any]:
        content_token_count = sum(1 for t in tokens if self._is_content(t))

        predicate_count = sum(
            1 for t in tokens
            if self._tag(t) in {"VV", "VA", "VX", "XSV", "XSA"}
        )

        ending_count = sum(
            1 for t in tokens
            if self._tag(t).startswith("E")
        )

        connective_ending_count = sum(
            1 for t in tokens
            if self._tag(t) == "EC"
        )

        adnominal_count = sum(
            1 for t in tokens
            if self._tag(t) == "ETM"
        )

        nominalizer_count = sum(
            1 for t in tokens
            if self._tag(t) == "ETN"
        )

        adverbial_ending_count = sum(
            1 for t in tokens
            if self._tag(t) == "EC"
            and (self._surface(t) in ADVERBIAL_EC_FORMS
                 or self._lemma(t) in ADVERBIAL_EC_FORMS)
        )

        first_token_index = self._first_non_punctuation_index(tokens)
        logical_marker_weighted = sum(
            self._match_weighted(t, LOGICAL_MARKERS)
            for i, t in enumerate(tokens)
            if i != first_token_index
        )
        logical_marker_count = sum(
            1 for i, t in enumerate(tokens)
            if i != first_token_index
            and self._match_weighted(t, LOGICAL_MARKERS) > 0.0
        )

        strong_logical_ending_weighted = sum(
            self._match_weighted(t, STRONG_LOGICAL_ENDINGS)
            for t in tokens
            if self._tag(t) == "EC"
        )
        strong_logical_ending_count = sum(
            1 for t in tokens
            if self._tag(t) == "EC"
            and self._match_weighted(t, STRONG_LOGICAL_ENDINGS) > 0.0
        )

        derivational_suffix_count = sum(
            1 for t in tokens
            if self._tag(t) in {"XSN"}
            or self._surface(t) in DERIVATIONAL_SUFFIXES
        )

        max_noun_chain = self._max_noun_chain(tokens)
        structural_span = self._compute_structural_span(tokens)
        repetition = self._compute_repetition_score(
            scored_words_full or [],
            polysemy_map or {},
        )

        length_score = self._compute_length_score(content_token_count)
        adj_predicate_count = max(0, predicate_count - 1)
        predicate_score = self._safe_ratio(
            adj_predicate_count, self.config.predicate_full_score_at,
        )
        embedding_score = self._safe_ratio(
            adnominal_count + nominalizer_count + adverbial_ending_count,
            self.config.embedding_full_score_at,
        )
        connective_score = self._safe_ratio(
            connective_ending_count, self.config.connective_full_score_at,
        )
        logical_raw = (
            logical_marker_weighted
            + strong_logical_ending_weighted
        )
        logical_score = min(1.0, logical_raw / self.config.logical_full_score_at)
        adj_max_noun_chain = max(0, max_noun_chain - 1)
        modifier_score = self._safe_ratio(
            adj_max_noun_chain, self.config.modifier_full_score_at,
        )
        derivational_score = self._safe_ratio(
            derivational_suffix_count, self.config.derivational_full_score_at,
        )

        structure_score = (
            self.config.weight_length * length_score
            + self.config.weight_predicate * predicate_score
            + self.config.weight_embedding * embedding_score
            + self.config.weight_connective * connective_score
            + self.config.weight_logical * logical_score
            + self.config.weight_modifier * modifier_score
            + self.config.weight_structural_span * structural_span["score"]
            + self.config.weight_repetition * repetition["score"]
        )
        structure_score = max(0.0, min(1.0, structure_score))
        rounded_score = round(structure_score, 4)

        return {
            "structure_score_0_1": rounded_score,
            "structure_score_10": round(rounded_score * 10, 2),
            "structure_parts": {
                "length_score": round(length_score, 4),
                "predicate_score": round(predicate_score, 4),
                "embedding_score": round(embedding_score, 4),
                "modifier_score": round(modifier_score, 4),
                "derivational_score": round(derivational_score, 4),
                "structural_span_score": structural_span["score"],
                "structural_span_raw": structural_span["raw"],
                "structural_span_normalized": structural_span["normalized"],
                "structural_span_count": structural_span["count"],
                "repetition_score": repetition["score"],
                "repetition_raw": repetition["raw"],
                "repetition_count": repetition["repetition_count"],
                "repetition_details": repetition["details"],
                "content_token_count": content_token_count,
                "predicate_count": predicate_count,
                "predicate_count_adj": adj_predicate_count,
                "ending_count": ending_count,
                "connective_ending_count": connective_ending_count,
                "adnominal_count": adnominal_count,
                "nominalizer_count": nominalizer_count,
                "adverbial_ending_count": adverbial_ending_count,
                "connective_score": round(connective_score, 4),
                "logical_score": round(logical_score, 4),
                "logical_marker_weighted": round(logical_marker_weighted, 4),
                "logical_marker_count": logical_marker_count,
                "strong_logical_ending_weighted": round(strong_logical_ending_weighted, 4),
                "strong_logical_ending_count": strong_logical_ending_count,
                "derivational_suffix_count": derivational_suffix_count,
                "max_noun_chain": max_noun_chain,
                "max_noun_chain_adj": adj_max_noun_chain,
            },
        }


__all__ = [
    "LOGICAL_MARKERS",
    "STRONG_LOGICAL_ENDINGS",
    "DERIVATIONAL_SUFFIXES",
    "ADVERBIAL_EC_FORMS",
    "REPETITION_EXCLUDE_LEMMAS",
    "StructureConfig",
    "StructureScorer",
]
