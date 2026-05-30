"""
python scripts/02_score_sentences.py "문장을 분석한다."
python scripts/02_score_sentences.py --file data/sentences.txt
python scripts/02_score_sentences.py --debug "문장을 분석한다."
python scripts/02_score_sentences.py          # interactive mode (Ctrl+Z/Ctrl+D to exit)
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from sentdiff.lexical import LexiconConfig
from sentdiff.pipeline import SentenceScorer


def format_result(result: dict, debug: bool = False) -> str:
    lp = result["score_parts"]
    sp = result["structure_parts"]

    parts = [
        f"  sentence:        {result['sentence']}",
        f"  score_10:        {result['score_10']}",
        f"  lexical_score:   {result['lexical_score_10']}",
        f"  structure_score: {result['structure_score_10']}",
        f"  content_words:   {result['content_token_count']}",
        f"  unknown_words:   {result['unknown_token_count']}",
    ]

    if debug:
        parts.append("")
        parts.append("  [lexical_parts]")
        parts.append(f"    mean_all:   {lp['mean_all']}")
        parts.append(f"    mean_top_n: {lp['mean_top_n']}")
        parts.append(f"    max:        {lp['max']}")

        parts.append("  [structure_parts]")
        for key in ("length_score", "predicate_score", "embedding_score",
                     "connective_score", "logical_score", "modifier_score",
                     "derivational_score"):
            parts.append(f"    {key}: {sp[key]}")
        parts.append(f"    content_token_count:         {sp['content_token_count']}")
        parts.append(f"    predicate_count:             {sp['predicate_count']}")
        parts.append(f"    ending_count:                {sp['ending_count']}")
        parts.append(f"    connective_ending_count:     {sp['connective_ending_count']}")
        parts.append(f"    adnominal_count:             {sp['adnominal_count']}")
        parts.append(f"    nominalizer_count:           {sp['nominalizer_count']}")
        parts.append(f"    logical_marker_weighted:     {sp['logical_marker_weighted']}")
        parts.append(f"    logical_marker_count:        {sp['logical_marker_count']}")
        parts.append(f"    strong_logical_ending_w:     {sp['strong_logical_ending_weighted']}")
        parts.append(f"    strong_logical_ending_cnt:   {sp['strong_logical_ending_count']}")
        parts.append(f"    weak_connective_w:           {sp['weak_connective_weighted']}")
        parts.append(f"    weak_connective_cnt:         {sp['weak_connective_count']}")
        parts.append(f"    derivational_suffix_count:   {sp['derivational_suffix_count']}")
        parts.append(f"    max_noun_chain:              {sp['max_noun_chain']}")

    if result["scored_words"]:
        word_lines = []
        for w in result["scored_words"]:
            word_lines.append(
                f"    {w['surface']:<12} {w['difficulty']:<8.4f} "
                f"{w['match_method']:<16} (id={w['matched_entry_id']})"
            )
        parts.append("  scored_words:")
        parts.extend(word_lines)

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
