from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.morph import MorphToken  # noqa: E402
from sentdiff.structure import (  # noqa: E402
    DERIVATIONAL_SUFFIXES,
    LOGICAL_MARKERS,
    STRONG_LOGICAL_ENDINGS,
    StructureConfig,
    StructureScorer,
)


def _make_token(
    surface: str,
    lemma: str,
    tag: str,
    pos: str = "",
    is_content: bool = True,
    start: int = 0,
    end: int = 0,
) -> MorphToken:
    return MorphToken(
        surface=surface,
        lemma=lemma,
        tag=tag,
        pos=pos or _tag_to_pos(tag),
        start=start,
        end=end or len(surface),
        is_content=is_content,
    )


def _tag_to_pos(tag: str) -> str:
    mapping = {
        "NNG": "명사", "NNP": "명사", "NNB": "명사",
        "VV": "동사", "VA": "형용사",
        "VCP": "긍정지정사", "VCN": "부정지정사",
        "EC": "연결어미", "ETM": "관형형전성어미", "ETN": "명사형전성어미",
        "XSN": "명사파생접미사", "XSV": "동사파생접미사", "XSA": "형용사파생접미사",
        "XR": "어근", "MAG": "일반부사",
        "JKS": "주격조사", "JX": "보조사",
        "EP": "선어말어미", "EF": "종결어미",
    }
    return mapping.get(tag, tag)


