from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.lexical import (  # noqa: E402
    LexicalMatch,
    LexiconConfig,
    LexiconEntry,
    LexiconScorer,
    _TOP_N,
    _lexical_weights,
)
from sentdiff.morph import MorphToken  # noqa: E402


def _make_token(
    surface: str,
    lemma: str,
    pos: str,
    tag: str = "",
    is_content: bool = True,
    start: int = 0,
    end: int = 0,
) -> MorphToken:
    return MorphToken(
        surface=surface,
        lemma=lemma,
        tag=tag or pos,
        pos=pos,
        start=start,
        end=end or len(surface),
        is_content=is_content,
    )


def _make_lexicon_csv(rows: list[tuple[int, str, float, str]]) -> str:
    lines = ["entry_id,lemma,difficulty,pos"]
    for entry_id, lemma, difficulty, pos in rows:
        lines.append(f"{entry_id},{lemma},{difficulty},{pos}")
    return "\n".join(lines)


class LexiconScorerTest(unittest.TestCase):
    """LexiconScorer lookup, scoring, filtering tests."""

    def setUp(self) -> None:
        fd, path = tempfile.mkstemp(suffix=".csv", prefix="lex_test_", text=True)
        os.close(fd)
        self._tmp_path = path

        rows = [
            (1, "가공", 0.494, "명사"),
            (2, "가공", 0.900, "어근"),
            (3, "문장", 0.200, "명사"),
            (4, "분석", 0.400, "명사"),
            (5, "훈련", 0.300, "명사"),
            (6, "사용", 0.200, "명사"),
            (7, "쉽다", 0.000, "형용사"),
            (8, "어렵다", 0.800, "형용사"),
            (9, "빠르다", 0.250, "형용사"),
            (10, "매우", 0.100, "부사"),
            (11, "그", 0.000, "관형사"),
            (12, "가까이", 0.000, "부사/명사"),
            (13, "가까이", 0.219, "부사"),
            (14, "가까이", 0.243, "명사"),
            (15, "XR어근", 0.500, "어근"),
        ]
        csv_content = _make_lexicon_csv(rows)
        Path(path).write_text(csv_content, encoding="utf-8")

        self.scorer = LexiconScorer(
            LexiconConfig(lexicon_path=path, aggregation="min")
        )

    def tearDown(self) -> None:
        try:
            Path(self._tmp_path).unlink(missing_ok=True)
        except PermissionError:
            pass

    # -----------------------------------------------------------------
    # lookup: exact
    # -----------------------------------------------------------------

    def test_lookup_exact(self) -> None:
        match = self.scorer.lookup("문장", "명사")
        self.assertEqual(match.match_method, "exact")
        self.assertAlmostEqual(match.difficulty, 0.200)
        self.assertEqual(match.matched_entry_id, 3)

    def test_lookup_unknown(self) -> None:
        match = self.scorer.lookup("없는단어", "명사")
        self.assertEqual(match.match_method, "unknown")
        self.assertAlmostEqual(match.difficulty, 0.30)

    def test_lookup_empty_lemma_unknown(self) -> None:
        match = self.scorer.lookup("", "명사")
        self.assertEqual(match.match_method, "unknown")

    # -----------------------------------------------------------------
    # lookup: compound POS exact
    # -----------------------------------------------------------------

    def test_lookup_compound_pos_exact_adverb(self) -> None:
        match = self.scorer.lookup("가까이", "부사")
        self.assertEqual(match.match_method, "exact")
        self.assertAlmostEqual(match.difficulty, 0.000)

    def test_lookup_compound_pos_exact_noun(self) -> None:
        match = self.scorer.lookup("가까이", "명사")
        self.assertEqual(match.match_method, "exact")
        self.assertAlmostEqual(match.difficulty, 0.000)

    # -----------------------------------------------------------------
    # lookup: multiple candidates → min aggregation
    # -----------------------------------------------------------------

    def test_multiple_candidates_min_aggregation(self) -> None:
        match = self.scorer.lookup("가까이", "부사")
        self.assertEqual(match.match_method, "exact")
        self.assertAlmostEqual(match.difficulty, 0.000)
        self.assertEqual(match.matched_entry_id, 12)

    # -----------------------------------------------------------------
    # lookup: base_exact fallback (compound NOT in lexicon)
    # -----------------------------------------------------------------

    def test_base_exact_fallback_to_noun(self) -> None:
        # "분석하다" is NOT in lexicon; "분석"(명사) IS → base_exact
        match = self.scorer.lookup("분석하다", "동사")
        self.assertEqual(match.match_method, "base_exact")
        self.assertAlmostEqual(match.difficulty, 0.400)

    def test_base_exact_fallback_to_do(self) -> None:
        # "사용되다" NOT in lexicon; "사용"(명사) IS → base_exact
        match = self.scorer.lookup("사용되다", "동사")
        self.assertEqual(match.match_method, "base_exact")
        self.assertAlmostEqual(match.difficulty, 0.200)

    def test_base_exact_fallback_to_causative(self) -> None:
        # "훈련시키다" NOT in lexicon; "훈련"(명사) IS → base_exact
        match = self.scorer.lookup("훈련시키다", "동사")
        self.assertEqual(match.match_method, "base_exact")
        self.assertAlmostEqual(match.difficulty, 0.300)

    def test_base_exact_blocks_one_char_base(self) -> None:
        match = self.scorer.lookup("해하다", "동사")
        self.assertEqual(match.match_method, "unknown")

    # -----------------------------------------------------------------
    # lookup: base_exact with 어근
    # -----------------------------------------------------------------

    def test_base_exact_with_root(self) -> None:
        match = self.scorer.lookup("XR어근하다", "동사")
        self.assertEqual(match.match_method, "base_exact")
        self.assertAlmostEqual(match.difficulty, 0.500)

    # -----------------------------------------------------------------
    # lookup: lemma-only fallback
    # -----------------------------------------------------------------

    def test_lemma_only_when_pos_mismatch(self) -> None:
        # "문장" exists as 명사, but lookup as 동사 → lemma_only
        match = self.scorer.lookup("문장", "동사")
        self.assertEqual(match.match_method, "lemma_only")
        self.assertAlmostEqual(match.difficulty, 0.200)

    # -----------------------------------------------------------------
    # lookup: exact has priority over base_exact
    # -----------------------------------------------------------------

    def test_exact_priority_over_base_exact(self) -> None:
        # "가공" is in lexicon; "가공되다" is not → base_exact
        # But "가공" lookup as 명사 should be exact
        match = self.scorer.lookup("가공", "명사")
        self.assertEqual(match.match_method, "exact")

    # -----------------------------------------------------------------
    # score_tokens: content filtering
    # -----------------------------------------------------------------

    def test_score_tokens_filters_non_content(self) -> None:
        tokens = [
            _make_token("문장", "문장", "명사", is_content=True),
            _make_token("을", "을", "조사", is_content=False),
            _make_token("분석", "분석", "명사", is_content=True),
        ]
        scored = self.scorer.score_tokens(tokens)
        self.assertEqual(len(scored), 2)
        lemmas = {item["lemma"] for item in scored}
        self.assertEqual(lemmas, {"문장", "분석"})

    def test_score_tokens_all_non_content_empty(self) -> None:
        tokens = [
            _make_token("은", "은", "조사", is_content=False),
            _make_token("를", "를", "조사", is_content=False),
        ]
        scored = self.scorer.score_tokens(tokens)
        self.assertEqual(len(scored), 0)

    def test_score_tokens_output_keys(self) -> None:
        tokens = [_make_token("가공", "가공", "명사")]
        scored = self.scorer.score_tokens(tokens)
        self.assertEqual(len(scored), 1)
        item = scored[0]
        self.assertIn("surface", item)
        self.assertIn("lemma", item)
        self.assertIn("tag", item)
        self.assertIn("pos", item)
        self.assertIn("difficulty", item)
        self.assertIn("match_method", item)
        self.assertIn("matched_entry_id", item)

    # -----------------------------------------------------------------
    # compute_sentence_score
    # -----------------------------------------------------------------

    def test_compute_score_empty(self) -> None:
        result = self.scorer.compute_sentence_score([])
        self.assertEqual(result["lexical_score_0_1"], 0.0)
        self.assertEqual(result["content_token_count"], 0)
        self.assertEqual(result["unknown_token_count"], 0)
        self.assertEqual(result["score_parts"]["mean_all"], 0.0)
        self.assertEqual(result["score_parts"]["mean_top_n"], 0.0)
        self.assertEqual(result["score_parts"]["max"], 0.0)

    def test_compute_score_all_known(self) -> None:
        tokens = [
            _make_token("문장", "문장", "명사"),
            _make_token("분석", "분석", "명사"),
            _make_token("쉽다", "쉽다", "형용사"),
        ]
        result = self.scorer.compute_sentence_score(tokens)
        self.assertEqual(result["content_token_count"], 3)
        self.assertEqual(result["unknown_token_count"], 0)
        diffs = [0.200, 0.400, 0.000]
        mean_all = sum(diffs) / 3
        top_n = sorted(diffs, reverse=True)[:_TOP_N]
        mean_top_n = sum(top_n) / _TOP_N
        max_val = max(diffs)
        capped_count = len(result["scored_words"])
        w_mean_all, w_mean_top_n, w_max = _lexical_weights(capped_count)
        expected = w_mean_all * mean_all + w_mean_top_n * mean_top_n + w_max * max_val
        self.assertAlmostEqual(result["lexical_score_0_1"], expected, places=4)
        self.assertAlmostEqual(result["score_parts"]["mean_all"], mean_all, places=4)
        self.assertAlmostEqual(result["score_parts"]["mean_top_n"], mean_top_n, places=4)
        self.assertAlmostEqual(result["score_parts"]["max"], max_val, places=4)
        self.assertIn("lexical_weights", result["score_parts"])
        self.assertEqual(result["score_parts"]["lexical_weights"]["mean_all"], w_mean_all)
        self.assertEqual(result["score_parts"]["lexical_weights"]["mean_top_n"], w_mean_top_n)
        self.assertEqual(result["score_parts"]["lexical_weights"]["max"], w_max)

    def test_compute_score_tracks_unknown_count(self) -> None:
        tokens = [
            _make_token("문장", "문장", "명사"),
            _make_token("모르는단어", "모르는단어", "명사"),
        ]
        result = self.scorer.compute_sentence_score(tokens)
        self.assertEqual(result["content_token_count"], 2)
        self.assertEqual(result["unknown_token_count"], 1)

    def test_compute_score_output_shape(self) -> None:
        tokens = [
            _make_token("가공", "가공", "명사"),
            _make_token("분석", "분석", "명사"),
        ]
        result = self.scorer.compute_sentence_score(tokens)
        self.assertIn("lexical_score_0_1", result)
        self.assertNotIn("score_0_1", result)
        self.assertNotIn("score_10", result)
        self.assertIn("content_token_count", result)
        self.assertIn("unknown_token_count", result)
        self.assertIn("scored_words", result)
        self.assertIn("score_parts", result)
        self.assertIn("mean_all", result["score_parts"])
        self.assertIn("mean_top_n", result["score_parts"])
        self.assertIn("max", result["score_parts"])
        self.assertEqual(len(result["scored_words"]), 2)
        for word in result["scored_words"]:
            self.assertIn("surface", word)
            self.assertIn("lemma", word)
            self.assertIn("tag", word)
            self.assertIn("pos", word)
            self.assertIn("difficulty", word)
            self.assertIn("match_method", word)
            self.assertIn("matched_entry_id", word)

    def test_compute_score_single_token(self) -> None:
        tokens = [_make_token("어렵다", "어렵다", "형용사")]
        result = self.scorer.compute_sentence_score(tokens)
        self.assertEqual(result["content_token_count"], 1)
        self.assertAlmostEqual(result["lexical_score_0_1"], 0.800, places=4)

    # -----------------------------------------------------------------
    # get_difficulty convenience
    # -----------------------------------------------------------------

    def test_get_difficulty_exact(self) -> None:
        diff = self.scorer.get_difficulty("문장", "명사")
        self.assertAlmostEqual(diff, 0.200)

    def test_get_difficulty_unknown(self) -> None:
        diff = self.scorer.get_difficulty("없는단어", "명사")
        self.assertAlmostEqual(diff, 0.30)


class LexiconConfigTest(unittest.TestCase):

    def test_invalid_aggregation_raises(self) -> None:
        with self.assertRaises(ValueError):
            LexiconConfig(aggregation="invalid")

    def test_invalid_unknown_difficulty_too_low(self) -> None:
        with self.assertRaises(ValueError):
            LexiconConfig(unknown_difficulty=-0.1)

    def test_invalid_unknown_difficulty_too_high(self) -> None:
        with self.assertRaises(ValueError):
            LexiconConfig(unknown_difficulty=1.5)

    def test_valid_config_defaults(self) -> None:
        config = LexiconConfig()
        self.assertEqual(config.aggregation, "min")
        self.assertEqual(config.unknown_difficulty, 0.30)

    def test_valid_config_custom(self) -> None:
        config = LexiconConfig(aggregation="median", unknown_difficulty=0.50)
        self.assertEqual(config.aggregation, "median")
        self.assertEqual(config.unknown_difficulty, 0.50)


if __name__ == "__main__":
    unittest.main()
