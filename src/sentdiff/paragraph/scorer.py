"""Paragraph-level difficulty scoring built on top of SentenceScorer."""

from __future__ import annotations

from collections import defaultdict
import re
from statistics import mean
from typing import Any

from sentdiff.pipeline import SentenceScorer


_SENTENCE_SPLIT_RE = re.compile(r"[^.!?。！？\n]+[.!?。！？]?", re.MULTILINE)

_CORE_INFORMATION_TAGS: set[str] = {"NNG", "NNP", "VV", "VA", "XR"}
_CORE_INFORMATION_POS: set[str] = {"명사", "동사", "형용사", "어근"}
_CONCEPT_REPETITION_EXCLUDED_LEMMAS: set[str] = {"것", "수", "때", "말", "점", "등", "바", "데"}
_INFORMATION_DENSITY_PER_SENTENCE: int = 13
_CONCEPT_REPETITION_FULL_SCORE_AT: float = 10.0
_CONCEPT_REPETITION_MIN_DIFFICULTY: float = 0.05


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
    def _is_core_information_word(word: dict[str, Any]) -> bool:
        tag = str(word.get("tag", "") or "").strip()
        base_tag = tag.split("-")[0]
        if base_tag in _CORE_INFORMATION_TAGS:
            return True
        if base_tag.isascii() and base_tag.isalnum():
            return False

        pos = str(word.get("pos", "") or "").strip()
        return pos in _CORE_INFORMATION_POS

    @staticmethod
    def _core_item_type(word: dict[str, Any]) -> str:
        tag = str(word.get("tag", "") or "").strip()
        if tag:
            return tag.split("-")[0]
        return str(word.get("pos", "") or "").strip()

    @staticmethod
    def _safe_difficulty(word: dict[str, Any]) -> float:
        try:
            difficulty = float(word.get("difficulty", 0.30))
        except (TypeError, ValueError):
            difficulty = 0.30
        return max(_CONCEPT_REPETITION_MIN_DIFFICULTY, min(1.0, difficulty))

    @staticmethod
    def _concept_pos_weight(item_type: str) -> float:
        if item_type in {"VV", "VA", "동사", "형용사"}:
            return 0.8
        return 1.0

    @staticmethod
    def _information_density(sentence_results: list[dict[str, Any]]) -> dict[str, float | int]:
        core_items: set[tuple[str, str]] = set()
        for result in sentence_results:
            for word in result.get("scored_words_full", []):
                if not ParagraphScorer._is_core_information_word(word):
                    continue
                lemma = str(word.get("lemma", "") or "").strip()
                item_type = ParagraphScorer._core_item_type(word)
                if lemma:
                    core_items.add((lemma, item_type))

        unique_count = len(core_items)
        full_score_at = len(sentence_results) * _INFORMATION_DENSITY_PER_SENTENCE
        score = min(1.0, unique_count / full_score_at) if full_score_at > 0 else 0.0
        return {
            "unique_core_content_count": unique_count,
            "information_density_full_score_at": full_score_at,
            "information_density": round(score, 4),
        }

    @staticmethod
    def _concept_repetition(sentence_results: list[dict[str, Any]]) -> dict[str, float | int]:
        counts: defaultdict[tuple[str, str], int] = defaultdict(int)
        sentence_ids: defaultdict[tuple[str, str], set[int]] = defaultdict(set)
        difficulties: defaultdict[tuple[str, str], list[float]] = defaultdict(list)

        for sentence_id, result in enumerate(sentence_results):
            for word in result.get("scored_words_full", []):
                if not ParagraphScorer._is_core_information_word(word):
                    continue
                lemma = str(word.get("lemma", "") or "").strip()
                if not lemma or lemma in _CONCEPT_REPETITION_EXCLUDED_LEMMAS:
                    continue
                item_type = ParagraphScorer._core_item_type(word)
                key = (lemma, item_type)
                counts[key] += 1
                sentence_ids[key].add(sentence_id)
                difficulties[key].append(ParagraphScorer._safe_difficulty(word))

        raw = 0.0
        repeated_count = 0
        for key, count in counts.items():
            if count <= 1:
                continue
            repeated_count += 1
            difficulty = max(difficulties[key]) if difficulties[key] else 0.30
            spread = min(1.6, 1.0 + 0.2 * (len(sentence_ids[key]) - 1))
            pos_weight = ParagraphScorer._concept_pos_weight(key[1])
            raw += (count - 1) * difficulty * spread * pos_weight

        score = min(1.0, raw / _CONCEPT_REPETITION_FULL_SCORE_AT)
        return {
            "repeated_core_content_count": repeated_count,
            "concept_repetition_raw": round(raw, 4),
            "concept_repetition_full_score_at": _CONCEPT_REPETITION_FULL_SCORE_AT,
            "concept_repetition": round(score, 4),
        }

    def score(self, paragraph: str | None) -> dict[str, Any]:
        text = str(paragraph or "")
        sentences = self.split_sentences(text)
        sentence_results = [self._sentence_scorer.score(sentence) for sentence in sentences]
        sentence_scores = [float(result.get("score_0_1", 0.0)) for result in sentence_results]

        aggregate = self._sentence_aggregate(sentence_scores)
        density = self._information_density(sentence_results)
        repetition = self._concept_repetition(sentence_results)

        score_0_1 = (
            0.85 * float(aggregate["sentence_aggregate"])
            + 0.15 * float(density["information_density"])
            + 0.10 * float(repetition["concept_repetition"])
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
                **density,
                **repetition,
                "paragraph_weights": {
                    "sentence_aggregate": 0.85,
                    "information_density": 0.15,
                    "concept_repetition_bonus": 0.10,
                },
            },
        }
