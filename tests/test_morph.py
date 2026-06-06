from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.morph import (  # noqa: E402
    KiwiMorphAnalyzer,
    MorphToken,
    base_sejong_tag,
    is_content_tag,
    is_excluded_lexical_tag,
    sejong_tag_to_pos,
    token_to_lemma_candidate,
)


class MorphHelperTests(unittest.TestCase):
    def test_base_sejong_tag_removes_kiwi_suffixes(self) -> None:
        self.assertEqual(base_sejong_tag("VA-I"), "VA")
        self.assertEqual(base_sejong_tag("VV-R"), "VV")
        self.assertEqual(base_sejong_tag("NNG"), "NNG")

    def test_sejong_tag_to_pos_maps_major_tags(self) -> None:
        cases = {
            "NNG": "명사",
            "NNP": "명사",
            "NP": "대명사",
            "NR": "수사",
            "VV": "동사",
            "VA": "형용사",
            "VX": "보조용언",
            "XSV": "접사",
            "XSA": "접사",
            "MAG": "부사",
            "XR": "어근",
            "SL": "외국어",
            "SH": "한자",
            "JKO": "조사",
            "ETM": "어미",
            "SF": "기호",
        }

        for tag, expected in cases.items():
            with self.subTest(tag=tag):
                self.assertEqual(sejong_tag_to_pos(tag), expected)

    def test_token_to_lemma_candidate_appends_da_for_predicates(self) -> None:
        self.assertEqual(token_to_lemma_candidate("먹", "VV"), "먹다")
        self.assertEqual(token_to_lemma_candidate("좋", "VA"), "좋다")
        self.assertEqual(token_to_lemma_candidate("가다", "VV"), "가다")
        self.assertEqual(token_to_lemma_candidate("문장", "NNG"), "문장")
        self.assertEqual(token_to_lemma_candidate("그렇", "VA-I"), "그렇다")
        self.assertEqual(token_to_lemma_candidate("짓", "VV-R"), "짓다")

    def test_sejong_tag_to_pos_handles_kiwi_suffixes(self) -> None:
        self.assertEqual(sejong_tag_to_pos("VA-I"), "형용사")
        self.assertEqual(sejong_tag_to_pos("VV-R"), "동사")
        self.assertEqual(sejong_tag_to_pos("EC-R"), "어미")

    def test_excluded_lexical_tags(self) -> None:
        for tag in ["VX", "XSV", "XSA", "XPN", "XSN", "JKO", "ETM", "SF"]:
            with self.subTest(tag=tag):
                self.assertTrue(is_excluded_lexical_tag(tag))

        for tag in ["NNG", "VV", "VA", "MAG", "XR", "SL", "SH"]:
            with self.subTest(tag=tag):
                self.assertFalse(is_excluded_lexical_tag(tag))

    def test_content_tag_policy(self) -> None:
        included = ["NNG", "NNP", "NP", "NR", "VV", "VA", "MAG", "XR", "SL", "SH"]
        excluded = ["NNB", "VX", "XSV", "XSA", "JKO", "ETM", "SF", "SN", "MM", "MAJ"]

        for tag in included:
            with self.subTest(f"included {tag}"):
                self.assertTrue(is_content_tag(tag))

        for tag in excluded:
            with self.subTest(f"excluded {tag}"):
                self.assertFalse(is_content_tag(tag))

    def test_content_tag_handles_irregular_suffix(self) -> None:
        for suffix in ["I", "R"]:
            for base in ["VV", "VA"]:
                with self.subTest(tag=f"{base}-{suffix}"):
                    self.assertTrue(is_content_tag(f"{base}-{suffix}"))
            self.assertFalse(is_content_tag(f"VX-{suffix}"))

    def test_excluded_lexical_tag_handles_irregular_suffix(self) -> None:
        for suffix in ["I", "R"]:
            self.assertTrue(is_excluded_lexical_tag(f"VX-{suffix}"))
            for base in ["VV", "VA"]:
                with self.subTest(tag=f"{base}-{suffix}"):
                    self.assertFalse(is_excluded_lexical_tag(f"{base}-{suffix}"))


class KiwiMorphAnalyzerTests(unittest.TestCase):
    def test_empty_sentence_returns_empty_list(self) -> None:
        analyzer = KiwiMorphAnalyzer()
        self.assertEqual(analyzer.analyze(""), [])
        self.assertEqual(analyzer.analyze("   "), [])

    def test_analyze_returns_morph_tokens(self) -> None:
        analyzer = KiwiMorphAnalyzer()
        tokens = analyzer.analyze("가공된 문장을 분석한다.")

        self.assertTrue(tokens)
        self.assertTrue(all(isinstance(token, MorphToken) for token in tokens))
        self.assertIn("가공", [token.surface for token in tokens])
        self.assertTrue(all(token.end >= token.start for token in tokens))

    def test_content_tokens_exclude_functional_markers(self) -> None:
        analyzer = KiwiMorphAnalyzer()
        tokens = analyzer.content_tokens("가공된 문장을 분석한다.")

        self.assertTrue(tokens)
        self.assertTrue(all(token.is_content for token in tokens))
        self.assertFalse(any(token.tag.startswith("J") for token in tokens))
        self.assertFalse(any(token.tag.startswith("E") for token in tokens))
        self.assertFalse(any(token.tag.startswith("S") for token in tokens))
        self.assertFalse(any(token.tag in {"VX", "XSV", "XSA"} for token in tokens))
        self.assertIn("가공", [token.surface for token in tokens])
        self.assertIn("문장", [token.surface for token in tokens])
        self.assertIn("분석", [token.surface for token in tokens])

    def test_polysemy_ignores_kiwi_tag_suffix_variants(self) -> None:
        class Token:
            def __init__(self, tag: str) -> None:
                self.tag = tag

        class FakeKiwi:
            def analyze(self, surface: str, top_n: int = 5):
                return [
                    ([Token("VA")], 0.0),
                    ([Token("VA-I")], -1.0),
                    ([Token("VA-R")], -2.0),
                ]

        analyzer = KiwiMorphAnalyzer(kiwi=FakeKiwi())
        self.assertEqual(analyzer.get_polysemy("그렇다"), 1)


if __name__ == "__main__":
    unittest.main()
