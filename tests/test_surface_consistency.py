from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from sentdiff.structure import StructureConfig  # noqa: E402


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class DocumentationConsistencyTest(unittest.TestCase):
    def test_flow_embedding_formula_matches_config(self) -> None:
        flow = _read("flow.md")
        threshold = StructureConfig().embedding_full_score_at

        self.assertIn(f"score = min(1.0, raw / {threshold})", flow)
        self.assertIn(f"{threshold}개 이상 → 1.0.", flow)
        self.assertNotIn("score = min(1.0, raw / 5)", flow)

    def test_repetition_docs_match_lemma_policy_and_difficulty_adjustment(self) -> None:
        for path in ("flow.md", "src/sentdiff/structure.md"):
            with self.subTest(path=path):
                text = _read(path)
                self.assertIn("lemma", text)
                self.assertIn(
                    "max(0.10, min(0.5, difficulty / 1.5))",
                    text,
                )
                self.assertNotIn("effective_difficulty = max(difficulty, 0.05)", text)

    def test_lexical_example_includes_zero_in_top_five_mean(self) -> None:
        flow = _read("flow.md")

        self.assertIn(
            "mean_top_5 = (0.25 + 0.22 + 0.20 + 0.00) / 4 = **0.1675**",
            flow,
        )
        self.assertIn("lexical = 0.50×0.1675 + 0.25×0.1675 + 0.25×0.25 = **0.1881**", flow)

    def test_cli_documentation_uses_current_count_names(self) -> None:
        doc = _read("scripts/02_score_sentences.md")

        self.assertIn("lexical_units:", doc)
        self.assertIn("structure_words:", doc)
        self.assertIn("unknown_units:", doc)
        self.assertNotIn("content_words:", doc)
        self.assertNotIn("unknown_words:", doc)


class HtmlConsistencyTest(unittest.TestCase):
    def test_html_structure_weights_match_structure_config(self) -> None:
        html = _read("index.html")
        config = StructureConfig()
        expected = {
            "length": config.weight_length,
            "predicate": config.weight_predicate,
            "embedding": config.weight_embedding,
            "modifier": config.weight_modifier,
            "repetition": config.weight_repetition,
            "logical": config.weight_logical,
            "connective": config.weight_connective,
        }

        for name, weight in expected.items():
            with self.subTest(name=name):
                score_key = f"{name}_score"
                weight_pattern = rf"{weight:.2f}".rstrip("0") + "0?"
                object_pattern = rf"{score_key}:\s*{weight_pattern}\b"
                debug_pattern = rf'"{name}",[\s\S]{{0,500}}?,\s*{weight_pattern}\s*,?\s*\]'
                self.assertRegex(html, object_pattern)
                self.assertRegex(html, debug_pattern)


class CliFormattingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "scripts" / "02_score_sentences.py"
        spec = importlib.util.spec_from_file_location("score_sentences_cli", path)
        assert spec is not None and spec.loader is not None
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def test_plain_output_uses_current_count_names(self) -> None:
        result = {
            "sentence": "문장을 분석한다.",
            "score_10": 3.12,
            "reliability": 0.75,
            "lexical_score_10": 2.89,
            "structure_score_10": 3.67,
            "negation_score_10": 0.0,
            "lexical_unit_count": 4,
            "structure_content_token_count": 6,
            "unknown_lexical_unit_count": 1,
        }

        output = self.module.format_result(result)

        self.assertIn("lexical_units:   4", output)
        self.assertIn("structure_words: 6", output)
        self.assertIn("unknown_units:   1", output)
        self.assertNotIn("content_words:", output)
        self.assertNotIn("unknown_words:", output)


if __name__ == "__main__":
    unittest.main()
