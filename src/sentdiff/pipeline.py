"""
pipeline.py

KiwiMorphAnalyzer + LexiconScorer + StructureScorer를 내부에서 관리하여,
문장 하나를 받으면 최종 난도 점수까지 한 번에 처리한다.

점수 구성:
  score_0_1 = 0.50 * lexical_score_0_1 + 0.50 * structure_score_0_1
"""

from __future__ import annotations

from typing import Any

from .lexical import LexiconConfig, LexiconScorer
from .morph import KiwiMorphAnalyzer
from .structure import StructureConfig, StructureScorer

_LEXICAL_WEIGHT: float = 0.50
_STRUCTURE_WEIGHT: float = 0.50


class SentenceScorer:
    def __init__(
        self,
        lexicon_config: LexiconConfig | None = None,
        structure_config: StructureConfig | None = None,
    ) -> None:
        self._analyzer = KiwiMorphAnalyzer()
        self._lexical_scorer = LexiconScorer(lexicon_config)
        self._structure_scorer = StructureScorer(structure_config)

    def score(self, sentence: str | None) -> dict[str, Any]:
        if sentence is None:
            sentence = ""

        tokens = self._analyzer.analyze(sentence)
        lexical_result = self._lexical_scorer.compute_sentence_score(tokens)
        structure_result = self._structure_scorer.score_tokens(tokens)

        lexical_score = lexical_result["lexical_score_0_1"]
        structure_score = structure_result["structure_score_0_1"]

        score_0_1 = _LEXICAL_WEIGHT * lexical_score + _STRUCTURE_WEIGHT * structure_score
        score_0_1 = max(0.0, min(1.0, score_0_1))

        return {
            "sentence": sentence,
            "score_0_1": round(score_0_1, 4),
            "score_10": round(score_0_1 * 10, 2),
            "lexical_score_0_1": lexical_score,
            "lexical_score_10": round(lexical_score * 10, 2),
            "structure_score_0_1": structure_score,
            "structure_score_10": structure_result["structure_score_10"],
            "content_token_count": lexical_result["content_token_count"],
            "content_token_count_capped": lexical_result.get("content_token_count_capped", lexical_result["content_token_count"]),
            "unknown_token_count": lexical_result["unknown_token_count"],
            "scored_words": lexical_result["scored_words"],
            "score_parts": lexical_result["score_parts"],
            "structure_parts": structure_result["structure_parts"],
            "lexical_weight": _LEXICAL_WEIGHT,
            "structure_weight": _STRUCTURE_WEIGHT,
        }


__all__ = [
    "SentenceScorer",
]
