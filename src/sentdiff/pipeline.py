"""
pipeline.py

KiwiMorphAnalyzer + LexiconScorer + StructureScorer + NegationAnalyzer를 내부에서 관리하여,
문장 하나를 받으면 최종 난도 점수까지 한 번에 처리한다.

점수 구성:
  score = min(1.0, 0.5 * lexical + 0.5 * structure + 0.2 * negation)
"""

from __future__ import annotations

from typing import Any

from .lexical import LexiconConfig, LexiconScorer
from .morph import KiwiMorphAnalyzer
from .negation import NegationAnalyzer
from .structure import StructureConfig, StructureScorer

_LEXICAL_WEIGHT: float = 5.0
_STRUCTURE_WEIGHT: float = 5.0
_NEGATION_BONUS_COEFF: float = 0.2


class SentenceScorer:
    def __init__(
        self,
        lexicon_config: LexiconConfig | None = None,
        structure_config: StructureConfig | None = None,
    ) -> None:
        self._analyzer = KiwiMorphAnalyzer()
        self._lexical_scorer = LexiconScorer(lexicon_config)
        self._structure_scorer = StructureScorer(structure_config)
        self._negation_analyzer = NegationAnalyzer()

    def score(self, sentence: str | None) -> dict[str, Any]:
        if sentence is None:
            sentence = ""

        tokens = self._analyzer.analyze(sentence)
        lexical_result = self._lexical_scorer.compute_sentence_score(tokens)
        structure_result = self._structure_scorer.score_tokens(tokens)
        negation_result = self._negation_analyzer.analyze(tokens)

        lexical_score = lexical_result["lexical_score_0_1"]
        structure_score = structure_result["structure_score_0_1"]
        negation_score = negation_result["negation_score"]

        score_0_1 = (
            0.5 * lexical_score + 0.5 * structure_score
            + _NEGATION_BONUS_COEFF * negation_score
        )
        score_0_1 = max(0.0, min(1.0, score_0_1))

        content_count = lexical_result["content_token_count"]
        unknown_count = lexical_result["unknown_token_count"]
        reliability = (
            1.0 - (unknown_count / content_count)
            if content_count > 0
            else 1.0
        )

        return {
            "sentence": sentence,
            "score_0_1": round(score_0_1, 4),
            "score_10": round(score_0_1 * 10, 2),
            "lexical_score_0_1": lexical_score,
            "lexical_score_10": round(lexical_score * 10, 2),
            "structure_score_0_1": structure_score,
            "structure_score_10": structure_result["structure_score_10"],
            "negation_score_0_1": round(negation_score, 4),
            "negation_score_10": round(negation_score * 10, 2),
            "content_token_count": lexical_result["content_token_count"],
            "content_token_count_capped": lexical_result.get("content_token_count_capped", lexical_result["content_token_count"]),
            "unknown_token_count": lexical_result["unknown_token_count"],
            "scored_words": lexical_result["scored_words"],
            "score_parts": lexical_result["score_parts"],
            "structure_parts": structure_result["structure_parts"],
            "negation_detail": negation_result,
            "lexical_weight": _LEXICAL_WEIGHT,
            "structure_weight": _STRUCTURE_WEIGHT,
            "negation_bonus_coefficient": _NEGATION_BONUS_COEFF,
            "reliability": round(max(0.0, reliability), 4),
        }


__all__ = [
    "SentenceScorer",
]
