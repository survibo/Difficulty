from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from sentdiff.lexicon_builder import build_lexicon, summarize_lexicon


def main():
    df = build_lexicon()
    summary = summarize_lexicon(df)

    print("lexicon_master.csv 생성 완료")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
