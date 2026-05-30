from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.lexicon_builder import (  # noqa: E402
    LexiconBuildConfig,
    _choose_derivation_base_row,
    _difficulty_basis,
    add_difficulty_columns,
    adjust_derivational_difficulty,
    finalize_lexicon,
)
from sentdiff.normalize import (  # noqa: E402
    parse_grade5,
    rank_to_difficulty,
    split_light_predicate_suffix,
)


def _row(
    lemma: str,
    *,
    difficulty: float,
    raw_difficulty: float | None = None,
    pos_norm: str = "명사",
    homograph_no: int = 0,
    source_40k: bool = True,
    source_5965: bool = False,
    rank_5965: float | None = None,
) -> dict[str, object]:
    if raw_difficulty is None:
        raw_difficulty = difficulty

    return {
        "lemma": lemma,
        "difficulty": difficulty,
        "raw_difficulty": raw_difficulty,
        "pos_norm": pos_norm,
        "homograph_no": homograph_no,
        "source_40k": source_40k,
        "source_5965": source_5965,
        "rank_5965": rank_5965,
    }


class LightPredicateSuffixTests(unittest.TestCase):
    def test_light_predicate_suffix_helpers_split_only_derivations(self) -> None:
        self.assertEqual(split_light_predicate_suffix("가공하다"), ("가공", "하다", 0.03))
        self.assertEqual(split_light_predicate_suffix("사용되다"), ("사용", "되다", 0.04))
        self.assertEqual(split_light_predicate_suffix("훈련시키다"), ("훈련", "시키다", 0.05))

        self.assertIsNone(split_light_predicate_suffix("하다"))
        self.assertIsNone(split_light_predicate_suffix("되다"))
        self.assertIsNone(split_light_predicate_suffix("시키다"))
        self.assertIsNone(split_light_predicate_suffix("들어가다"))


