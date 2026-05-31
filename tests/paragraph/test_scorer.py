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
            {"lemma": word.strip(".,!?。！？"), "pos": "명사", "surface": word, "match_method": "exact"}
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
                "sentence_aggregate": 0.80,
                "information_density": 0.10,
                "concept_repetition": 0.10,
            },
        )

    def test_paragraph_score_uses_sentence_density_and_concept_repetition(self) -> None:
        result = self.scorer.score("그러나 쉬운 문장이다.")
        parts = result["paragraph_parts"]
        expected = (
            0.80 * parts["sentence_aggregate"]
            + 0.10 * parts["information_density"]
            + 0.10 * parts["concept_repetition"]
        )
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

    def test_information_density_uses_unique_core_content_items(self) -> None:
        result = self.scorer.score("같은 단어. 같은 다른.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 3)
        self.assertEqual(parts["information_density_full_score_at"], 20)
        self.assertEqual(parts["information_density"], round(3 / 20, 4))

    def test_information_density_counts_only_core_content_tags(self) -> None:
        class CoreTagSentenceScorer:
            def score(self, sentence: str) -> dict:
                return {
                    "sentence": sentence,
                    "score_0_1": 0.2,
                    "score_10": 2.0,
                    "scored_words_full": [
                        {"lemma": "정책", "pos": "명사", "tag": "NNG"},
                        {"lemma": "그", "pos": "대명사", "tag": "NP"},
                        {"lemma": "매우", "pos": "부사", "tag": "MAG"},
                        {"lemma": "어렵다", "pos": "형용사", "tag": "VA"},
                        {"lemma": "구조", "pos": "어근", "tag": "XR"},
                        {"lemma": "수", "pos": "명사", "tag": "NNB"},
                    ],
                }

        result = ParagraphScorer(CoreTagSentenceScorer()).score("정책은 그 매우 어려운 구조일 수 있다.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 3)
        self.assertEqual(parts["information_density_full_score_at"], 10)
        self.assertEqual(parts["information_density"], round(3 / 10, 4))

    def test_information_density_caps_at_sentence_count_times_ten(self) -> None:
        result = self.scorer.score("a b c d e f g h i j k.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 11)
        self.assertEqual(parts["information_density_full_score_at"], 10)
        self.assertEqual(parts["information_density"], 1.0)

    def test_information_density_counts_same_lemma_different_pos(self) -> None:
        class PosSentenceScorer:
            def score(self, sentence: str) -> dict:
                return {
                    "sentence": sentence,
                    "score_0_1": 0.2,
                    "score_10": 2.0,
                    "scored_words_full": [
                        {"lemma": "말", "pos": "명사", "surface": "말", "match_method": "exact"},
                        {"lemma": "말", "pos": "동사", "surface": "말", "match_method": "exact"},
                    ],
                }

        result = ParagraphScorer(PosSentenceScorer()).score("말 말.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 2)
        self.assertEqual(parts["information_density_full_score_at"], 10)
        self.assertEqual(parts["information_density"], round(2 / 10, 4))

    def test_concept_repetition_uses_repeated_core_words_with_difficulty_and_spread(self) -> None:
        class RepeatedConceptSentenceScorer:
            def score(self, sentence: str) -> dict:
                words = [{"lemma": "변증법", "pos": "명사", "tag": "NNG", "difficulty": 0.9}]
                if "둘째" in sentence:
                    words.append({"lemma": "변증법", "pos": "명사", "tag": "NNG", "difficulty": 0.9})
                    words.append({"lemma": "수", "pos": "명사", "tag": "NNB", "difficulty": 0.9})
                return {
                    "sentence": sentence,
                    "score_0_1": 0.2,
                    "score_10": 2.0,
                    "scored_words_full": words,
                }

        result = ParagraphScorer(RepeatedConceptSentenceScorer()).score("첫째 문장. 둘째 문장.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["repeated_core_content_count"], 1)
        self.assertEqual(parts["concept_repetition_full_score_at"], 10.0)
        self.assertEqual(parts["concept_repetition_raw"], 2.16)
        self.assertEqual(parts["concept_repetition"], 0.216)


if __name__ == "__main__":
    unittest.main()
