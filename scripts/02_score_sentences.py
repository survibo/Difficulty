"""
python scripts/02_score_sentences.py "문장을 분석한다."
python scripts/02_score_sentences.py --file data/sentences.txt
python scripts/02_score_sentences.py --debug "문장을 분석한다."
python scripts/02_score_sentences.py          # interactive mode (Ctrl+Z/Ctrl+D to exit)
"""

import argparse
import sys
from pathlib import Path

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from sentdiff.lexical import LexiconConfig
from sentdiff.pipeline import SentenceScorer

from sentdiff.morph import KiwiMorphAnalyzer, morph_tag_role


# ---------------------------------------------------------------------------
# Debug helpers
# ---------------------------------------------------------------------------


def _structure_role(tag: str, surface: str) -> str:
    return morph_tag_role(tag)


def _is_lexical_token(tag: str) -> bool:
    from sentdiff.morph import is_content_tag
    return is_content_tag(tag)


def _cjk_width(s: str) -> int:
    """터미널에서의 시각적 폭 반환 (CJK=2, ASCII=1)."""
    width = 0
    for ch in s:
        if ord(ch) > 0x2E80:
            width += 2
        else:
            width += 1
    return width


def _pad(s: str, width: int) -> str:
    """CJK 문자 폭을 고려해 문자열을 width 칸에 왼쪽 정렬."""
    actual = _cjk_width(s)
    return s + " " * max(0, width - actual)


def _token_table(sentence: str) -> list[dict]:
    analyzer = KiwiMorphAnalyzer()
    tokens = analyzer.analyze(sentence)
    rows = []
    for t in tokens:
        rows.append({
            "surface": t.surface,
            "tag": t.tag,
            "pos": t.pos,
            "lemma": t.lemma,
            "lexical": "yes" if _is_lexical_token(t.tag) else "no",
            "structure_role": _structure_role(t.tag, t.surface),
        })
    return rows


def _format_morph_trace(sentence: str) -> str:
    rows = _token_table(sentence)
    if not rows:
        return "  (empty)"
    lines = [
        f"  {_pad('surface', 10)}{_pad('tag', 7)}{_pad('pos', 10)}"
        f"{_pad('lemma', 10)}{_pad('lexical', 8)}structure_role"
    ]
    for r in rows:
        lines.append(
            f"  {_pad(r['surface'], 10)}{_pad(r['tag'], 7)}{_pad(r['pos'], 10)}"
            f"{_pad(r['lemma'], 10)}{_pad(r['lexical'], 8)}{r['structure_role']}"
        )
    return "\n".join(lines)


def _structure_reasons(sp: dict) -> list[str]:
    reasons = []
    bc = sp["structure_content_token_count"]
    pc = sp["predicate_count"]
    adj_pc = sp["predicate_count_adj"]
    cc = sp["connective_ending_count"]
    em = sp["adnominal_count"] + sp["nominalizer_count"]
    ae = sp["adverbial_ending_count"]
    lr = sp["logical_marker_weighted"] + sp["strong_logical_ending_weighted"]
    cs = sp["connective_score"]
    ls = sp["logical_score"]
    mc = sp["max_noun_chain"]
    adj_mc = sp["max_noun_chain_adj"]
    dc = sp["derivational_suffix_count"]
    rc = sp["repetition_count"]
    rr = sp["repetition_raw"]

    if pc == 0:
        reasons.append("  no predicate tokens")
    elif adj_pc == 0:
        reasons.append(f"  predicate_count={pc} → -1보정 → adj=0")
    else:
        reasons.append(f"  predicate_count={pc} → adj={adj_pc}/7 → score={sp['predicate_score']}")

    if bc <= 5:
        reasons.append(f"  content_words={bc} ≤ 5 → length=0")
    elif bc < 29:
        reasons.append(f"  content_words={bc} → ({bc}-5)/24={sp['length_score']}")
    else:
        reasons.append(f"  content_words={bc} → length=1.0 (≥29)")

    if em == 0 and ae == 0:
        reasons.append("  no ETM/ETN/부사절 → embedding=0")
    else:
        parts = []
        if em: parts.append(f"ETM+ETN={em}")
        if ae: parts.append(f"부사절={ae}")
        reasons.append(f"  {' + '.join(parts)}/7 → embedding={sp['embedding_score']}")

    if cc == 0 and lr == 0:
        reasons.append("  no EC/logical markers → connective=0, logical=0")
    else:
        reasons.append(f"  EC={cc}/4 → cs={cs:.3f} (×{sp['connective_score']})  +  logical_weighted={lr:.1f}/4 → ls={ls:.3f} (×{sp['logical_score']})")

    if mc <= 1:
        reasons.append(f"  max_noun_chain={mc} → adj=0 → modifier=0")
    else:
        reasons.append(f"  max_noun_chain={mc} → adj={adj_mc}/4 → modifier={sp['modifier_score']}")

    if dc == 0:
        reasons.append("  no derivational suffixes → derivational=0 (display-only)")
    else:
        reasons.append(f"  derivational_count={dc}/3 → derivational={sp['derivational_score']} (display-only)")

    if rc == 0:
        reasons.append("  no word repetition → repetition=0")
    else:
        details = sp.get("repetition_details", [])
        parts = []
        for d in details:
            parts.append(f"{d['surface']}({d['count']}회×{d['difficulty']}d×{d['polysemy']}pol)")
        parts_str = ", ".join(parts)
        reasons.append(f"  repetition_raw={rr}/6.0 → score={sp['repetition_score']}  ({parts_str})")

    return reasons


