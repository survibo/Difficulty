"""
lexicon_builder.py

4만 개 5등급 어휘 목록(vocab_40k.xlsx)을 읽어
문장 난이도 측정용 마스터 어휘 사전 `data/processed/lexicon_master.csv`를 생성한다.

입력:
- data/raw/vocab_40k.xlsx
  - 여섯 번째 시트 사용: sheet_name=5
  - 예상 컬럼: 등급, 어휘, 표준동형어번호수정, 품사, 어종, 원어, 의미, 분야

핵심 설계:
- 4만 개 5등급 목록을 난도 기준으로 사용한다.
- grade_5 → difficulty 매핑으로 기본 난도 결정.
- 어종/분야 신호로 미세 보정.
- 하다/되다/시키다 파생어는 base lemma 난도로 완화.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pandas as pd

from .normalize import (
    clamp,
    grade5_to_difficulty,
    is_missing,
    is_valid_lemma,
    normalize_columns,
    normalize_domain,
    normalize_lemma,
    normalize_origin,
    normalize_pos,
    origin_domain_signal,
    parse_grade5,
    parse_homograph_no,
    safe_float,
    safe_int,
    split_light_predicate_suffix,
    weighted_available,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class LexiconBuildConfig:
    vocab_40k_path: str | Path = "data/raw/vocab_40k.xlsx"
    output_path: str | Path = "data/processed/lexicon_master.csv"

    vocab_40k_sheet_name: int | str = 5
    header: int = 0
    encoding: str = "utf-8-sig"

    # 최종 확정 가중치 — grade5 + origin/domain만 사용.
    weight_grade5: float = 0.95
    weight_origin_domain: float = 0.05

    # 정보가 전혀 부족한 경우의 기본 난도.
    default_difficulty: float = 0.30

    # 하다/되다/시키다 파생어 난도 보정.
    use_derivational_adjustment: bool = True
    derivational_base_weight: float = 0.60
    derivational_original_weight: float = 0.40
    derivational_max_drop: float = 0.35
    derivational_adjust_only_downward: bool = True


# ---------------------------------------------------------------------
# Column handling
# ---------------------------------------------------------------------


def _normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = normalize_columns(df.columns)
    return df


def _find_column(
    df: pd.DataFrame,
    aliases: Iterable[str],
    *,
    required: bool = True,
    table_name: str = "dataframe",
) -> Optional[str]:
    """
    여러 후보 이름 중 실제 DataFrame에 존재하는 컬럼명을 찾는다.
    """
    normalized_aliases = [str(a).strip() for a in aliases]

    for alias in normalized_aliases:
        if alias in df.columns:
            return alias

    compact_to_original = {
        str(col).replace(" ", ""): col
        for col in df.columns
    }

    for alias in normalized_aliases:
        compact = alias.replace(" ", "")
        if compact in compact_to_original:
            return compact_to_original[compact]

    if required:
        raise ValueError(
            f"{table_name}에서 필요한 컬럼을 찾지 못했습니다. "
            f"후보={normalized_aliases}, 실제 컬럼={list(df.columns)}"
        )

    return None


# ---------------------------------------------------------------------
# Input loader
# ---------------------------------------------------------------------


def _read_excel_file(
    path: Path,
    *,
    sheet_name: int | str,
    header: int,
) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        engine = "openpyxl"
    elif suffix == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise ImportError(
                f"{path} 파일은 .xls 형식이라 xlrd 패키지가 필요합니다. "
                "python -m pip install xlrd"
            ) from exc
        engine = "xlrd"
    else:
        engine = None
    return pd.read_excel(path, sheet_name=sheet_name, header=header, engine=engine)


def load_vocab_40k(config: LexiconBuildConfig) -> pd.DataFrame:
    """
    4만 개 5등급 어휘 목록을 읽고 표준 컬럼으로 변환한다.
    """
    path = Path(config.vocab_40k_path)
    if not path.exists():
        raise FileNotFoundError(f"4만 어휘 파일을 찾지 못했습니다: {path}")

    df = _read_excel_file(path, sheet_name=config.vocab_40k_sheet_name, header=config.header)
    df = _normalize_dataframe_columns(df)

    grade_col = _find_column(df, ["등급", "어휘등급", "급수"], table_name="vocab_40k")
    lemma_col = _find_column(df, ["어휘", "단어", "표제어"], table_name="vocab_40k")
    homograph_col = _find_column(
        df,
        ["표준동형어번호수정", "동형어번호", "동형어 번호", "동형 번호", "동형어"],
        required=False,
        table_name="vocab_40k",
    )
    pos_col = _find_column(df, ["품사"], table_name="vocab_40k")
    origin_col = _find_column(df, ["어종"], required=False, table_name="vocab_40k")
    original_col = _find_column(df, ["원어"], required=False, table_name="vocab_40k")
    meaning_col = _find_column(df, ["의미", "뜻풀이", "풀이"], required=False, table_name="vocab_40k")
    domain_col = _find_column(df, ["분야", "전문분야"], required=False, table_name="vocab_40k")

    cleaned = pd.DataFrame()
    cleaned["lemma"] = df[lemma_col].map(normalize_lemma)
    cleaned["homograph_no"] = df[homograph_col].map(parse_homograph_no) if homograph_col else 0
    cleaned["pos_norm"] = df[pos_col].map(normalize_pos)
    cleaned["grade_5"] = df[grade_col].map(parse_grade5)
    cleaned["origin"] = df[origin_col].map(normalize_origin) if origin_col else ""
    cleaned["original_form"] = df[original_col].map(lambda x: "" if is_missing(x) else str(x).strip()) if original_col else ""
    cleaned["meaning"] = df[meaning_col].map(lambda x: "" if is_missing(x) else str(x).strip()) if meaning_col else ""
    cleaned["domain"] = df[domain_col].map(normalize_domain) if domain_col else ""

    cleaned = cleaned[cleaned["lemma"].map(is_valid_lemma)].copy()
    cleaned = cleaned.drop_duplicates(
        subset=["lemma", "homograph_no", "pos_norm", "grade_5", "origin", "original_form", "meaning", "domain"],
        keep="first",
    ).reset_index(drop=True)
    cleaned.insert(0, "main_id", range(len(cleaned)))
    return cleaned


# ---------------------------------------------------------------------
# Difficulty calculation
# ---------------------------------------------------------------------


def _safe_grade5_diff(value: Any) -> Optional[float]:
    if is_missing(value):
        return None
    return grade5_to_difficulty(value)


def _origin_domain_signal_or_none(row: pd.Series) -> Optional[float]:
    origin = row.get("origin")
    domain = row.get("domain")
    if is_missing(origin) and is_missing(domain):
        return None
    return origin_domain_signal(origin=origin, domain=domain)


def _difficulty_basis(row: pd.Series) -> str:
    parts: list[str] = []
    if not is_missing(row.get("grade5_diff")):
        parts.append("grade_5")
    od_value = row.get("origin_domain_signal")
    if od_value is not None and not is_missing(od_value):
        try:
            if float(od_value) > 0:
                parts.append("origin_domain")
        except (TypeError, ValueError):
            pass
    if _as_bool(row.get("derivation_adjusted")):
        parts.append("derivation_adjusted")
    return "+".join(parts) if parts else "default"


def _has_derivation_base_pos(pos_value: Any) -> bool:
    text = "" if is_missing(pos_value) else str(pos_value)
    parts = {part.strip() for part in text.split("/") if part.strip()}
    return bool({"명사", "어근"} & parts)


def _choose_derivation_base_row(base_rows: pd.DataFrame) -> Optional[pd.Series]:
    if base_rows.empty:
        return None
    candidates = base_rows.copy()
    difficulty_col = (
        "difficulty" if "difficulty" in candidates.columns
        else "raw_difficulty" if "raw_difficulty" in candidates.columns
        else None
    )
    candidates["_base_pos_priority"] = candidates["pos_norm"].map(
        lambda value: 0 if _has_derivation_base_pos(value) else 1
    )
    candidates["_difficulty_sort"] = (
        candidates[difficulty_col].map(lambda value: safe_float(value, default=float("inf")))
        if difficulty_col else float("inf")
    )
    candidates["_homograph_sort"] = candidates["homograph_no"].map(parse_homograph_no)
    sorted_candidates = candidates.sort_values(
        by=["_base_pos_priority", "_difficulty_sort", "_homograph_sort"],
        ascending=[True, True, True],
        kind="mergesort",
    )
    return sorted_candidates.iloc[0]


def adjust_derivational_difficulty(
    df: pd.DataFrame,
    config: LexiconBuildConfig,
) -> pd.DataFrame:
    out = df.copy()
    out["derivation_base"] = ""
    out["derivation_suffix"] = ""
    out["derivation_penalty"] = np.nan
    out["derivation_base_difficulty"] = np.nan
    out["derivation_adjusted"] = False

    lemma_groups = {
        str(lemma): rows
        for lemma, rows in out.groupby("lemma", dropna=False)
        if not is_missing(lemma)
    }

    for idx, row in out.iterrows():
        split = split_light_predicate_suffix(row.get("lemma"))
        if split is None:
            continue
        base, suffix, penalty = split
        out.at[idx, "derivation_base"] = base
        out.at[idx, "derivation_suffix"] = suffix
        out.at[idx, "derivation_penalty"] = penalty
        if len(base) < 2:
            continue
        base_rows = lemma_groups.get(base)
        if base_rows is None or base_rows.empty:
            continue
        base_row = _choose_derivation_base_row(base_rows)
        if base_row is None:
            continue
        if not _has_derivation_base_pos(base_row.get("pos_norm")):
            continue
        raw_difficulty = safe_float(row.get("raw_difficulty"), default=None)
        base_difficulty = safe_float(base_row.get("difficulty"), default=None)
        if raw_difficulty is None or base_difficulty is None:
            continue
        out.at[idx, "derivation_base_difficulty"] = base_difficulty
        adjusted = (
            (base_difficulty * config.derivational_base_weight)
            + (raw_difficulty * config.derivational_original_weight)
            + penalty
        )
        max_drop = max(0.0, float(config.derivational_max_drop))
        adjusted = clamp(max(adjusted, raw_difficulty - max_drop))
        if config.derivational_adjust_only_downward and adjusted >= raw_difficulty:
            continue
        out.at[idx, "difficulty"] = adjusted
        out.at[idx, "derivation_adjusted"] = True

    return out


def add_difficulty_columns(
    df: pd.DataFrame,
    config: LexiconBuildConfig,
) -> pd.DataFrame:
    """
    grade_5 + origin/domain 신호를 바탕으로 difficulty를 계산한다.

    최종 확정 가중치:
    - 4만 5등급 기반 난도: 0.95
    - 어종/분야 신호: 0.05
    """
    out = df.copy()

    out["grade5_diff"] = out["grade_5"].map(_safe_grade5_diff)
    out["origin_domain_signal"] = out.apply(_origin_domain_signal_or_none, axis=1)

    difficulties: list[float] = []
    for _, row in out.iterrows():
        has_grade5 = row.get("grade5_diff") is not None and not is_missing(row.get("grade5_diff"))

        if not has_grade5:
            difficulties.append(clamp(config.default_difficulty))
            continue

        base = weighted_available(
            values=[
                row.get("grade5_diff"),
                row.get("origin_domain_signal"),
            ],
            weights=[
                config.weight_grade5,
                config.weight_origin_domain,
            ],
            default=config.default_difficulty,
        )
        if base is None:
            base = config.default_difficulty
        difficulties.append(clamp(float(base)))

    out["raw_difficulty"] = difficulties
    out["difficulty"] = out["raw_difficulty"]

    if config.use_derivational_adjustment:
        out = adjust_derivational_difficulty(out, config)

    out["difficulty_basis"] = out.apply(_difficulty_basis, axis=1)
    return out


# ---------------------------------------------------------------------
# Final formatting
# ---------------------------------------------------------------------


def _as_bool(value: Any) -> bool:
    if is_missing(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "y"}


def _source_label(row: pd.Series) -> str:
    return "vocab_40k_only"


def finalize_lexicon(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["source"] = out.apply(_source_label, axis=1)
    out["pos"] = out["pos_norm"].fillna("")
    out["homograph_no"] = out["homograph_no"].map(parse_homograph_no)

    out = out.sort_values(
        by=["lemma", "homograph_no", "pos", "difficulty"],
        ascending=[True, True, True, True],
        kind="mergesort",
    ).reset_index(drop=True)

    out.insert(0, "entry_id", range(1, len(out) + 1))

    final_columns = [
        "entry_id",
        "lemma",
        "difficulty",
        "raw_difficulty",
        "homograph_no",
        "pos",
        "pos_norm",
        "grade_5",
        "origin",
        "original_form",
        "meaning",
        "domain",
        "source",
        "grade5_diff",
        "origin_domain_signal",
        "derivation_base",
        "derivation_suffix",
        "derivation_penalty",
        "derivation_base_difficulty",
        "derivation_adjusted",
        "difficulty_basis",
    ]

    for col in final_columns:
        if col not in out.columns:
            out[col] = ""

    out = out[final_columns].copy()

    object_cols = out.select_dtypes(include=["object"]).columns
    for col in object_cols:
        out[col] = out[col].fillna("")

    return out


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def build_lexicon(
    config: Optional[LexiconBuildConfig] = None,
) -> pd.DataFrame:
    """
    4만 어휘 엑셀을 읽어 lexicon_master.csv를 생성하고 DataFrame을 반환한다.
    """
    if config is None:
        config = LexiconBuildConfig()

    main_df = load_vocab_40k(config)
    combined = add_difficulty_columns(main_df, config)
    final = finalize_lexicon(combined)

    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_path, index=False, encoding=config.encoding)

    return final


def build_lexicon_from_paths(
    vocab_40k_path: str | Path = "data/raw/vocab_40k.xlsx",
    output_path: str | Path = "data/processed/lexicon_master.csv",
) -> pd.DataFrame:
    config = LexiconBuildConfig(
        vocab_40k_path=vocab_40k_path,
        output_path=output_path,
    )
    return build_lexicon(config)


def summarize_lexicon(df: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "n_entries": int(len(df)),
        "n_unique_lemmas": int(df["lemma"].nunique()) if "lemma" in df.columns else 0,
        "source_counts": (
            df["source"].value_counts(dropna=False).to_dict()
            if "source" in df.columns
            else {}
        ),
        "difficulty_mean": (
            float(df["difficulty"].mean())
            if "difficulty" in df.columns and len(df) > 0
            else None
        ),
        "difficulty_min": (
            float(df["difficulty"].min())
            if "difficulty" in df.columns and len(df) > 0
            else None
        ),
        "difficulty_max": (
            float(df["difficulty"].max())
            if "difficulty" in df.columns and len(df) > 0
            else None
        ),
    }
    return summary


def main() -> None:
    config = LexiconBuildConfig()
    df = build_lexicon(config)
    summary = summarize_lexicon(df)

    print("lexicon_master.csv 생성 완료")
    print(f"- entries: {summary['n_entries']}")
    print(f"- unique lemmas: {summary['n_unique_lemmas']}")
    print(f"- source counts: {summary['source_counts']}")
    print(f"- difficulty mean: {summary['difficulty_mean']}")
    print(f"- difficulty min: {summary['difficulty_min']}")
    print(f"- difficulty max: {summary['difficulty_max']}")
    print(f"- output: {config.output_path}")


if __name__ == "__main__":
    main()