class DerivationalDifficultyTests(unittest.TestCase):
    def test_derivational_adjustment_lowers_difficulty_and_preserves_raw(self) -> None:
        df = pd.DataFrame(
            [
                _row("가공", difficulty=0.494, pos_norm="명사"),
                _row("가공하다", difficulty=0.967, raw_difficulty=0.967, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())
        adjusted = out[out["lemma"].eq("가공하다")].iloc[0]

        self.assertLess(adjusted["difficulty"], adjusted["raw_difficulty"])
        self.assertEqual(adjusted["raw_difficulty"], 0.967)
        self.assertEqual(adjusted["derivation_base"], "가공")
        self.assertEqual(adjusted["derivation_suffix"], "하다")
        self.assertTrue(bool(adjusted["derivation_adjusted"]))

    def test_derivational_adjustment_handles_do_be_and_causative_suffixes(self) -> None:
        df = pd.DataFrame(
            [
                _row("사용", difficulty=0.20, pos_norm="명사"),
                _row("사용되다", difficulty=0.90, pos_norm="동사"),
                _row("훈련", difficulty=0.30, pos_norm="명사"),
                _row("훈련시키다", difficulty=0.95, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())
        used = out[out["lemma"].eq("사용되다")].iloc[0]
        trained = out[out["lemma"].eq("훈련시키다")].iloc[0]

        self.assertTrue(bool(used["derivation_adjusted"]))
        self.assertEqual(used["derivation_base"], "사용")
        self.assertEqual(used["derivation_suffix"], "되다")
        self.assertTrue(bool(trained["derivation_adjusted"]))
        self.assertEqual(trained["derivation_base"], "훈련")
        self.assertEqual(trained["derivation_suffix"], "시키다")

    def test_non_targets_single_lemmas_and_missing_bases_are_not_adjusted(self) -> None:
        df = pd.DataFrame(
            [
                _row("들어가다", difficulty=0.95, pos_norm="동사"),
                _row("살아가다", difficulty=0.95, pos_norm="동사"),
                _row("나아가다", difficulty=0.95, pos_norm="동사"),
                _row("하다", difficulty=0.0, pos_norm="동사"),
                _row("되다", difficulty=0.0, pos_norm="동사"),
                _row("시키다", difficulty=0.0, pos_norm="동사"),
                _row("없는말하다", difficulty=0.9, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())

        for lemma in ["들어가다", "살아가다", "나아가다", "하다", "되다", "시키다"]:
            row = out[out["lemma"].eq(lemma)].iloc[0]
            self.assertFalse(bool(row["derivation_adjusted"]))
            self.assertEqual(row["difficulty"], row["raw_difficulty"])

        missing = out[out["lemma"].eq("없는말하다")].iloc[0]
        self.assertEqual(missing["derivation_base"], "없는말")
        self.assertFalse(bool(missing["derivation_adjusted"]))

    def test_adjustment_never_raises_difficulty_when_downward_only(self) -> None:
        df = pd.DataFrame(
            [
                _row("쉬운", difficulty=0.80, pos_norm="명사"),
                _row("쉬운하다", difficulty=0.10, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())
        row = out[out["lemma"].eq("쉬운하다")].iloc[0]

        self.assertEqual(row["difficulty"], row["raw_difficulty"])
        self.assertFalse(bool(row["derivation_adjusted"]))

    def test_derivational_adjustment_caps_maximum_drop(self) -> None:
        df = pd.DataFrame(
            [
                _row("가공", difficulty=0.0, pos_norm="명사"),
                _row("가공하다", difficulty=1.0, raw_difficulty=1.0, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())
        row = out[out["lemma"].eq("가공하다")].iloc[0]

        self.assertTrue(bool(row["derivation_adjusted"]))
        self.assertAlmostEqual(float(row["difficulty"]), 0.65)

    def test_derivational_adjustment_skips_one_character_base(self) -> None:
        df = pd.DataFrame(
            [
                _row("해", difficulty=0.0, pos_norm="명사"),
                _row("해하다", difficulty=1.0, raw_difficulty=1.0, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())
        row = out[out["lemma"].eq("해하다")].iloc[0]

        self.assertEqual(row["derivation_base"], "해")
        self.assertFalse(bool(row["derivation_adjusted"]))
        self.assertEqual(row["difficulty"], row["raw_difficulty"])

    def test_derivational_adjustment_requires_nominal_or_root_base(self) -> None:
        df = pd.DataFrame(
            [
                _row("좋아", difficulty=0.0, pos_norm="동사"),
                _row("좋아하다", difficulty=0.9, raw_difficulty=0.9, pos_norm="동사"),
            ]
        )

        out = adjust_derivational_difficulty(df, LexiconBuildConfig())
        row = out[out["lemma"].eq("좋아하다")].iloc[0]

        self.assertEqual(row["derivation_base"], "좋아")
        self.assertFalse(bool(row["derivation_adjusted"]))
        self.assertEqual(row["difficulty"], row["raw_difficulty"])

    def test_add_difficulty_columns_preserves_raw_and_marks_basis(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "lemma": "가공",
                    "homograph_no": 0,
                    "pos_norm": "명사",
                    "pos_40k": "명사",
                    "pos_5965": "",
                    "grade_5": 3,
                    "aux_5965_diff": None,
                    "rank_5965": None,
                    "origin": "",
                    "domain": "",
                    "source_40k": True,
                    "source_5965": False,
                },
                {
                    "lemma": "가공하다",
                    "homograph_no": 0,
                    "pos_norm": "동사",
                    "pos_40k": "동사",
                    "pos_5965": "",
                    "grade_5": 5,
                    "aux_5965_diff": None,
                    "rank_5965": None,
                    "origin": "",
                    "domain": "",
                    "source_40k": True,
                    "source_5965": False,
                },
            ]
        )

        out = add_difficulty_columns(df, LexiconBuildConfig())
        row = out[out["lemma"].eq("가공하다")].iloc[0]

        self.assertIn("raw_difficulty", out.columns)
        self.assertLess(row["difficulty"], row["raw_difficulty"])
        self.assertIn("derivation_adjusted", row["difficulty_basis"])

    def test_origin_domain_missing_is_not_used_as_easy_signal(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "lemma": "일식",
                    "homograph_no": 0,
                    "pos_norm": "명사",
                    "pos_40k": "",
                    "pos_5965": "명사",
                    "grade_5": None,
                    "aux_5965_diff": 0.25,
                    "rank_5965": 5965,
                    "origin": "",
                    "domain": "",
                    "source_40k": False,
                    "source_5965": True,
                }
            ]
        )

        out = add_difficulty_columns(df, LexiconBuildConfig())
        row = out.iloc[0]

        self.assertTrue(pd.isna(row["origin_domain_signal"]))
        self.assertAlmostEqual(float(row["rank_diff"]), 1.0)
        self.assertAlmostEqual(float(row["raw_difficulty"]), 0.5)
        self.assertEqual(row["difficulty_basis"], "vocab_5965+rank_5965")


class NormalizeDifficultyHelperTests(unittest.TestCase):
    def test_parse_grade5_is_strict(self) -> None:
        self.assertEqual(parse_grade5("1"), 1)
        self.assertEqual(parse_grade5("1.0"), 1)
        self.assertEqual(parse_grade5("1등급"), 1)
        self.assertEqual(parse_grade5(5), 5)

        self.assertIsNone(parse_grade5("15등급"))
        self.assertIsNone(parse_grade5("1~5등급"))
        self.assertIsNone(parse_grade5("등급5"))
        self.assertIsNone(parse_grade5("5등급 후보"))

    def test_rank_to_difficulty_starts_at_zero(self) -> None:
        self.assertAlmostEqual(rank_to_difficulty(1, 5965), 0.0)
        self.assertAlmostEqual(rank_to_difficulty(5965, 5965), 1.0)
        self.assertIsNone(rank_to_difficulty(0, 5965))


class DerivationBaseSelectionTests(unittest.TestCase):
    def test_base_selection_uses_boolean_sources_not_final_source_label(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    **_row(
                        "기준",
                        difficulty=0.1,
                        pos_norm="명사",
                        source_40k=False,
                        source_5965=False,
                    ),
                    "source": "both",
                },
                {
                    **_row(
                        "기준",
                        difficulty=0.2,
                        pos_norm="명사",
                        source_40k=True,
                        source_5965=True,
                    ),
                    "source": "vocab_40k_only",
                },
            ]
        )

        chosen = _choose_derivation_base_row(rows)
        self.assertIsNotNone(chosen)
        self.assertEqual(float(chosen["difficulty"]), 0.2)

    def test_base_selection_treats_compound_pos_as_preferred_nominal(self) -> None:
        rows = pd.DataFrame(
            [
                _row("기준", difficulty=0.1, pos_norm="동사", source_40k=True),
                _row("기준", difficulty=0.2, pos_norm="부사/명사", source_40k=True),
            ]
        )

        chosen = _choose_derivation_base_row(rows)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen["pos_norm"], "부사/명사")

    def test_homograph_number_is_only_final_tie_breaker(self) -> None:
        rows = pd.DataFrame(
            [
                _row("기준", difficulty=0.20, pos_norm="명사", homograph_no=1),
                _row("기준", difficulty=0.10, pos_norm="명사", homograph_no=2),
            ]
        )

        chosen = _choose_derivation_base_row(rows)
        self.assertIsNotNone(chosen)
        self.assertEqual(int(chosen["homograph_no"]), 2)


class FinalizeLexiconContractTests(unittest.TestCase):
    def test_finalize_places_raw_difficulty_after_difficulty(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "lemma": "가공하다",
                    "homograph_no": 0,
                    "pos_norm": "동사",
                    "pos_40k": "동사",
                    "pos_5965": "",
                    "difficulty": 0.5,
                    "raw_difficulty": 0.9,
                    "source_40k": True,
                    "source_5965": False,
                }
            ]
        )

        out = finalize_lexicon(df)
        self.assertEqual(
            list(out.columns[:5]),
            ["entry_id", "lemma", "difficulty", "raw_difficulty", "homograph_no"],
        )


if __name__ == "__main__":
    unittest.main()
