"""Shared logical-expression and clause-boundary matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .morph import base_sejong_tag, normalize_morph_form


LOGICAL_MARKERS: dict[str, float] = {
    "즉": 1.0, "곧": 0.8, "다시 말해": 1.0, "다시 말하면": 1.0,
    "말하자면": 0.8, "예컨대": 0.8, "예를 들어": 0.8, "따라서": 1.0,
    "그러므로": 1.0, "그렇기 때문에": 1.0, "그 때문에": 0.9,
    "그 결과": 0.9, "결과적으로": 0.9, "이로 인해": 0.9,
    "이 때문에": 0.9, "왜냐하면": 1.0, "그러나": 1.0, "하지만": 1.0,
    "그렇지만": 1.0, "반면": 0.9, "반대로": 0.9, "오히려": 0.8,
    "그럼에도": 0.9, "그럼에도 불구하고": 1.0, "비록": 0.8, "물론": 0.7,
    "만약": 1.0, "만일": 1.0, "가령": 0.8, "또한": 0.7, "더불어": 0.7,
    "아울러": 0.7, "나아가": 0.8, "게다가": 0.7, "한편": 0.8,
    "동시에": 0.7, "결국": 0.9, "요컨대": 1.0, "종합하면": 1.0,
    "정리하면": 0.9, "결론적으로": 1.0, "뿐 아니라": 0.8,
    "뿐만 아니라": 0.9, "아니라": 0.5,
}

STRONG_LOGICAL_ENDINGS: dict[str, float] = {
    "므로": 1.0, "으므로": 1.0, "기에": 0.9, "때문에": 1.0,
    "면": 0.8, "으면": 0.8, "다면": 1.0, "ㄴ다면": 1.0, "는다면": 1.0,
    "라면": 1.0, "거든": 0.8, "지만": 1.0, "으나": 0.9, "더라도": 1.0,
    "아도": 0.9, "어도": 0.9, "을지라도": 1.0, "려고": 0.7,
    "으려고": 0.7, "도록": 0.8, "는데": 0.6, "은데": 0.6, "ㄴ데": 0.6,
}

QUOTE_EC = {
    "라고", "이라고", "다고", "ㄴ다고", "는다고", "냐고", "느냐고", "자고",
}
CONDITIONAL_EC = {"면", "으면", "다면", "ㄴ다면", "는다면", "라면"}
COORDINATE_EC = {"고", "며", "으며", "거나", "든지"}


@dataclass(frozen=True)
class PatternMatch:
    kind: str
    label: str
    weight: float
    start: int
    end: int
    token_start: int
    token_end: int


class PatternMatcher:
    @staticmethod
    def _tag(token: Any) -> str:
        return base_sejong_tag(getattr(token, "tag", ""))

    @staticmethod
    def _form(token: Any) -> str:
        return normalize_morph_form(
            getattr(token, "surface", "") or getattr(token, "lemma", "")
        )

    @staticmethod
    def _token_range_for_chars(tokens: list[Any], start: int, end: int) -> tuple[int, int]:
        overlaps = [
            i for i, token in enumerate(tokens)
            if int(getattr(token, "end", 0)) > start and int(getattr(token, "start", 0)) < end
        ]
        if not overlaps:
            return 0, 0
        return overlaps[0], overlaps[-1] + 1

    @staticmethod
    def _longest_non_overlapping(matches: list[PatternMatch]) -> list[PatternMatch]:
        selected: list[PatternMatch] = []
        for match in sorted(matches, key=lambda item: (-(item.end - item.start), item.start)):
            if any(match.start < current.end and current.start < match.end for current in selected):
                continue
            selected.append(match)
        return sorted(selected, key=lambda item: item.start)

    def match_logical_markers(self, sentence: str, tokens: list[Any]) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        for label, weight in LOGICAL_MARKERS.items():
            start = 0
            while True:
                start = sentence.find(label, start)
                if start < 0:
                    break
                end = start + len(label)
                token_start, token_end = self._token_range_for_chars(tokens, start, end)
                if (
                    token_end <= token_start
                    or int(getattr(tokens[token_start], "start", -1)) != start
                    or int(getattr(tokens[token_end - 1], "end", -1)) != end
                ):
                    start = end
                    continue
                matches.append(PatternMatch(
                    "logical_marker", label, weight, start, end, token_start, token_end,
                ))
                start = end
        return self._longest_non_overlapping(matches)

    def match_strong_endings(self, tokens: list[Any]) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        for i, token in enumerate(tokens):
            tag = self._tag(token)
            form = self._form(token)
            if tag == "EC" and form in STRONG_LOGICAL_ENDINGS:
                matches.append(PatternMatch(
                    "strong_ending", form, STRONG_LOGICAL_ENDINGS[form],
                    int(getattr(token, "start", 0)), int(getattr(token, "end", 0)), i, i + 1,
                ))
            if i + 1 >= len(tokens):
                continue
            next_token = tokens[i + 1]
            next_tag = self._tag(next_token)
            if tag == "ETN" and form == "기" and next_tag == "JKB" and self._form(next_token) == "에":
                matches.append(PatternMatch(
                    "strong_ending", "기에", STRONG_LOGICAL_ENDINGS["기에"],
                    int(getattr(token, "start", 0)), int(getattr(next_token, "end", 0)), i, i + 2,
                ))
            if tag == "NNB" and form == "때문" and next_tag == "JKB" and self._form(next_token) == "에":
                matches.append(PatternMatch(
                    "strong_ending", "때문에", STRONG_LOGICAL_ENDINGS["때문에"],
                    int(getattr(token, "start", 0)), int(getattr(next_token, "end", 0)), i, i + 2,
                ))
        return self._longest_non_overlapping(matches)

    def match_boundaries(self, tokens: list[Any]) -> list[PatternMatch]:
        matches: list[PatternMatch] = []
        for i, token in enumerate(tokens):
            tag = self._tag(token)
            kind = ""
            if i + 1 < len(tokens):
                next_token = tokens[i + 1]
                next_tag = self._tag(next_token)
                if (
                    (tag == "ETN" and self._form(token) == "기")
                    or (tag == "NNB" and self._form(token) == "때문")
                ) and next_tag == "JKB" and self._form(next_token) == "에":
                    matches.append(PatternMatch(
                        "boundary_subordinate", self._form(token) + self._form(next_token), 0.0,
                        int(getattr(token, "start", 0)), int(getattr(next_token, "end", 0)), i, i + 2,
                    ))
                    continue
            if tag in {"SP", "SF", "SE"} or tag.startswith("SS"):
                kind = "punct"
            elif tag in {"ETM", "ETN"}:
                if i + 2 < len(tokens):
                    next1 = self._tag(tokens[i + 1])
                    next2 = self._tag(tokens[i + 2])
                    if next1 in {"NNB", "NNG"} and next2 in {"JX", "JKS", "JKO", "JKC"}:
                        kind = "nominal"
            elif tag == "EC":
                j = i + 1
                while j < len(tokens) and self._tag(tokens[j]) in {"JX", "JKO", "JKC"}:
                    j += 1
                if j < len(tokens) and self._tag(tokens[j]) == "VX":
                    kind = "aux"
                else:
                    form = self._form(token)
                    if form in QUOTE_EC:
                        kind = "quote"
                    elif form in CONDITIONAL_EC:
                        kind = "conditional"
                    elif form in COORDINATE_EC:
                        kind = "coordinate"
                    else:
                        kind = "subordinate"
            if kind:
                matches.append(PatternMatch(
                    f"boundary_{kind}", self._form(token), 0.0,
                    int(getattr(token, "start", 0)), int(getattr(token, "end", 0)), i, i + 1,
                ))
        return matches


__all__ = [
    "LOGICAL_MARKERS", "STRONG_LOGICAL_ENDINGS", "QUOTE_EC", "CONDITIONAL_EC",
    "COORDINATE_EC", "PatternMatch", "PatternMatcher",
]