def _active_features(sp: dict) -> list[str]:
    active = []
    if sp["predicate_score"] > 0:
        active.append("predicate")
    if sp["embedding_score"] > 0:
        active.append("embedding")
    if sp["connective_score"] > 0:
        active.append("connective")
    if sp["logical_score"] > 0:
        active.append("logical")
    if sp["modifier_score"] > 0:
        active.append("modifier")
    if sp["repetition_score"] > 0:
        active.append("repetition")
    return active


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_result(result: dict, debug: bool = False) -> str:
    parts = [
        f"sentence: {result['sentence']}",
    ]

    if debug:
        lp = result["score_parts"]
        sp = result["structure_parts"]
        nd = result["negation_detail"]

        lex = result["lexical_score_0_1"]
        struc = result["structure_score_0_1"]
        neg = result["negation_score_0_1"]
        final = result["score_0_1"]

        content = result["lexical_unit_count"]
        unknown = result["unknown_lexical_unit_count"]
        known = content - unknown
        covered = f"{known}/{content}" if content > 0 else "0/0"

        parts.append("")
        parts.append("[summary]")
        parts.append(f"  final_score:  {result['score_10']} / 10")
        parts.append(f"  lexical:      {lex:.4f}  ({result['lexical_score_10']}/10)  → contribution {lex * 0.5:.4f}")
        parts.append(f"  structure:    {struc:.4f}  ({result['structure_score_10']}/10)  → contribution {struc * 0.5:.4f}")
        parts.append(f"  negation:     {neg:.4f}  ({result['negation_score_10']}/10)  → bonus        {neg * 0.2:.4f}")
        parts.append(f"  coverage:     {covered} lexical words matched, unknown={unknown}")

        parts.append("")
        parts.append("[morph trace]")
        parts.append(_format_morph_trace(result["sentence"]))

        parts.append("")
        parts.append("[lexical]")
        parts.append(f"  lexical units: {content} → capped: {result['lexical_unit_count_capped']}")
        sorted_words = sorted(result["scored_words"], key=lambda w: w["difficulty"], reverse=True)
        parts.append("  top words:")
        for w in sorted_words:
            parts.append(f"    {w['lemma']}/{w['pos']:<4}  {w['difficulty']:.4f}   {w['match_method']}")
        parts.append("  formula:")
        lw = lp.get("lexical_weights", {"mean_all": 0.25, "mean_top_n": 0.50, "max": 0.25})
        parts.append(
            f"    {lw['mean_all']}×mean_all({lp['mean_all']}) + {lw['mean_top_n']}×mean_top5({lp['mean_top_n']}) + {lw['max']}×max({lp['max']})"
        )
        parts.append(f"    = {lex:.4f}")

        parts.append("")
        parts.append("[structure]")
        parts.append(f"  score={struc:.4f}")
        active = _active_features(sp)
        if active:
            parts.append(f"  active features: {', '.join(active)}")
        else:
            parts.append("  active features: none")
        parts.append("  reason:")
        parts.extend(_structure_reasons(sp))
        parts.append("  logical spans:")
        for match in sp.get("logical_matches", []) + sp.get("strong_ending_matches", []):
            parts.append(f"    {match['label']}  weight={match['weight']}  chars={match['start']}:{match['end']}")
        if not sp.get("logical_matches") and not sp.get("strong_ending_matches"):
            parts.append("    none")

        parts.append("")
        parts.append("[negation]")
        if nd["negation_count_total"] > 0:
            hits = []
            if nd["local_negation_score"] > 0:
                hits.append(f"local={nd['local_negation_score']}")
            if nd["construction_negation_score"] > 0:
                hits.append(f"construction={nd['construction_negation_score']}")
            if nd["embedded_negation_score"] > 0:
                hits.append(f"embedded={nd['embedded_negation_score']}")
            if nd["negation_density_score"] > 0:
                hits.append(f"density={nd['negation_density_score']}")
            parts.append(f"  {nd['negation_count_total']} negation markers: {', '.join(hits)} → max={nd['negation_score']}")
        else:
            parts.append("  no negation markers detected")
        parts.append("  clause boundaries:")
        for match in nd.get("boundary_matches", []):
            parts.append(f"    {match['kind']}:{match['label']}  chars={match['start']}:{match['end']}")
        if not nd.get("boundary_matches"):
            parts.append("    none")

        parts.append("")
        parts.append("[warnings]")
        warnings = []
        if unknown > 0:
            warnings.append(f"  {unknown} unknown word(s) → reliability={result['reliability']}")
        if not warnings:
            warnings.append("  none")
        parts.extend(warnings)

    else:
        parts.append(f"  score_10:        {result['score_10']}")
        parts.append(f"  reliability:     {result['reliability']}")
        parts.append(f"  lexical_score:   {result['lexical_score_10']}")
        parts.append(f"  structure_score: {result['structure_score_10']}")
        parts.append(f"  negation_score:  {result['negation_score_10']}")
        parts.append(f"  lexical_units:   {result['lexical_unit_count']}")
        parts.append(f"  structure_words: {result['structure_content_token_count']}")
        parts.append(f"  unknown_units:   {result['unknown_lexical_unit_count']}")

    return "\n".join(parts)


