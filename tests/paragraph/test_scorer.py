from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.paragraph import ParagraphScorer  # noqa: E402


class FakeSentenceScorer:
    def score(self, sentence: str) -> dict:
        score = 0.8 if "어렵" in sentence else 0.2
        words = [
            {"lemma": word.strip(".,!?。！？"), "surface": word, "match_method": "exact"}
            for word in sentence.split()
            if word.strip(".,!?。！？")
        ]
        return {
            "sentence": sentence,
            "score_0_1": score,
            "score_10": score * 10,
            "scored_words_full": words,
        }


class ParagraphScorerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = ParagraphScorer(FakeSentenceScorer())

    def test_split_sentences(self) -> None:
        self.assertEqual(
            ParagraphScorer.split_sentences("첫 문장이다. 둘째 문장이다? 셋째"),
            ["첫 문장이다.", "둘째 문장이다?", "셋째"],
        )

    def test_empty_paragraph(self) -> None:
        result = self.scorer.score("  ")
        self.assertEqual(result["score_0_1"], 0.0)
        self.assertEqual(result["sentence_count"], 0)
        self.assertEqual(result["paragraph_parts"]["information_density_full_score_at"], 0)

    def test_sentence_aggregate_uses_mean_top3_and_max(self) -> None:
        result = self.scorer.score("쉬운 문장이다. 쉬운 문장이다. 어렵다. 어렵다.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["sentence_mean"], 0.5)
        self.assertEqual(parts["sentence_top_3_mean"], 0.6)
        self.assertEqual(parts["sentence_max"], 0.8)
        self.assertEqual(parts["sentence_aggregate"], 0.6)

    def test_paragraph_weights(self) -> None:
        result = self.scorer.score("쉬운 문장이다.")
        self.assertEqual(
            result["paragraph_parts"]["paragraph_weights"],
            {
                "sentence_aggregate": 0.70,
                "information_density": 0.30,
            },
        )

    def test_paragraph_score_uses_sentence_and_density_only(self) -> None:
        result = self.scorer.score("그러나 쉬운 문장이다.")
        parts = result["paragraph_parts"]
        expected = 0.70 * parts["sentence_aggregate"] + 0.30 * parts["information_density"]
        self.assertEqual(result["score_0_1"], round(expected, 4))
        self.assertEqual(parts["discourse_marker_score"], 1.0)

    def test_initial_discourse_markers_count_for_paragraphs(self) -> None:
        result = self.scorer.score("그러나 쉬운 문장이다. 따라서 어려운 문장이다.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["discourse_marker_count"], 2)
        self.assertEqual(parts["discourse_marker_weighted"], 2.0)
        self.assertEqual(parts["discourse_marker_score"], 1.0)

    def test_discourse_marker_score_is_normalized_by_sentence_count(self) -> None:
        result = self.scorer.score("그러나 쉬운 문장이다. 쉬운 문장이다. 쉬운 문장이다. 쉬운 문장이다.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["sentence_mean"], 0.2)
        self.assertEqual(parts["discourse_marker_count"], 1)
        self.assertEqual(parts["discourse_marker_weighted"], 1.0)
        self.assertEqual(parts["discourse_marker_score"], 0.25)

    def test_information_density_uses_unique_lemmas(self) -> None:
        result = self.scorer.score("같은 단어. 같은 다른.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_content_lemma_count"], 3)
        self.assertEqual(parts["information_density_full_score_at"], 14)
        self.assertEqual(parts["information_density"], round(3 / 14, 4))

    def test_information_density_caps_at_sentence_count_times_seven(self) -> None:
        result = self.scorer.score("a b c d e f g h.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_content_lemma_count"], 8)
        self.assertEqual(parts["information_density_full_score_at"], 7)
        self.assertEqual(parts["information_density"], 1.0)


if __name__ == "__main__":
    unittest.main()
