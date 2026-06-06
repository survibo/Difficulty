"""Lexicon-aware lexical unit resolution over Kiwi morph tokens."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable

from .morph import base_sejong_tag, normalize_morph_form


@dataclass(frozen=True)
class LexicalUnit:
    surface: str
    lemma: str
    pos: str
    start: int
    end: int
    token_start: int
    token_end: int
    tags: tuple[str, ...]
    head_tag: str
    difficulty: float
    match_method: str
    matched_entry_id: int


@dataclass(frozen=True)
class _Candidate:
    unit: LexicalUnit
    covered_content: int
    known_content: int
    full_known: int
    unknown: int
    span_tokens: int


class LexicalUnitResolver:
    """Choose a non-overlapping lexical segmentation with whole-headword priority."""

    _MAX_TOKEN_SPAN = 8
    _DERIVATIONAL_TAGS = {"XSN", "XSM", "XSV", "XSA"}
    _ENDING_TAGS = {"EP", "EF"}

    def __init__(self, lookup: Callable[[str, str, str], Any]) -> None:
        self._lookup = lookup

    @staticmethod
    def _surface(sentence: str, tokens: list[Any], start: int, end: int) -> str:
        char_start = int(getattr(tokens[start], "start", 0))
        char_end = int(getattr(tokens[end - 1], "end", char_start))
        source = sentence[char_start:char_end].strip()
        if source:
            return source
        return "".join(str(getattr(token, "surface", "") or "") for token in tokens[start:end])

    @staticmethod
    def _has_internal_space(sentence: str, tokens: list[Any], start: int, end: int) -> bool:
        for i in range(start, end - 1):
            left = int(getattr(tokens[i], "end", 0))
            right = int(getattr(tokens[i + 1], "start", left))
            if any(ch.isspace() for ch in sentence[left:right]):
                return True
        return False

    @staticmethod
    def _candidate_pos(tags: tuple[str, ...], fallback_pos: str) -> list[str]:
        if "XSA" in tags:
            preferred = "형용사"
        elif "XSV" in tags:
            preferred = "동사"
        elif "XSM" in tags:
            preferred = "부사"
        elif "XSN" in tags or all(tag.startswith("N") for tag in tags):
            preferred = "명사"
        else:
            preferred = fallback_pos
        return list(dict.fromkeys([preferred, fallback_pos, "명사", "어근"]))

    @classmethod
    def _candidate_lemmas(cls, surface: str, tokens: list[Any], start: int, end: int) -> list[str]:
        span = tokens[start:end]
        surfaces = [normalize_morph_form(getattr(token, "surface", "")) for token in span]
        lemmas = [normalize_morph_form(getattr(token, "lemma", "")) for token in span]
        tags = [base_sejong_tag(getattr(token, "tag", "")) for token in span]

        candidates = [normalize_morph_form(surface), "".join(surfaces)]

        derivational_index = next(
            (i for i, tag in enumerate(tags) if tag in {"XSV", "XSA"}),
            None,
        )
        if derivational_index is not None:
            stem = "".join(surfaces[:derivational_index + 1])
            candidates.append(stem + "다")

        non_content_tags = [
            tag for token, tag in zip(span, tags)
            if not bool(getattr(token, "is_content", False))
        ]
        if (
            sum(bool(getattr(token, "is_content", False)) for token in span) == 1
            and all(tag in cls._ENDING_TAGS for tag in non_content_tags)
        ):
            content_token = next(token for token in span if bool(getattr(token, "is_content", False)))
            candidates.append(normalize_morph_form(getattr(content_token, "lemma", "")))

        content_and_suffix = [
            surfaces[i]
            for i, tag in enumerate(tags)
            if bool(getattr(span[i], "is_content", False)) or tag in cls._DERIVATIONAL_TAGS
        ]
        if content_and_suffix:
            candidates.append("".join(content_and_suffix))

        if len(span) == 1:
            candidates.extend(lemmas)

        return [value for value in dict.fromkeys(candidates) if value]

    def _known_span_candidate(
        self, sentence: str, tokens: list[Any], start: int, end: int,
    ) -> _Candidate | None:
        if end - start <= 1 or self._has_internal_space(sentence, tokens, start, end):
            return None

        span = tokens[start:end]
        tags = tuple(base_sejong_tag(getattr(token, "tag", "")) for token in span)
        content_count = sum(bool(getattr(token, "is_content", False)) for token in span)
        if content_count == 0:
            return None

        allowed = all(
            bool(getattr(token, "is_content", False))
            or tag in self._DERIVATIONAL_TAGS
            or tag in self._ENDING_TAGS
            for token, tag in zip(span, tags)
        )
        if not allowed:
            return None

        surface = self._surface(sentence, tokens, start, end)
        fallback_pos = str(getattr(next(
            (token for token in reversed(span) if bool(getattr(token, "is_content", False))),
            span[0],
        ), "pos", "") or "")

        for lemma in self._candidate_lemmas(surface, tokens, start, end):
            for pos in self._candidate_pos(tags, fallback_pos):
                match = self._lookup(lemma, pos, surface)
                if match.match_method not in {"exact", "lemma_only"}:
                    continue
                head_tag = next(
                    (tag for tag in reversed(tags) if tag in {"VV", "VA", "XSV", "XSA", "XSM", "XSN"}),
                    next((tag for tag in reversed(tags) if tag.startswith("N") or tag == "XR"), tags[-1]),
                )
                head_tag = {
                    "XSV": "VV", "XSA": "VA", "XSM": "MAG", "XSN": "NNG",
                }.get(head_tag, head_tag)
                unit = LexicalUnit(
                    surface=surface,
                    lemma=lemma,
                    pos=pos,
                    start=int(getattr(span[0], "start", 0)),
                    end=int(getattr(span[-1], "end", 0)),
                    token_start=start,
                    token_end=end,
                    tags=tags,
                    head_tag=head_tag,
                    difficulty=float(match.difficulty),
                    match_method=f"span_{match.match_method}",
                    matched_entry_id=int(match.matched_entry_id),
                )
                return _Candidate(unit, content_count, content_count, 1, 0, end - start)
        return None

    def _single_candidate(self, token: Any, index: int) -> _Candidate | None:
        if not bool(getattr(token, "is_content", False)):
            return None
        surface = str(getattr(token, "surface", "") or "")
        lemma = str(getattr(token, "lemma", "") or "")
        pos = str(getattr(token, "pos", "") or "")
        tag = base_sejong_tag(getattr(token, "tag", ""))
        match = self._lookup(lemma, pos, surface)
        known = int(match.match_method != "unknown")
        unit = LexicalUnit(
            surface=surface,
            lemma=match.lemma,
            pos=match.pos,
            start=int(getattr(token, "start", 0)),
            end=int(getattr(token, "end", 0)),
            token_start=index,
            token_end=index + 1,
            tags=(tag,),
            head_tag=tag,
            difficulty=float(match.difficulty),
            match_method=match.match_method,
            matched_entry_id=int(match.matched_entry_id),
        )
        return _Candidate(unit, 1, known, 0, 1 - known, 1)

    def resolve(self, sentence: str, tokens: list[Any]) -> list[LexicalUnit]:
        candidates: dict[int, list[_Candidate]] = {}
        for start, token in enumerate(tokens):
            single = self._single_candidate(token, start)
            if single is not None:
                candidates.setdefault(start, []).append(single)
            max_end = min(len(tokens), start + self._MAX_TOKEN_SPAN)
            for end in range(start + 2, max_end + 1):
                candidate = self._known_span_candidate(sentence, tokens, start, end)
                if candidate is not None:
                    candidates.setdefault(start, []).append(candidate)

        @lru_cache(maxsize=None)
        def choose(index: int) -> tuple[tuple[int, int, int, int, int, int], tuple[LexicalUnit, ...]]:
            if index >= len(tokens):
                return (0, 0, 0, 0, 0, 0), ()

            best_score, best_units = choose(index + 1)
            for candidate in candidates.get(index, []):
                tail_score, tail_units = choose(candidate.unit.token_end)
                score = (
                    candidate.known_content + tail_score[0],
                    candidate.covered_content + tail_score[1],
                    candidate.full_known + tail_score[2],
                    candidate.span_tokens + tail_score[3],
                    -candidate.unknown + tail_score[4],
                    -1 + tail_score[5],
                )
                if score > best_score:
                    best_score = score
                    best_units = (candidate.unit,) + tail_units
            return best_score, best_units

        return list(choose(0)[1])


__all__ = ["LexicalUnit", "LexicalUnitResolver"]