def score_sentence(scorer: SentenceScorer, sentence: str, debug: bool = False) -> None:
    result = scorer.score(sentence)
    print(format_result(result, debug=debug))
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="한국어 문장 난이도 측정",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "사용 예:\n"
            "  %(prog)s \"문장을 분석한다.\"\n"
            "  %(prog)s --file sentences.txt\n"
            "  %(prog)s --debug \"문장을 분석한다.\"\n"
            "  %(prog)s                    # interactive mode\n"
        ),
    )
    parser.add_argument(
        "sentence",
        nargs="?",
        default=None,
        help="점수를 측정할 문장 (따옴표로 감싸기)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default=None,
        help="문장이 한 줄씩 적힌 텍스트 파일 경로",
    )
    parser.add_argument(
        "--lexicon",
        "-l",
        type=str,
        default=None,
        help="lexicon_master.csv 경로 (기본: data/processed/lexicon_master.csv)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="점수 세부 구성 요소 출력",
    )

    args = parser.parse_args()

    if args.sentence is not None and args.file is not None:
        parser.error("sentence와 --file은 동시에 사용할 수 없습니다.")

    default_lexicon_path = PROJECT_ROOT / "data/processed/lexicon_master.csv"
    lexicon_path = Path(args.lexicon) if args.lexicon else default_lexicon_path

    config = LexiconConfig(lexicon_path=lexicon_path)
    scorer = SentenceScorer(config)

    if args.sentence is not None:
        score_sentence(scorer, args.sentence, debug=args.debug)
        return

    if args.file is not None:
        path = Path(args.file)
        if not path.exists():
            print(f"파일을 찾을 수 없습니다: {path}", file=sys.stderr)
            sys.exit(1)

        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            stripped = line.strip()
            if stripped:
                score_sentence(scorer, stripped, debug=args.debug)
        return

    print("문장을 입력하세요 (빈 줄 또는 EOF로 종료):")
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            break
        score_sentence(scorer, stripped, debug=args.debug)


if __name__ == "__main__":
    main()
