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
from .normalize import normalize_text
from .patterns import PatternMatcher
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
        self._pattern_matcher = PatternMatcher()

    def score(self, sentence: str | None) -> dict[str, Any]:
        if sentence is None:
            sentence = ""

        analysis_text = normalize_text(sentence)
        tokens = self._analyzer.analyze(analysis_text)
        lexical_result = self._lexical_scorer.compute_sentence_score(tokens, analysis_text)
        logical_matches = self._pattern_matcher.match_logical_markers(analysis_text, tokens)
        strong_ending_matches = self._pattern_matcher.match_strong_endings(tokens)
        boundary_matches = self._pattern_matcher.match_boundaries(tokens)

        scored_full = lexical_result["scored_words_full"]
        unique_surfaces = {s["surface"] for s in scored_full if s["surface"]}
        polysemy_map: dict[str, int] = {}
        for surface in unique_surfaces:
            polysemy_map[surface] = self._analyzer.get_polysemy(surface)

        structure_result = self._structure_scorer.score_tokens(
            tokens, analysis_text,
            scored_words_full=scored_full,
            polysemy_map=polysemy_map,
            logical_matches=logical_matches,
            strong_ending_matches=strong_ending_matches,
        )
        negation_result = self._negation_analyzer.analyze(tokens, boundary_matches)

        lexical_score = lexical_result["lexical_score_0_1"]
        structure_score = structure_result["structure_score_0_1"]
        negation_score = negation_result["negation_score"]

        score_0_1 = (
            0.5 * lexical_score + 0.5 * structure_score
            + _NEGATION_BONUS_COEFF * negation_score
        )
        score_0_1 = max(0.0, min(1.0, score_0_1))

        content_count = lexical_result["lexical_unit_count"]
        unknown_count = lexical_result["unknown_lexical_unit_count"]
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
            "lexical_unit_count": lexical_result["lexical_unit_count"],
            "lexical_unit_count_capped": lexical_result.get("lexical_unit_count_capped", lexical_result["lexical_unit_count"]),
            "unknown_lexical_unit_count": lexical_result["unknown_lexical_unit_count"],
            "structure_content_token_count": structure_result["structure_parts"]["structure_content_token_count"],
            "scored_words_full": lexical_result["scored_words_full"],
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
