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
    WEAK_CONNECTIVE_ENDINGS,
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

    def test_weak_connective_weighted(self) -> None:
        tokens = [
            _make_token("고", "고", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["weak_connective_weighted"], 0.3)
        self.assertEqual(sp["weak_connective_count"], 1)

    def test_weak_connective_surface_mismatch_not_counted(self) -> None:
        tokens = [
            _make_token("먹고", "먹다", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["weak_connective_weighted"], 0.0)

    def test_unlisted_ec_not_counted(self) -> None:
        tokens = [
            _make_token("아서", "아서", "EC"),
        ]
        result = self.scorer.score_tokens(tokens)
        sp = result["structure_parts"]
        self.assertEqual(sp["strong_logical_ending_count"], 0)
        self.assertEqual(sp["weak_connective_count"], 0)

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
            "connective_score", "logical_score", "modifier_score",
            "derivational_score",
            "content_token_count", "predicate_count", "ending_count",
            "connective_ending_count", "adnominal_count",
            "nominalizer_count", "logical_marker_count",
            "logical_marker_weighted",
            "strong_logical_ending_count", "strong_logical_ending_weighted",
            "weak_connective_count", "weak_connective_weighted",
            "derivational_suffix_count", "max_noun_chain",
        }
        self.assertEqual(set(sp.keys()), sub_keys)


if __name__ == "__main__":
    unittest.main()
