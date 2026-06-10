from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "03_find_lexicon.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("find_lexicon", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FindLexiconTest(unittest.TestCase):
    def setUp(self) -> None:
        self.module = _load_module()
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False, newline="",
        )
        handle.write(
            "entry_id,lemma,difficulty,pos,meaning\n"
            "1,가,0.0,명사,첫 항목\n"
            "2,유동성,0.7,명사,흐르는 성질\n"
            "3,유동,0.4,명사,흐름\n"
            "4,유동성,0.8,명사,자금화 가능성\n"
        )
        handle.close()
        self.path = Path(handle.name)

    def tearDown(self) -> None:
        self.path.unlink(missing_ok=True)

    def test_exact_match_returns_all_rows_and_csv_line_numbers(self) -> None:
        matches = self.module.find_rows(self.path, "유동성")

        self.assertEqual([item.line_number for item in matches], [3, 5])
        self.assertEqual([item.row["entry_id"] for item in matches], ["2", "4"])

    def test_contains_match_returns_partial_matches(self) -> None:
        matches = self.module.find_rows(self.path, "유동", contains=True)

        self.assertEqual([item.row["lemma"] for item in matches], ["유동성", "유동", "유동성"])

    def test_line_number_points_to_start_of_multiline_csv_record(self) -> None:
        multiline_path = self.path.with_name(self.path.stem + "_multiline.csv")
        multiline_path.write_text(
            'entry_id,lemma,difficulty,pos,meaning\n'
            '1,앞단어,0.1,명사,"첫 줄\n둘째 줄"\n'
            '2,찾을단어,0.5,명사,뜻\n',
            encoding="utf-8",
        )
        self.addCleanup(multiline_path.unlink, missing_ok=True)

        matches = self.module.find_rows(multiline_path, "찾을단어")

        self.assertEqual(matches[0].line_number, 4)

    def test_second_column_must_be_lemma(self) -> None:
        bad_path = self.path.with_name(self.path.stem + "_bad.csv")
        bad_path.write_text("entry_id,word,difficulty\n1,유동성,0.7\n", encoding="utf-8")
        self.addCleanup(bad_path.unlink, missing_ok=True)

        with self.assertRaisesRegex(ValueError, "second column must be 'lemma'"):
            self.module.find_rows(bad_path, "유동성")

    def test_format_match_includes_location_and_main_fields(self) -> None:
        match = self.module.find_rows(self.path, "유동성")[0]

        output = self.module.format_match(match)

        self.assertIn(f"{self.path}:3", output)
        self.assertIn("entry_id: 2", output)
        self.assertIn("lemma: 유동성", output)
        self.assertIn("difficulty: 0.7", output)
        self.assertIn("meaning: 흐르는 성질", output)


if __name__ == "__main__":
    unittest.main()
