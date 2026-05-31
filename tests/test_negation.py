from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.morph import MorphToken  # noqa: E402
from sentdiff.negation import NegationAnalyzer  # noqa: E402


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
        "NNG": "명사", "NNB": "명사",
        "VV": "동사", "VA": "형용사",
        "VCP": "긍정지정사", "VCN": "부정지정사",
        "EC": "연결어미", "ETM": "관형형전성어미", "ETN": "명사형전성어미",
        "XSV": "동사파생접미사",
        "MAG": "일반부사",
        "JKS": "주격조사", "JX": "보조사",
        "EF": "종결어미",
        "SP": "쉼표",
    }
    return mapping.get(tag, tag)


class NegationAnalyzerTest(unittest.TestCase):

    def setUp(self) -> None:
        self.analyzer = NegationAnalyzer()

    def _assert_negation(self, tokens, *, count=None, local_max=None, score=None):
        result = self.analyzer.analyze(tokens)
        if count is not None:
            self.assertEqual(result["negation_count_total"], count)
        if local_max is not None:
            self.assertEqual(result["negation_count_local_max"], local_max)
        if score is not None:
            self.assertGreaterEqual(result["negation_score"], score)

    # =====================================================================
    # simple negation → score == 0.0
    # =====================================================================

    def test_simple_mag_an(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("가다", "가다", "VV"),
        ]
        self._assert_negation(tokens, count=1, local_max=1, score=0.0)

    def test_simple_mag_mot(self):
        tokens = [
            _make_token("못", "못", "MAG"),
            _make_token("가다", "가다", "VV"),
        ]
        self._assert_negation(tokens, count=1, local_max=1, score=0.0)

    def test_simple_va_eop(self):
        tokens = [
            _make_token("시간", "시간", "NNG"),
            _make_token("이", "이", "JKS"),
            _make_token("없", "없다", "VA"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=1, local_max=1, score=0.0)

    def test_simple_vcn_ani(self):
        tokens = [
            _make_token("그것", "그것", "NP"),
            _make_token("은", "은", "JX"),
            _make_token("아니", "아니다", "VCN"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=1, local_max=1, score=0.0)

    def test_simple_vx_mal(self):
        tokens = [
            _make_token("하", "하다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("말", "말다", "VX"),
            _make_token("아", "아", "EF"),
        ]
        self._assert_negation(tokens, count=1, local_max=1, score=0.0)

    # =====================================================================
    # parallel negation → score == 0.0
    # =====================================================================

    def test_parallel_an_meokgo_an(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("먹", "먹다", "VV"),
            _make_token("고", "고", "EC"),
            _make_token("안", "안", "MAG"),
            _make_token("잤", "자다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.0)

    def test_parallel_an_johaha_an_handa(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("좋아하", "좋아하다", "VV"),
            _make_token("고", "고", "EC"),
            _make_token("안", "안", "MAG"),
            _make_token("하", "하다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.0)

    def test_parallel_an_meokgo_jaji_anha(self):
        # 안 먹고 자지 않았다 → 고 is coordinate, negations in separate segments
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("먹", "먹다", "VV"),
            _make_token("고", "고", "EC"),
            _make_token("자", "자다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.0)

    def test_parallel_with_punct(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("좋아하", "좋아하다", "VV"),
            _make_token("고", "고", "EC"),
            _make_token(",", ",", "SP"),
            _make_token("안", "안", "MAG"),
            _make_token("좋아하", "좋아하다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.0)

    # =====================================================================
    # direct multiple negation → score >= 0.5
    # =====================================================================

    def test_double_an_hal_su_eop(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("하", "하다", "VV"),
            _make_token("ᆯ", "ᆯ", "ETM"),
            _make_token("수", "수", "NNB"),
            _make_token("없", "없다", "VA"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=2, score=0.5)

    def test_double_mot_haji_anhassda(self):
        tokens = [
            _make_token("못", "못", "MAG"),
            _make_token("하", "하다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
            _make_token("았다", "았다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=2, score=0.5)

    def test_double_an_mot_ganda(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("못", "못", "MAG"),
            _make_token("가", "가다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=2, score=0.5)

    def test_double_aux_chain(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("하", "하다", "VV"),
            _make_token("고", "고", "EC"),
            _make_token("싶", "싶다", "VX"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
        ]
        self._assert_negation(tokens, count=2, local_max=2, score=0.5)

    def test_double_eopji_anhda(self):
        tokens = [
            _make_token("없", "없다", "VA"),
            _make_token("지", "지", "EC"),
            _make_token("는", "는", "JX"),
            _make_token("않", "않", "VX"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=2, score=0.5)

    # =====================================================================
    # conditional multiple negation → score >= 1.0
    # =====================================================================

    def test_conditional_an_myeon_an_doenda(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("하", "하다", "VV"),
            _make_token("면", "면", "EC"),
            _make_token("안", "안", "MAG"),
            _make_token("되", "되다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=1.0)

    def test_conditional_gaji_anh_eumyeon_an(self):
        tokens = [
            _make_token("가", "가다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
            _make_token("으면", "으면", "EC"),
            _make_token("안", "안", "MAG"),
            _make_token("되", "되다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=1.0)

    def test_conditional_haji_anh_eumyeon_an(self):
        tokens = [
            _make_token("하", "하다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
            _make_token("으면", "으면", "EC"),
            _make_token("안", "안", "MAG"),
            _make_token("되", "되다", "VV"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=1.0)

    # =====================================================================
    # quote / embedded negation → score >= 0.5
    # =====================================================================

    def test_quote_ani_saenggak_an(self):
        tokens = [
            _make_token("아니", "아니다", "VCN"),
            _make_token("라고", "라고", "EC"),
            _make_token("생각", "생각하다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.5)

    def test_quote_ani_malhal_su_eop(self):
        tokens = [
            _make_token("아니", "아니다", "VCN"),
            _make_token("라고", "라고", "EC"),
            _make_token("말", "말", "NNG"),
            _make_token("하", "하다", "XSV"),
            _make_token("ᆯ", "ᆯ", "ETM"),
            _make_token("수", "수", "NNB"),
            _make_token("없", "없다", "VA"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.5)

    def test_quote_mal_lago_haji_anh(self):
        tokens = [
            _make_token("가", "가다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("말", "말다", "VX"),
            _make_token("라고", "라고", "EC"),
            _make_token("하", "하다", "VV"),
            _make_token("지", "지", "EC"),
            _make_token("않", "않", "VX"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.5)

    def test_quote_ani_bol_su_eop(self):
        tokens = [
            _make_token("그것", "그것", "NP"),
            _make_token("이", "이다", "VCP"),
            _make_token("아니", "아니다", "VCN"),
            _make_token("라고", "라고", "EC"),
            _make_token("보", "보다", "VV"),
            _make_token("ᆯ", "ᆯ", "ETM"),
            _make_token("수", "수", "NNB"),
            _make_token("없", "없다", "VA"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.5)

    # =====================================================================
    # nominal / partial negation → score >= 0.5
    # =====================================================================

    def test_nominal_an_gan_geot_ani(self):
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("가", "가다", "VV"),
            _make_token("ᆫ", "ᆫ", "ETM"),
            _make_token("것", "것", "NNB"),
            _make_token("은", "은", "JX"),
            _make_token("아니", "아니다", "VCN"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.5)

    def test_nominal_eop_neun_geot_ani(self):
        tokens = [
            _make_token("없", "없다", "VA"),
            _make_token("는", "는", "ETM"),
            _make_token("것", "것", "NNB"),
            _make_token("은", "은", "JX"),
            _make_token("아니", "아니다", "VCN"),
            _make_token("다", "다", "EF"),
        ]
        self._assert_negation(tokens, count=2, local_max=1, score=0.5)

    # =====================================================================
    # output shape
    # =====================================================================

    def test_output_shape(self) -> None:
        tokens = [
            _make_token("안", "안", "MAG"),
            _make_token("가다", "가다", "VV"),
        ]
        result = self.analyzer.analyze(tokens)
        sub_keys = {
            "negation_count_total", "negation_count_local_max",
            "negation_embedded_links", "negation_construction_hits",
            "local_negation_score", "construction_negation_score",
            "embedded_negation_score", "negation_density_score",
            "negation_score",
        }
        self.assertEqual(set(result.keys()), sub_keys)


if __name__ == "__main__":
    unittest.main()
