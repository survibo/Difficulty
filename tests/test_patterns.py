from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.morph import MorphToken  # noqa: E402
from sentdiff.patterns import PatternMatcher  # noqa: E402


def _make_token(
    surface: str,
    tag: str,
    start: int,
    end: int,
    *,
    lemma: str | None = None,
    is_content: bool = False,
) -> MorphToken:
    return MorphToken(
        surface=surface,
        lemma=lemma or surface,
        tag=tag,
        pos=tag,
        start=start,
        end=end,
        is_content=is_content,
    )


class PatternMatcherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = PatternMatcher()

    def test_logical_markers_select_longest_non_overlapping_phrase(self) -> None:
        sentence = "문제다. 그럼에도 불구하고 간다."
        tokens = [
            _make_token("문제", "NNG", 0, 2, is_content=True),
            _make_token("그럼에도", "MAG", 5, 9),
            _make_token("불구하고", "EC", 10, 14),
            _make_token("간다", "VV", 15, 17, is_content=True),
        ]

        matches = self.matcher.match_logical_markers(sentence, tokens)

        self.assertEqual([match.label for match in matches], ["그럼에도 불구하고"])
        self.assertEqual(matches[0].weight, 1.0)
        self.assertEqual((matches[0].token_start, matches[0].token_end), (1, 3))

    def test_strong_endings_match_etn_jkb_and_nnb_jkb_sequences(self) -> None:
        tokens = [
            _make_token("기", "ETN", 0, 1),
            _make_token("에", "JKB", 1, 2),
            _make_token("때문", "NNB", 3, 5),
            _make_token("에", "JKB", 5, 6),
        ]

        matches = self.matcher.match_strong_endings(tokens)

        self.assertEqual([match.label for match in matches], ["기에", "때문에"])
        self.assertEqual([match.weight for match in matches], [0.9, 1.0])
        self.assertEqual(
            [(match.token_start, match.token_end) for match in matches],
            [(0, 2), (2, 4)],
        )

    def test_boundaries_normalize_final_consonant_quote_and_conditional_forms(self) -> None:
        tokens = [
            _make_token("ᆫ다고", "EC", 0, 3),
            _make_token("ᆫ다면", "EC", 4, 7),
        ]

        matches = self.matcher.match_boundaries(tokens)

        self.assertEqual(
            [(match.kind, match.label) for match in matches],
            [("boundary_quote", "ㄴ다고"), ("boundary_conditional", "ㄴ다면")],
        )

    def test_boundaries_classify_etn_jkb_and_nnb_jkb_as_subordinate_spans(self) -> None:
        tokens = [
            _make_token("기", "ETN", 0, 1),
            _make_token("에", "JKB", 1, 2),
            _make_token("때문", "NNB", 3, 5),
            _make_token("에", "JKB", 5, 6),
        ]

        matches = self.matcher.match_boundaries(tokens)

        self.assertEqual(
            [(match.kind, match.label, match.token_start, match.token_end) for match in matches],
            [
                ("boundary_subordinate", "기에", 0, 2),
                ("boundary_subordinate", "때문에", 2, 4),
            ],
        )


if __name__ == "__main__":
    unittest.main()