class StructureScorerTest(unittest.TestCase):

    def setUp(self) -> None:
        self.scorer = StructureScorer()

    # -----------------------------------------------------------------
    # empty / no content tokens
    # -----------------------------------------------------------------

    def test_empty_tokens(self) -> None:
        result = self.scorer.score_tokens([])
        self.assertEqual(result["structure_score_0_1"], 0.0)
        sp = result["structure_parts"]
        self.assertEqual(sp["content_token_count"], 0)
        self.assertEqual(sp["length_score"], 0.0)
        self.assertEqual(sp["predicate_count"], 0)

    def test_all_non_content_tokens(self) -> None:
        tokens = [
            _make_token("은", "은", "JX", is_content=False),
            _make_token("를", "를", "JKO", is_content=False),
        ]
        result = self.scorer.score_tokens(tokens)
        self.assertEqual(result["structure_score_0_1"], 0.0)
        self.assertEqual(result["structure_parts"]["content_token_count"], 0)

    # -----------------------------------------------------------------
    # predicate_count: VV / VA / VCP / VCN
    # -----------------------------------------------------------------

    def test_predicate_count(self) -> None:
        tokens = [
            _make_token("먹다", "먹다", "VV"),
            _make_token("예쁘다", "예쁘다", "VA"),
            _make_token("이다", "이다", "VCP"),
            _make_token("아니다", "아니다", "VCN"),
            _make_token("문장", "문장", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["predicate_count"], 4)
        self.assertGreater(sp["predicate_score"], 0.0)

    # -----------------------------------------------------------------
    # embedding: ETM + ETN
    # -----------------------------------------------------------------

    def test_embedding_count(self) -> None:
        tokens = [
            _make_token("하는", "하다", "ETM"),
            _make_token("것", "것", "NNB"),
            _make_token("읽음", "읽다", "ETN"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["adnominal_count"], 1)
        self.assertEqual(sp["nominalizer_count"], 1)
        self.assertGreater(sp["embedding_score"], 0.0)

    # -----------------------------------------------------------------
    # connective endings: EC
    # -----------------------------------------------------------------

    def test_connective_ending_count(self) -> None:
        tokens = [
            _make_token("먹고", "먹다", "EC"),
            _make_token("마시며", "마시다", "EC"),
            _make_token("문장", "문장", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["connective_ending_count"], 2)
        self.assertGreater(sp["connective_score"], 0.0)

    # -----------------------------------------------------------------
    # logical markers: surface / lemma matching
    # -----------------------------------------------------------------

    def test_logical_marker_surface(self) -> None:
        tokens = [
            _make_token("따라서", "따르다", "MAG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["logical_marker_weighted"], 1.0)
        self.assertEqual(sp["logical_marker_count"], 1)

    def test_logical_marker_lemma(self) -> None:
        tokens = [
            _make_token("즉", "즉", "MAG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["logical_marker_weighted"], 1.0)
        self.assertEqual(sp["logical_marker_count"], 1)

    def test_strong_logical_ending_weighted(self) -> None:
        tokens = [
            _make_token("므로", "므로", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["strong_logical_ending_weighted"], 1.0)
        self.assertEqual(sp["strong_logical_ending_count"], 1)

    def test_strong_logical_ending_lemma(self) -> None:
        tokens = [
            _make_token("으므로", "므로", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["strong_logical_ending_weighted"], 1.0)
        self.assertEqual(sp["strong_logical_ending_count"], 1)

    def test_connective_logical_both_zero(self) -> None:
        tokens = [
            _make_token("문장", "문장", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["connective_score"], 0.0)
        self.assertEqual(sp["logical_score"], 0.0)
        self.assertEqual(sp["connective_logical_score"], 0.0)

    def test_connective_logical_averaging(self) -> None:
        tokens = [
            _make_token("먹고", "먹다", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["connective_ending_count"], 1)
        self.assertEqual(sp["connective_score"], 0.25)  # 1/4
        self.assertEqual(sp["logical_score"], 0.0)      # no marker match
        self.assertAlmostEqual(sp["connective_logical_score"], 0.0833, places=3)

    def test_logical_marker_increases_logical_score(self) -> None:
        tokens = [
            _make_token("따라서", "따르다", "MAG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["logical_marker_weighted"], 1.0)
        self.assertEqual(sp["logical_score"], 0.25)  # 1.0/4
        self.assertAlmostEqual(sp["connective_logical_score"], 0.1667, places=3)  # (0 + 0.25×2)/3

    def test_unlisted_ec_not_counted_as_logical(self) -> None:
        tokens = [
            _make_token("아서", "아서", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["strong_logical_ending_count"], 0)
        self.assertEqual(sp["logical_marker_weighted"], 0.0)

    # -----------------------------------------------------------------
    # noun chain
    # -----------------------------------------------------------------

    def test_noun_chain_simple(self) -> None:
        tokens = [
            _make_token("사회", "사회", "NNG"),
            _make_token("문화", "문화", "NNG"),
            _make_token("연구", "연구", "NNG"),
            _make_token("방법", "방법", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["max_noun_chain"], 4)

    def test_noun_chain_xsn_extends(self) -> None:
        tokens = [
            _make_token("방법", "방법", "NNG"),
            _make_token("론", "론", "XSN"),
            _make_token("적", "적", "XSN"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["max_noun_chain"], 3)

    def test_noun_chain_xsn_does_not_start(self) -> None:
        tokens = [
            _make_token("화", "화", "XSN"),
            _make_token("과정", "과정", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["max_noun_chain"], 1)

    # -----------------------------------------------------------------
    # derivational suffixes: XSN / XSV / XSA + surface check
    # -----------------------------------------------------------------

    def test_derivational_suffix_tag(self) -> None:
        tokens = [
            _make_token("분석", "분석", "NNG"),
            _make_token("적", "적", "XSN"),
            _make_token("체계", "체계", "NNG"),
            _make_token("성", "성", "XSN"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["derivational_suffix_count"], 2)

    def test_derivational_suffix_surface(self) -> None:
        tokens = [
            _make_token("체계", "체계", "NNG"),
            _make_token("론", "론", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["derivational_suffix_count"], 1)

    # -----------------------------------------------------------------
    # output shape
    # -----------------------------------------------------------------

    def test_output_shape(self) -> None:
        tokens = [
            _make_token("문장", "문장", "NNG"),
            _make_token("분석", "분석", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        self.assertIn("structure_score_0_1", result)
        self.assertIn("structure_score_10", result)
        self.assertIn("structure_parts", result)

        sp = result["structure_parts"]
        sub_keys = {
            "length_score", "predicate_score", "embedding_score",
            "connective_logical_score", "modifier_score",
            "derivational_score", "structural_span_score",
            "structural_span_raw", "structural_span_normalized",
            "structural_span_count",
            "repetition_score", "repetition_raw",
            "repetition_count", "repetition_details",
            "content_token_count", "predicate_count", "ending_count",
            "connective_ending_count", "adnominal_count",
            "nominalizer_count", "logical_marker_count",
            "logical_marker_weighted",
            "strong_logical_ending_count", "strong_logical_ending_weighted",
            "derivational_suffix_count",
            "max_noun_chain",
            "predicate_count_adj", "max_noun_chain_adj",
            "connective_score", "logical_score",
        }
        self.assertEqual(set(sp.keys()), sub_keys)

    # -----------------------------------------------------------------
    # structural_span: segment content count at ETM/ETN/EC
    # -----------------------------------------------------------------

    def test_structural_span_no_markers(self) -> None:
        tokens = [
            _make_token("문장", "문장", "NNG"),
            _make_token("분석", "분석", "NNG"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["structural_span_score"], 0.0)
        self.assertEqual(sp["structural_span_count"], 0)

    def test_structural_span_content_counted(self) -> None:
        tokens = [
            _make_token("세계", "세계", "NNG"),
            _make_token("근원", "근원", "NNG"),
            _make_token("적인", "적", "ETM", is_content=False),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["structural_span_count"], 1)
        self.assertEqual(sp["structural_span_raw"], 2.0)

    def test_structural_span_leading_marker_skipped(self) -> None:
        tokens = [
            _make_token("는", "는", "ETM", is_content=False),
            _make_token("것", "것", "NNB"),
            _make_token("먹", "먹다", "VV"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["structural_span_count"], 0)
        self.assertEqual(sp["structural_span_score"], 0.0)

    def test_structural_span_ec_boundary_order(self) -> None:
        tokens = [
            _make_token("뛰", "뛰다", "VV"),
            _make_token("고", "고", "EC", is_content=False),
            _make_token("점프", "점프", "NNG"),
            _make_token("하며", "하다", "EC", is_content=False),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["structural_span_count"], 2)
        self.assertEqual(sp["structural_span_raw"], 2.0)

    def test_structural_span_aux_ec(self) -> None:
        tokens = [
            _make_token("먹", "먹다", "VV"),
            _make_token("고", "고", "EC", is_content=False),
            _make_token("싶", "싶다", "VX", is_content=False),
            _make_token("다", "다", "EF", is_content=False),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["structural_span_count"], 1)
        self.assertEqual(sp["structural_span_raw"], 1.0)


    # -----------------------------------------------------------------
    # repetition: duplicated surfaces
    # -----------------------------------------------------------------

    def test_repetition_no_duplicates(self) -> None:
        tokens = [
            _make_token("연구", "연구", "NNG"),
            _make_token("분석", "분석", "NNG"),
        ]
        scored_words_full = [
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "분석", "lemma": "분석", "pos": "NNG", "difficulty": 0.7, "match_method": "exact", "matched_entry_id": 2},
        ]
        result = self.scorer.score_tokens(tokens, scored_words_full=scored_words_full, polysemy_map={})
        sp = result["structure_parts"]
        self.assertEqual(sp["repetition_score"], 0.0)
        self.assertEqual(sp["repetition_count"], 0)
        self.assertEqual(sp["repetition_raw"], 0.0)

    def test_repetition_three_times(self) -> None:
        tokens = [
            _make_token("연구", "연구", "NNG"),
            _make_token("연구", "연구", "NNG"),
            _make_token("연구", "연구", "NNG"),
        ]
        scored_words_full = [
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
        ]
        polysemy_map = {"연구": 1}
        result = self.scorer.score_tokens(tokens, scored_words_full=scored_words_full, polysemy_map=polysemy_map)
        sp = result["structure_parts"]
        self.assertEqual(sp["repetition_count"], 2)
        expected_raw = (3 - 1) * 0.6 * 1  # (count-1) * difficulty * polysemy
        self.assertAlmostEqual(sp["repetition_raw"], expected_raw, places=4)
        expected_score = min(1.0, expected_raw / 3.5)
        self.assertAlmostEqual(sp["repetition_score"], expected_score, places=4)

    def test_repetition_excluded_lemma(self) -> None:
        tokens = [
            _make_token("말", "말", "NNG"),
            _make_token("말", "말", "NNG"),
        ]
        scored_words_full = [
            {"surface": "말", "lemma": "말", "pos": "NNG", "difficulty": 0.5, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "말", "lemma": "말", "pos": "NNG", "difficulty": 0.5, "match_method": "exact", "matched_entry_id": 1},
        ]
        result = self.scorer.score_tokens(tokens, scored_words_full=scored_words_full, polysemy_map={"말": 3})
        sp = result["structure_parts"]
        self.assertEqual(sp["repetition_score"], 0.0)
        self.assertEqual(sp["repetition_count"], 0)

    def test_repetition_multiple_surfaces(self) -> None:
        tokens = [
            _make_token("연구", "연구", "NNG"),
            _make_token("연구", "연구", "NNG"),
            _make_token("분석", "분석", "NNG"),
            _make_token("분석", "분석", "NNG"),
            _make_token("분석", "분석", "NNG"),
        ]
        scored_words_full = [
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "분석", "lemma": "분석", "pos": "NNG", "difficulty": 0.7, "match_method": "exact", "matched_entry_id": 2},
            {"surface": "분석", "lemma": "분석", "pos": "NNG", "difficulty": 0.7, "match_method": "exact", "matched_entry_id": 2},
            {"surface": "분석", "lemma": "분석", "pos": "NNG", "difficulty": 0.7, "match_method": "exact", "matched_entry_id": 2},
        ]
        polysemy_map = {"연구": 1, "분석": 2}
        result = self.scorer.score_tokens(tokens, scored_words_full=scored_words_full, polysemy_map=polysemy_map)
        sp = result["structure_parts"]
        self.assertEqual(sp["repetition_count"], 3)  # (2-1) + (3-1) = 3
        expected_raw = (2 - 1) * 0.6 * 1 + (3 - 1) * 0.7 * 2
        self.assertAlmostEqual(sp["repetition_raw"], expected_raw, places=4)

    def test_repetition_details_structure(self) -> None:
        tokens = [
            _make_token("연구", "연구", "NNG"),
            _make_token("연구", "연구", "NNG"),
        ]
        scored_words_full = [
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
            {"surface": "연구", "lemma": "연구", "pos": "NNG", "difficulty": 0.6, "match_method": "exact", "matched_entry_id": 1},
        ]
        result = self.scorer.score_tokens(tokens, scored_words_full=scored_words_full, polysemy_map={"연구": 2})
        sp = result["structure_parts"]
        self.assertEqual(len(sp["repetition_details"]), 1)
        detail = sp["repetition_details"][0]
        self.assertEqual(detail["surface"], "연구")
        self.assertEqual(detail["count"], 2)
        self.assertEqual(detail["polysemy"], 2)


if __name__ == "__main__":
    unittest.main()
