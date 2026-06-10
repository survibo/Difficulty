"""
lexicon_master.csv의 두 번째 열(lemma)을 검색하고 CSV 위치를 출력한다.

python scripts/03_find_lexicon.py "유동성"
python scripts/03_find_lexicon.py "유동" --contains
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import NamedTuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEXICON = PROJECT_ROOT / "data" / "processed" / "lexicon_master.csv"


class LexiconMatch(NamedTuple):
    path: Path
    line_number: int
    row: dict[str, str]


def find_rows(path: str | Path, query: str, contains: bool = False) -> list[LexiconMatch]:
    csv_path = Path(path)
    matches: list[LexiconMatch] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            fieldnames = next(reader)
        except StopIteration as exc:
            raise ValueError("lexicon CSV is empty") from exc

        if len(fieldnames) < 2 or fieldnames[1] != "lemma":
            actual = fieldnames[1] if len(fieldnames) >= 2 else "(missing)"
            raise ValueError(f"second column must be 'lemma' (got {actual!r})")

        while True:
            line_number = reader.line_num + 1
            try:
                values = next(reader)
            except StopIteration:
                break

            row = dict(zip(fieldnames, values))
            lemma = row.get("lemma", "")
            matched = query in lemma if contains else query == lemma
            if matched:
                matches.append(LexiconMatch(csv_path, line_number, row))

    return matches


def _format_value(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\n    ")


def format_match(match: LexiconMatch) -> str:
    lines = [f"{match.path}:{match.line_number}"]
    for key, value in match.row.items():
        if value:
            lines.append(f"  {key}: {_format_value(value)}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="lexicon_master.csv의 두 번째 열(lemma) 위치 검색",
    )
    parser.add_argument("word", help="검색할 lemma")
    parser.add_argument(
        "--contains",
        action="store_true",
        help="정확 일치 대신 lemma 부분 일치 검색",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_LEXICON,
        help=f"검색할 CSV 경로 (기본: {DEFAULT_LEXICON.relative_to(PROJECT_ROOT)})",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        matches = find_rows(args.file, args.word, contains=args.contains)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not matches:
        mode = "contains" if args.contains else "exact"
        print(f"not found: {args.word!r} ({mode})")
        return 1

    print(f"{len(matches)} match(es)")
    for index, match in enumerate(matches):
        if index:
            print()
        print(format_match(match))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
