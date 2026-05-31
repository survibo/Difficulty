"""Paragraph-level difficulty scoring built on top of SentenceScorer."""

from __future__ import annotations

import re
from statistics import mean
from typing import Any

from sentdiff.pipeline import SentenceScorer


_SENTENCE_SPLIT_RE = re.compile(r"[^.!?。！？\n]+[.!?。！？]?", re.MULTILINE)

_DISCOURSE_MARKERS: dict[str, float] = {
    "즉": 1.0,
    "따라서": 1.0,
    "그러므로": 1.0,
    "그러나": 1.0,
    "하지만": 1.0,
    "그렇지만": 1.0,
    "그럼에도": 0.9,
    "그럼에도 불구하고": 1.0,
    "반면": 0.9,
    "한편": 0.8,
    "또한": 0.7,
    "더불어": 0.7,
    "아울러": 0.7,
    "나아가": 0.8,
    "게다가": 0.7,
    "결국": 0.9,
    "요컨대": 1.0,
    "종합하면": 1.0,
    "정리하면": 0.9,
    "결론적으로": 1.0,
}


class ParagraphScorer:
    """Score paragraph difficulty without changing sentence scoring behavior."""

    def __init__(self, sentence_scorer: Any | None = None) -> None:
        self._sentence_scorer = sentence_scorer or SentenceScorer()

    @staticmethod
    def split_sentences(paragraph: str | None) -> list[str]:
        text = str(paragraph or "").strip()
        if not text:
            return []
        return [m.group(0).strip() for m in _SENTENCE_SPLIT_RE.finditer(text) if m.group(0).strip()]

    @staticmethod
    def _sentence_aggregate(scores: list[float]) -> dict[str, float]:
        if not scores:
            return {
                "sentence_mean": 0.0,
                "sentence_top_3_mean": 0.0,
                "sentence_max": 0.0,
                "sentence_aggregate": 0.0,
            }

        top_3 = sorted(scores, reverse=True)[:3]
        sentence_mean = mean(scores)
        top_3_mean = mean(top_3)
        sentence_max = max(scores)
        aggregate = 0.4 * sentence_mean + 0.4 * top_3_mean + 0.2 * sentence_max
        return {
            "sentence_mean": round(sentence_mean, 4),
            "sentence_top_3_mean": round(top_3_mean, 4),
            "sentence_max": round(sentence_max, 4),
            "sentence_aggregate": round(aggregate, 4),
        }

    @staticmethod
    def _discourse_marker_weight(sentence: str) -> float:
        stripped = sentence.strip().lstrip("'\"“‘([{")
        for marker, weight in sorted(_DISCOURSE_MARKERS.items(), key=lambda x: len(x[0]), reverse=True):
            if stripped.startswith(marker):
                return weight
        return 0.0

    @classmethod
    def _discourse_score(cls, sentences: list[str]) -> dict[str, float | int]:
        weighted = sum(cls._discourse_marker_weight(sentence) for sentence in sentences)
        count = sum(1 for sentence in sentences if cls._discourse_marker_weight(sentence) > 0.0)
        score = min(1.0, weighted / len(sentences)) if sentences else 0.0
        return {
            "discourse_marker_count": count,
            "discourse_marker_weighted": round(weighted, 4),
            "discourse_marker_score": round(score, 4),
        }

    @staticmethod
    def _information_density(sentence_results: list[dict[str, Any]]) -> dict[str, float | int]:
        lemmas: set[str] = set()
        for result in sentence_results:
            for word in result.get("scored_words_full", []):
                lemma = str(word.get("lemma", "") or "").strip()
                if lemma:
                    lemmas.add(lemma)

        unique_count = len(lemmas)
        full_score_at = len(sentence_results) * 10
        score = min(1.0, unique_count / full_score_at) if full_score_at > 0 else 0.0
        return {
            "unique_content_lemma_count": unique_count,
            "information_density_full_score_at": full_score_at,
            "information_density": round(score, 4),
        }

    def score(self, paragraph: str | None) -> dict[str, Any]:
        text = str(paragraph or "")
        sentences = self.split_sentences(text)
        sentence_results = [self._sentence_scorer.score(sentence) for sentence in sentences]
        sentence_scores = [float(result.get("score_0_1", 0.0)) for result in sentence_results]

        aggregate = self._sentence_aggregate(sentence_scores)
        discourse = self._discourse_score(sentences)
        density = self._information_density(sentence_results)

        score_0_1 = (
            0.70 * float(aggregate["sentence_aggregate"])
            + 0.30 * float(density["information_density"])
        )
        score_0_1 = max(0.0, min(1.0, score_0_1))

        return {
            "paragraph": text,
            "score_0_1": round(score_0_1, 4),
            "score_10": round(score_0_1 * 10, 2),
            "sentence_count": len(sentences),
            "sentences": sentence_results,
            "paragraph_parts": {
                **aggregate,
                **discourse,
                **density,
                "paragraph_weights": {
                    "sentence_aggregate": 0.70,
                    "information_density": 0.30,
                },
            },
        }
