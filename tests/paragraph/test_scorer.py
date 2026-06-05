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
        with self.assertRaisesRegex(ValueError, "4개 이상"):
            self.scorer.score("  ")

    def test_paragraph_requires_at_least_four_sentences(self) -> None:
        with self.assertRaisesRegex(ValueError, "4개 이상"):
            self.scorer.score("첫 문장이다. 둘째 문장이다. 셋째 문장이다.")

    def test_sentence_aggregate_uses_mean_top3_and_max(self) -> None:
        result = self.scorer.score("쉬운 문장이다. 쉬운 문장이다. 어렵다. 어렵다.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["sentence_mean"], 0.5)
        self.assertEqual(parts["sentence_top_3_mean"], 0.6)
        self.assertEqual(parts["sentence_max"], 0.8)
        self.assertEqual(parts["sentence_aggregate"], 0.6)

    def test_paragraph_weights(self) -> None:
        result = self.scorer.score("쉬운 문장이다. 쉬운 문장이다. 쉬운 문장이다. 쉬운 문장이다.")
        self.assertEqual(
            result["paragraph_parts"]["paragraph_weights"],
            {
                "sentence_aggregate": 0.85,
                "information_density": 0.15,
                "concept_repetition_bonus": 0.15,
            },
        )

    def test_paragraph_score_uses_sentence_density_and_concept_repetition(self) -> None:
        result = self.scorer.score("그러나 쉬운 문장이다. 쉬운 문장이다. 쉬운 문장이다. 쉬운 문장이다.")
        parts = result["paragraph_parts"]
        expected = (
            0.85 * parts["sentence_aggregate"]
            + 0.15 * parts["information_density"]
            + 0.15 * parts["concept_repetition"]
        )
        self.assertEqual(result["score_0_1"], round(expected, 4))

    def test_information_density_uses_unique_core_content_items(self) -> None:
        result = self.scorer.score("같은 단어. 같은 다른. 같은. 단어.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 3)
        self.assertEqual(parts["information_density_full_score_at"], 52)
        self.assertEqual(parts["information_density"], round(3 / 52, 4))

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

        result = ParagraphScorer(CoreTagSentenceScorer()).score("문장 하나. 문장 둘. 문장 셋. 문장 넷.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 3)
        self.assertEqual(parts["information_density_full_score_at"], 52)
        self.assertEqual(parts["information_density"], round(3 / 52, 4))

    def test_information_density_caps_at_sentence_count_times_thirteen(self) -> None:
        class DenseSentenceScorer:
            def score(self, sentence: str) -> dict:
                words = [
                    {"lemma": f"w{i}", "pos": "명사", "tag": "NNG"}
                    for i in range(60)
                ]
                return {
                    "sentence": sentence,
                    "score_0_1": 0.2,
                    "score_10": 2.0,
                    "scored_words_full": words,
                }

        result = ParagraphScorer(DenseSentenceScorer()).score("문장 하나. 문장 둘. 문장 셋. 문장 넷.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 60)
        self.assertEqual(parts["information_density_full_score_at"], 52)
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

        result = ParagraphScorer(PosSentenceScorer()).score("문장 하나. 문장 둘. 문장 셋. 문장 넷.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["unique_core_content_count"], 2)
        self.assertEqual(parts["information_density_full_score_at"], 52)
        self.assertEqual(parts["information_density"], round(2 / 52, 4))

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

        result = ParagraphScorer(RepeatedConceptSentenceScorer()).score("첫째 문장. 둘째 문장. 셋째 문장. 넷째 문장.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["repeated_core_content_count"], 1)
        self.assertEqual(parts["concept_repetition_full_score_at"], 10.0)
        self.assertEqual(parts["concept_repetition_raw"], 5.76)
        self.assertEqual(parts["concept_repetition"], 0.576)

    def test_concept_repetition_uses_minimum_difficulty_for_zero_difficulty_words(self) -> None:
        class EasyRepeatedConceptSentenceScorer:
            def score(self, sentence: str) -> dict:
                return {
                    "sentence": sentence,
                    "score_0_1": 0.2,
                    "score_10": 2.0,
                    "scored_words_full": [
                        {"lemma": "쉽다", "pos": "형용사", "tag": "VA", "difficulty": 0.0},
                    ],
                }

        result = ParagraphScorer(EasyRepeatedConceptSentenceScorer()).score("첫째 문장. 둘째 문장. 셋째 문장. 넷째 문장.")
        parts = result["paragraph_parts"]
        self.assertEqual(parts["repeated_core_content_count"], 1)
        self.assertEqual(parts["concept_repetition_raw"], 0.192)
        self.assertEqual(parts["concept_repetition"], 0.0192)


if __name__ == "__main__":
    unittest.main()
