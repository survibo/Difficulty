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
from sentdiff.structure import StructureConfig


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


def _format_raw(value: float | int) -> str:
    if isinstance(value, int) or float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _format_structure_table(sp: dict) -> list[str]:
    config = StructureConfig()
    logical_raw = (
        sp["logical_marker_weighted"]
        + sp["strong_logical_ending_weighted"]
    )
    rows = [
        ("length", sp["structure_content_token_count"], sp["length_score"], config.weight_length),
        ("predicate", sp["predicate_count"], sp["predicate_score"], config.weight_predicate),
        (
            "embedding",
            sp["adnominal_count"] + sp["nominalizer_count"] + sp["adverbial_ending_count"],
            sp["embedding_score"],
            config.weight_embedding,
        ),
        ("modifier", sp["noun_chain_raw"], sp["modifier_score"], config.weight_modifier),
        ("repetition", sp["repetition_raw"], sp["repetition_score"], config.weight_repetition),
        ("logical", logical_raw, sp["logical_score"], config.weight_logical),
        ("connective", sp["connective_ending_count"], sp["connective_score"], config.weight_connective),
    ]

    lines = [
        "  feature        raw       normalized  weight  contribution",
    ]
    for feature, raw, normalized, weight in rows:
        contribution = normalized * weight
        lines.append(
            f"  {feature:<14}{_format_raw(raw):<10}"
            f"{normalized:<12.2f}{weight:<8.2f}{contribution:.3f}"
        )
    return lines


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
        parts.append(
            f"    mean_all denominator: {lp.get('mean_all_count', result['lexical_unit_count_capped'])}"
            f" (excluded zero: {lp.get('mean_all_zero_excluded_count', 0)})"
        )
        parts.append(f"    = {lex:.4f}")

        parts.append("")
        parts.append("[structure]")
        parts.append(f"  score = {struc:.4f}")
        parts.extend(_format_structure_table(sp))

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
