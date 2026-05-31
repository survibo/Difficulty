from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

try:
    import kiwipiepy  # noqa: F401
    HAS_KIWI = True
except ImportError:
    HAS_KIWI = False


def _make_lexicon_csv(rows: list[tuple[int, str, float, str]]) -> str:
    lines = ["entry_id,lemma,difficulty,pos"]
    for entry_id, lemma, difficulty, pos in rows:
        lines.append(f"{entry_id},{lemma},{difficulty},{pos}")
    return "\n".join(lines)


@unittest.skipIf(not HAS_KIWI, "kiwipiepy is not installed")
class SentenceScorerTest(unittest.TestCase):

    def setUp(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".csv", prefix="pipe_test_", text=True)
        os.close(fd)
        self._tmp_path = path

        rows = [
            (1, "문장", 0.200, "명사"),
            (2, "분석", 0.400, "명사"),
            (3, "쉽다", 0.000, "형용사"),
            (4, "어렵다", 0.800, "형용사"),
            (5, "매우", 0.100, "부사"),
        ]
        Path(path).write_text(_make_lexicon_csv(rows), encoding="utf-8")

        from sentdiff.pipeline import SentenceScorer
        from sentdiff.lexical import LexiconConfig

        self.scorer = SentenceScorer(
            LexiconConfig(lexicon_path=path, aggregation="min")
        )

    def tearDown(self) -> None:
        try:
            Path(self._tmp_path).unlink(missing_ok=True)
        except PermissionError:
            pass

    # -----------------------------------------------------------------

    def test_empty_sentence(self) -> None:
        result = self.scorer.score("")
        self.assertEqual(result["sentence"], "")
        self.assertEqual(result["score_0_1"], 0.0)
        self.assertEqual(result["content_token_count"], 0)
        self.assertEqual(result["unknown_token_count"], 0)

    def test_none_sentence(self) -> None:
        result = self.scorer.score(None)
        self.assertEqual(result["sentence"], "")
        self.assertEqual(result["score_0_1"], 0.0)

    def test_whitespace_sentence(self) -> None:
        result = self.scorer.score("  ")
        self.assertEqual(result["sentence"], "  ")
        self.assertEqual(result["score_0_1"], 0.0)
        self.assertEqual(result["content_token_count"], 0)

    def test_output_keys(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        expected_keys = {
            "sentence",
            "score_0_1",
            "score_10",
            "lexical_score_0_1",
            "lexical_score_10",
            "structure_score_0_1",
            "structure_score_10",
            "negation_score_0_1",
            "negation_score_10",
            "negation_detail",
            "content_token_count",
            "content_token_count_capped",
            "unknown_token_count",
            "scored_words",
            "score_parts",
            "structure_parts",
            "lexical_weight",
            "structure_weight",
            "negation_bonus_coefficient",
            "reliability",
        }
        self.assertEqual(set(result.keys()), expected_keys)

    def test_score_10_consistency(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        self.assertEqual(result["score_10"], round(result["score_0_1"] * 10, 2))

    def test_score_composition(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        expected = (
            0.5 * result["lexical_score_0_1"]
            + 0.5 * result["structure_score_0_1"]
            + 0.2 * result["negation_score_0_1"]
        )
        self.assertAlmostEqual(result["score_0_1"], min(1.0, expected), places=4)

    def test_structure_parts_contains_length_score(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        self.assertIn("length_score", result["structure_parts"])
        self.assertIn("structure_score_0_1", result)

    def test_content_and_unknown_counts_are_integers(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        self.assertIsInstance(result["content_token_count"], int)
        self.assertIsInstance(result["unknown_token_count"], int)
        self.assertGreaterEqual(result["content_token_count"], 0)
        self.assertGreaterEqual(result["unknown_token_count"], 0)

    def test_scored_words_structure(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        for word in result["scored_words"]:
            self.assertIn("surface", word)
            self.assertIn("lemma", word)
            self.assertIn("pos", word)
            self.assertIn("difficulty", word)
            self.assertIn("match_method", word)
            self.assertIn("matched_entry_id", word)

    def test_known_words_get_exact_match(self) -> None:
        result = self.scorer.score("문장")
        self.assertGreater(result["content_token_count"], 0)
        for word in result["scored_words"]:
            if word["lemma"] == "문장":
                self.assertEqual(word["match_method"], "exact")
                self.assertAlmostEqual(word["difficulty"], 0.200)

    def test_weights_sum_to_one(self) -> None:
        result = self.scorer.score("문장을 분석한다.")
        self.assertEqual(result["lexical_weight"], 5.0)
        self.assertEqual(result["structure_weight"], 5.0)
        self.assertEqual(result["negation_bonus_coefficient"], 0.2)


if __name__ == "__main__":
    unittest.main()
