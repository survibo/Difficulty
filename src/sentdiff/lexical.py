"""
lexical.py

MorphToken 리스트의 내용어를 lexicon_master.csv에 lookup해서
어휘 난도를 계산하고 문장 단위 lexical score를 반환한다.

Lookup 우선순위:
1. exact:           (lemma, pos)
2. base_exact:      (base, pos) → (base, "명사") → (base, "어근")
3. lemma_only:      lemma
4. base_lemma_only: base
5. unknown
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Optional

import pandas as pd

from .normalize import split_light_predicate_suffix


# ---------------------------------------------------------------------
# Tunable parameters
# ---------------------------------------------------------------------

_WEIGHT_MEAN_ALL: float = 0.30
_WEIGHT_MEAN_TOP_N: float = 0.40
_WEIGHT_MAX: float = 0.30
_TOP_N: int = 3


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class LexiconEntry:
    entry_id: int
    lemma: str
    pos: str
    difficulty: float


@dataclass(frozen=True)
class LexicalMatch:
    surface: str
    lemma: str
    pos: str
    difficulty: float
    match_method: str
    matched_entry_id: int = 0


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class LexiconConfig:
    lexicon_path: str | Path = "data/processed/lexicon_master.csv"
    unknown_difficulty: float = 0.30
    aggregation: str = "min"

    def __post_init__(self) -> None:
        if self.aggregation not in {"min", "median", "mean"}:
            raise ValueError(
                f"aggregation must be one of: min, median, mean (got {self.aggregation!r})"
            )
        if not 0.0 <= self.unknown_difficulty <= 1.0:
            raise ValueError(
                f"unknown_difficulty must be between 0.0 and 1.0 "
                f"(got {self.unknown_difficulty})"
            )


# ---------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------


class LexiconScorer:
    def __init__(self, config: LexiconConfig | None = None) -> None:
        self.config = config or LexiconConfig()

        self._exact_map: dict[tuple[str, str], list[LexiconEntry]] = {}
        self._lemma_map: dict[str, list[LexiconEntry]] = {}

        self._load_lexicon()

    # -----------------------------------------------------------------
    # Lexicon loading
    # -----------------------------------------------------------------

    @staticmethod
    def _split_pos_parts(pos: str) -> list[str]:
        parts = re.split(r"[/,;·]+", pos)
        return [p.strip() for p in parts if p.strip()]

    def _load_lexicon(self) -> None:
        path = Path(self.config.lexicon_path)

        if not path.exists():
            raise FileNotFoundError(
                f"lexicon file not found: {path}"
            )

        df = pd.read_csv(path, encoding="utf-8-sig")

        required = {"entry_id", "lemma", "difficulty", "pos"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(
                f"lexicon CSV missing required columns: {missing}"
            )

        for _, row in df.iterrows():
            entry = LexiconEntry(
                entry_id=int(row["entry_id"]),
                lemma=str(row["lemma"]),
                pos=str(row["pos"]),
                difficulty=float(row["difficulty"]),
            )

            pos_parts = self._split_pos_parts(entry.pos)
            for pos_part in pos_parts:
                key = (entry.lemma, pos_part)
                self._exact_map.setdefault(key, []).append(entry)

            self._lemma_map.setdefault(entry.lemma, []).append(entry)

    # -----------------------------------------------------------------
    # Aggregation
    # -----------------------------------------------------------------

    def _aggregate(self, entries: list[LexiconEntry]) -> tuple[float, int]:
        if not entries:
            return self.config.unknown_difficulty, 0

        agg = self.config.aggregation

        if agg == "min":
            best = min(entries, key=lambda e: e.difficulty)
            return best.difficulty, best.entry_id

        if agg == "median":
            sorted_entries = sorted(entries, key=lambda e: e.difficulty)
            mid = len(sorted_entries) // 2
            return sorted_entries[mid].difficulty, 0

        if agg == "mean":
            diffs = [e.difficulty for e in entries]
            return sum(diffs) / len(diffs), 0

        raise ValueError(f"unexpected aggregation: {agg!r}")

    # -----------------------------------------------------------------
    # Base lemma fallback helpers
    # -----------------------------------------------------------------

    def _has_nominal_root_pos(self, pos: str) -> bool:
        parts = self._split_pos_parts(pos)
        return bool({"명사", "어근"} & set(parts))

    def _base_exact_lookup(
        self, base: str, original_pos: str, surface: str, lemma: str
    ) -> Optional[LexicalMatch]:
        for candidate_pos in [original_pos, "명사", "어근"]:
            key = (base, candidate_pos)
            entries = self._exact_map.get(key)
            if entries:
                is_valid = any(
                    self._has_nominal_root_pos(e.pos) for e in entries
                )
                if is_valid:
                    diff, eid = self._aggregate(entries)
                    return LexicalMatch(
                        surface=surface,
                        lemma=lemma,
                        pos=original_pos,
                        difficulty=diff,
                        match_method="base_exact",
                        matched_entry_id=eid,
                    )
        return None

    def _base_lemma_only_lookup(
        self, base: str, surface: str, lemma: str, original_pos: str
    ) -> Optional[LexicalMatch]:
        entries = self._lemma_map.get(base)
        if not entries:
            return None

        valid = [e for e in entries if self._has_nominal_root_pos(e.pos)]
        if not valid:
            return None

        diff, eid = self._aggregate(valid)
        return LexicalMatch(
            surface=surface,
            lemma=lemma,
            pos=original_pos,
            difficulty=diff,
            match_method="base_lemma_only",
            matched_entry_id=eid,
        )

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def lookup(self, lemma: str, pos: str, surface: str = "") -> LexicalMatch:
        norm_lemma = lemma.strip()
        norm_pos = pos.strip()

        if not norm_lemma:
            return LexicalMatch(
                surface=surface,
                lemma=lemma,
                pos=pos,
                difficulty=self.config.unknown_difficulty,
                match_method="unknown",
            )

        # 1. exact
        exact_key = (norm_lemma, norm_pos)
        entries = self._exact_map.get(exact_key)
        if entries:
            diff, eid = self._aggregate(entries)
            return LexicalMatch(
                surface=surface,
                lemma=norm_lemma,
                pos=norm_pos,
                difficulty=diff,
                match_method="exact",
                matched_entry_id=eid,
            )

        # 2. base_exact
        split_result = split_light_predicate_suffix(norm_lemma)
        if split_result is not None:
            base, _suffix, _penalty = split_result
            if len(base) >= 2:
                match = self._base_exact_lookup(base, norm_pos, surface, norm_lemma)
                if match is not None:
                    return match

        # 3. lemma_only
        lemma_entries = self._lemma_map.get(norm_lemma)
        if lemma_entries:
            diff, eid = self._aggregate(lemma_entries)
            return LexicalMatch(
                surface=surface,
                lemma=norm_lemma,
                pos=norm_pos,
                difficulty=diff,
                match_method="lemma_only",
                matched_entry_id=eid,
            )

        # 4. base_lemma_only
        if split_result is not None:
            base, _suffix, _penalty = split_result
            if len(base) >= 2:
                match = self._base_lemma_only_lookup(base, surface, norm_lemma, norm_pos)
                if match is not None:
                    return match

        # 5. unknown
        return LexicalMatch(
            surface=surface,
            lemma=norm_lemma,
            pos=norm_pos,
            difficulty=self.config.unknown_difficulty,
            match_method="unknown",
        )

    def get_difficulty(self, lemma: str, pos: str) -> float:
        return self.lookup(lemma, pos).difficulty

    def score_tokens(self, tokens: list[Any]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []

        for token in tokens:
            is_content = getattr(token, "is_content", True)
            if not is_content:
                continue

            surface = getattr(token, "surface", "")
            lemma = getattr(token, "lemma", "")
            pos = getattr(token, "pos", "")

            match = self.lookup(lemma, pos, surface)
            result.append({
                "surface": match.surface,
                "lemma": match.lemma,
                "pos": match.pos,
                "difficulty": match.difficulty,
                "match_method": match.match_method,
                "matched_entry_id": match.matched_entry_id,
            })

        return result

    def compute_sentence_score(self, tokens: list[Any]) -> dict[str, Any]:
        scored = self.score_tokens(tokens)
        diffs = [item["difficulty"] for item in scored]

        if not diffs:
            return {
                "lexical_score_0_1": 0.0,
                "content_token_count": 0,
                "unknown_token_count": 0,
                "scored_words": [],
                "score_parts": {
                    "mean_all": 0.0,
                    "mean_top_n": 0.0,
                    "max": 0.0,
                },
            }

        mean_all = mean(diffs)
        top_n = sorted(diffs, reverse=True)[:_TOP_N]
        mean_top_n = mean(top_n) if top_n else 0.0
        max_val = max(diffs)

        raw_score = _WEIGHT_MEAN_ALL * mean_all + _WEIGHT_MEAN_TOP_N * mean_top_n + _WEIGHT_MAX * max_val
        raw_score = max(0.0, min(1.0, raw_score))
        lexical_score = round(raw_score, 4)

        unknown_count = sum(
            1 for s in scored if s["match_method"] == "unknown"
        )

        return {
            "lexical_score_0_1": lexical_score,
            "content_token_count": len(scored),
            "unknown_token_count": unknown_count,
            "scored_words": scored,
            "score_parts": {
                "mean_all": round(mean_all, 4),
                "mean_top_n": round(mean_top_n, 4),
                "max": round(max_val, 4),
            },
        }


# ---------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------


def score_sentence(
    analyzer: Any,
    scorer: LexiconScorer,
    sentence: str,
) -> dict[str, Any]:
    from .morph import KiwiMorphAnalyzer

    if isinstance(analyzer, KiwiMorphAnalyzer):
        tokens = analyzer.analyze(sentence)
    else:
        tokens = analyzer.analyze(sentence)

    return scorer.compute_sentence_score(tokens)


__all__ = [
    "LexiconEntry",
    "LexicalMatch",
    "LexiconConfig",
    "LexiconScorer",
    "score_sentence",
]
