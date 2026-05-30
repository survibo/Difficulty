"""
lexicon_builder.py

두 어휘 목록을 병합해 문장 난이도 측정용 마스터 어휘 사전
`data/processed/lexicon_master.csv`를 생성한다.

입력:
- data/raw/vocab_5965.xls
  - 첫 번째 시트 사용: sheet_name=0
  - 예상 컬럼: 순위, 단어, 품사, 풀이, 등급

- data/raw/vocab_40k.xlsx
  - 여섯 번째 시트 사용: sheet_name=5
  - 예상 컬럼: 등급, 어휘, 동형어번호, 품사, 어종, 원어, 의미, 분야

핵심 설계:
- 4만 개 5등급 목록을 메인 난도 기준으로 사용한다.
- 5965개 목록은 보조 기준으로만 약하게 반영한다.
- 5965 등급은 A/B = 쉬움, C = 2등급성 보조값으로 처리한다.
- 병합 기준은 lemma + homograph_no + pos_norm을 우선 사용한다.
- 병합 실패 시 lemma + homograph_no 기준으로 보조 병합을 시도한다.
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
    grade5965_to_aux_difficulty,
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
    rank_to_difficulty,
    safe_float,
    safe_int,
    split_homograph_suffix,
    split_light_predicate_suffix,
    weighted_available,
)


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class LexiconBuildConfig:
    vocab_5965_path: str | Path = "data/raw/vocab_5965.xls"
    vocab_40k_path: str | Path = "data/raw/vocab_40k.xlsx"
    output_path: str | Path = "data/processed/lexicon_master.csv"

    # pandas 기준:
    # 첫 번째 시트 = 0
    # 여섯 번째 시트 = 5
    vocab_5965_sheet_name: int | str = 0
    vocab_40k_sheet_name: int | str = 5

    header: int = 0
    encoding: str = "utf-8-sig"

    # 최종 확정 가중치.
    # 4만 목록을 강하게 신뢰하고, 5965는 약하게만 반영한다.
    weight_grade5: float = 0.80
    weight_5965_aux: float = 0.10
    weight_rank: float = 0.05
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

    # 공백 제거 후 비교
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
# 5965 grade label handling
# ---------------------------------------------------------------------


def normalize_5965_grade_label(grade_value: Any) -> str:
    """
    5965 등급 원값을 보존하되 비교하기 쉽게 정규화한다.

    확정 기준:
    - A/B는 쉬운 어휘 그룹
    - C는 2등급성 보조값
    """
    if is_missing(grade_value):
        return ""

    text = str(grade_value).strip().upper()

    if text in {"A", "B", "C"}:
        return text

    numeric = safe_int(text)
    if numeric == 1:
        return "A/B"
    if numeric in {2, 3}:
        return "C"

    return text


# ---------------------------------------------------------------------
# Input loaders
# ---------------------------------------------------------------------


def _read_excel_file(
    path: Path,
    *,
    sheet_name: int | str,
    header: int,
) -> pd.DataFrame:
    """
    파일 확장자에 맞는 pandas Excel 엔진으로 읽는다.

    - .xlsx/.xlsm: openpyxl
    - .xls: xlrd
    """
    suffix = path.suffix.lower()

    if suffix == ".xls":
        try:
            import xlrd
        except ImportError as exc:
            raise ImportError(
                f"{path} 파일은 .xls 형식이라 xlrd 패키지가 필요합니다. "
                "현재 활성화된 venv에서 다음 명령으로 설치하세요: "
                "python -m pip install xlrd"
            ) from exc

        engine = "xlrd"
    elif suffix in {".xlsx", ".xlsm"}:
        engine = "openpyxl"
    else:
        engine = None

    return pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=header,
        engine=engine,
    )


def load_vocab_40k(config: LexiconBuildConfig) -> pd.DataFrame:
    """
    4만 개 5등급 어휘 목록을 읽고 표준 컬럼으로 변환한다.
    """
    path = Path(config.vocab_40k_path)

    if not path.exists():
        raise FileNotFoundError(f"4만 어휘 파일을 찾지 못했습니다: {path}")

    df = _read_excel_file(
        path,
        sheet_name=config.vocab_40k_sheet_name,
        header=config.header,
    )
    df = _normalize_dataframe_columns(df)

    grade_col = _find_column(df, ["등급", "어휘등급", "급수"], table_name="vocab_40k")
    lemma_col = _find_column(df, ["어휘", "단어", "표제어"], table_name="vocab_40k")
    homograph_col = _find_column(
        df,
        ["동형어번호", "동형어 번호", "동형 번호", "동형어"],
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

    if homograph_col:
        cleaned["homograph_no"] = df[homograph_col].map(parse_homograph_no)
    else:
        cleaned["homograph_no"] = 0

    cleaned["pos_40k"] = df[pos_col].map(normalize_pos)
    cleaned["pos_norm"] = cleaned["pos_40k"]

    cleaned["grade_5"] = df[grade_col].map(parse_grade5)

    cleaned["origin"] = (
        df[origin_col].map(normalize_origin)
        if origin_col
        else ""
    )
    cleaned["original_form"] = (
        df[original_col].map(lambda x: "" if is_missing(x) else str(x).strip())
        if original_col
        else ""
    )
    cleaned["meaning"] = (
        df[meaning_col].map(lambda x: "" if is_missing(x) else str(x).strip())
        if meaning_col
        else ""
    )
    cleaned["domain"] = (
        df[domain_col].map(normalize_domain)
        if domain_col
        else ""
    )

    cleaned["source_40k"] = True

    cleaned = cleaned[cleaned["lemma"].map(is_valid_lemma)].copy()

    # 같은 의미 항목이 완전히 중복된 경우 제거.
    cleaned = cleaned.drop_duplicates(
        subset=[
            "lemma",
            "homograph_no",
            "pos_norm",
            "grade_5",
            "origin",
            "original_form",
            "meaning",
            "domain",
        ],
        keep="first",
    ).reset_index(drop=True)

    cleaned.insert(0, "main_id", range(len(cleaned)))

    return cleaned


def load_vocab_5965(config: LexiconBuildConfig) -> pd.DataFrame:
    """
    5965개 학습용 어휘 목록을 읽고 표준 컬럼으로 변환한다.
    """
    path = Path(config.vocab_5965_path)

    if not path.exists():
        raise FileNotFoundError(f"5965 어휘 파일을 찾지 못했습니다: {path}")

    df = _read_excel_file(
        path,
        sheet_name=config.vocab_5965_sheet_name,
        header=config.header,
    )
    df = _normalize_dataframe_columns(df)

    rank_col = _find_column(df, ["순위", "랭크", "rank"], required=False, table_name="vocab_5965")
    word_col = _find_column(df, ["단어", "어휘", "표제어"], table_name="vocab_5965")
    pos_col = _find_column(df, ["품사"], table_name="vocab_5965")
    gloss_col = _find_column(df, ["풀이", "뜻풀이", "의미"], required=False, table_name="vocab_5965")
    grade_col = _find_column(df, ["등급", "급수"], table_name="vocab_5965")

    lemma_and_homograph = df[word_col].map(split_homograph_suffix)

    cleaned = pd.DataFrame()
    cleaned["lemma"] = [item[0] for item in lemma_and_homograph]
    cleaned["homograph_no"] = [item[1] for item in lemma_and_homograph]

    cleaned["pos_5965"] = df[pos_col].map(normalize_pos)
    cleaned["pos_norm"] = cleaned["pos_5965"]

    if rank_col:
        cleaned["rank_5965"] = df[rank_col].map(lambda x: safe_float(x, default=np.nan))
    else:
        cleaned["rank_5965"] = np.nan

    cleaned["grade_5965_raw"] = df[grade_col].map(normalize_5965_grade_label)

    # normalize.py의 확정 기준 사용:
    # A -> 0.00, B -> 0.00, C -> 0.25
    cleaned["aux_5965_diff"] = df[grade_col].map(grade5965_to_aux_difficulty)

    cleaned["gloss_5965"] = (
        df[gloss_col].map(lambda x: "" if is_missing(x) else str(x).strip())
        if gloss_col
        else ""
    )

    cleaned["source_5965"] = True

    cleaned = cleaned[cleaned["lemma"].map(is_valid_lemma)].copy()

    cleaned = cleaned.drop_duplicates(
        subset=[
            "lemma",
            "homograph_no",
            "pos_norm",
            "rank_5965",
            "grade_5965_raw",
            "aux_5965_diff",
            "gloss_5965",
        ],
        keep="first",
    ).reset_index(drop=True)

    cleaned.insert(0, "aux_id", range(len(cleaned)))

    return cleaned


# ---------------------------------------------------------------------
# Merge helpers
# ---------------------------------------------------------------------


def _make_exact_aux_table(aux_df: pd.DataFrame) -> pd.DataFrame:
    """
    exact merge용 5965 테이블을 만든다.

    같은 lemma + homograph_no + pos_norm에 여러 후보가 있으면
    순위가 낮은 항목을 우선한다.
    """
    if aux_df.empty:
        return aux_df.copy()

    out = aux_df.copy()

    out["_rank_sort"] = out["rank_5965"].fillna(float("inf"))
    out["_aux_diff_sort"] = out["aux_5965_diff"].fillna(float("inf"))

    out = out.sort_values(
        by=["lemma", "homograph_no", "pos_norm", "_rank_sort", "_aux_diff_sort"],
        ascending=[True, True, True, True, True],
        kind="mergesort",
    )

    out = out.drop_duplicates(
        subset=["lemma", "homograph_no", "pos_norm"],
        keep="first",
    )

    out = out.drop(columns=["_rank_sort", "_aux_diff_sort"])

    return out.reset_index(drop=True)


def _make_relaxed_aux_table(aux_df: pd.DataFrame) -> pd.DataFrame:
    """
    lemma + homograph_no 기준으로 보조 병합할 수 있는 5965 테이블 생성.

    같은 lemma + homograph_no에 여러 후보가 있으면 무리하게 하나로 고르지 않는다.
    후보가 정확히 하나뿐인 경우만 relaxed match에 사용한다.
    """
    if aux_df.empty:
        return aux_df.copy()

    exact_aux = _make_exact_aux_table(aux_df)

    key_cols = ["lemma", "homograph_no"]

    counts = exact_aux.groupby(key_cols).size().reset_index(name="candidate_count")
    unique_keys = counts[counts["candidate_count"] == 1][key_cols]

    relaxed = exact_aux.merge(unique_keys, on=key_cols, how="inner")

    return relaxed.copy()


def _merge_main_with_aux(
    main_df: pd.DataFrame,
    aux_df: pd.DataFrame,
) -> tuple[pd.DataFrame, set[int]]:
    """
    4만 목록을 중심으로 5965 보조 정보를 병합한다.

    1차:
    - lemma + homograph_no + pos_norm exact match

    2차:
    - exact match 실패 row에 한해
    - lemma + homograph_no 기준으로 5965 후보가 정확히 하나일 때만 relaxed match
    """
    exact_keys = ["lemma", "homograph_no", "pos_norm"]

    aux_cols = [
        "aux_id",
        "lemma",
        "homograph_no",
        "pos_norm",
        "pos_5965",
        "rank_5965",
        "grade_5965_raw",
        "aux_5965_diff",
        "gloss_5965",
        "source_5965",
    ]

    exact_aux = _make_exact_aux_table(aux_df)

    merged = main_df.merge(
        exact_aux[aux_cols],
        on=exact_keys,
        how="left",
        suffixes=("", "_aux"),
    )

    merged["match_method"] = np.where(
        merged["aux_id"].notna(),
        "exact:lemma+homograph+pos",
        "",
    )

    no_aux_mask = merged["aux_id"].isna()

    if no_aux_mask.any():
        relaxed_aux = _make_relaxed_aux_table(aux_df)

        relaxed_cols = [
            "aux_id",
            "lemma",
            "homograph_no",
            "pos_5965",
            "rank_5965",
            "grade_5965_raw",
            "aux_5965_diff",
            "gloss_5965",
            "source_5965",
        ]

        relaxed_matches = main_df.loc[
            no_aux_mask.values,
            ["main_id", "lemma", "homograph_no"],
        ].merge(
            relaxed_aux[relaxed_cols],
            on=["lemma", "homograph_no"],
            how="left",
            suffixes=("", "_relaxed"),
        )

        relaxed_matches = relaxed_matches.set_index("main_id")

        for idx, row in merged.loc[no_aux_mask].iterrows():
            main_id = row["main_id"]

            if main_id not in relaxed_matches.index:
                continue

            relaxed_row = relaxed_matches.loc[main_id]

            # 혹시 같은 main_id가 DataFrame으로 온 경우 방어.
            if isinstance(relaxed_row, pd.DataFrame):
                if len(relaxed_row) != 1:
                    continue
                relaxed_row = relaxed_row.iloc[0]

            if pd.isna(relaxed_row.get("aux_id")):
                continue

            for col in [
                "aux_id",
                "pos_5965",
                "rank_5965",
                "grade_5965_raw",
                "aux_5965_diff",
                "gloss_5965",
                "source_5965",
            ]:
                merged.at[idx, col] = relaxed_row.get(col)

            merged.at[idx, "match_method"] = "relaxed:lemma+homograph"

    matched_aux_ids = {
        int(x)
        for x in merged["aux_id"].dropna().tolist()
    }

    return merged, matched_aux_ids


def _make_aux_only_rows(
    aux_df: pd.DataFrame,
    matched_aux_ids: set[int],
) -> pd.DataFrame:
    """
    4만 목록에는 없고 5965 목록에만 남은 항목을 최종 사전에 추가한다.
    """
    aux_only = aux_df[~aux_df["aux_id"].isin(matched_aux_ids)].copy()

    if aux_only.empty:
        return pd.DataFrame()

    out = pd.DataFrame()
    out["main_id"] = np.nan
    out["aux_id"] = aux_only["aux_id"]

    out["lemma"] = aux_only["lemma"]
    out["homograph_no"] = aux_only["homograph_no"]

    out["pos_40k"] = ""
    out["pos_5965"] = aux_only["pos_5965"]
    out["pos_norm"] = aux_only["pos_norm"]

    out["grade_5"] = np.nan
    out["origin"] = ""
    out["original_form"] = ""
    out["meaning"] = ""
    out["domain"] = ""

    out["rank_5965"] = aux_only["rank_5965"]
    out["grade_5965_raw"] = aux_only["grade_5965_raw"]
    out["aux_5965_diff"] = aux_only["aux_5965_diff"]
    out["gloss_5965"] = aux_only["gloss_5965"]

    out["source_40k"] = False
    out["source_5965"] = True
    out["match_method"] = "aux_only"

    return out.reset_index(drop=True)


# ---------------------------------------------------------------------
# Difficulty calculation
# ---------------------------------------------------------------------


def _safe_grade5_diff(value: Any) -> Optional[float]:
    if is_missing(value):
        return None
    return grade5_to_difficulty(value)


def _safe_rank_diff(rank: Any, max_rank: Any) -> Optional[float]:
    if is_missing(rank):
        return None
    return rank_to_difficulty(rank, max_rank)


def _origin_domain_signal_or_none(row: pd.Series) -> Optional[float]:
    origin = row.get("origin")
    domain = row.get("domain")

    if is_missing(origin) and is_missing(domain):
        return None

    return origin_domain_signal(
        origin=origin,
        domain=domain,
    )


def _difficulty_basis(row: pd.Series) -> str:
    parts: list[str] = []

    if not is_missing(row.get("grade5_diff")):
        parts.append("grade_5")
    if not is_missing(row.get("aux_5965_diff")):
        parts.append("vocab_5965")
    if not is_missing(row.get("rank_diff")):
        parts.append("rank_5965")

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


def _source_priority(row: pd.Series) -> int:
    has_40k = _as_bool(row.get("source_40k"))
    has_5965 = _as_bool(row.get("source_5965"))

    if has_40k and has_5965:
        return 0
    if has_40k:
        return 1
    if has_5965:
        return 2
    return 3


def _choose_derivation_base_row(base_rows: pd.DataFrame) -> Optional[pd.Series]:
    """
    하다/되다/시키다 파생어 보정에 사용할 base lemma 대표 행을 고른다.
    """
    if base_rows.empty:
        return None

    candidates = base_rows.copy()
    difficulty_col = (
        "difficulty"
        if "difficulty" in candidates.columns
        else "raw_difficulty"
        if "raw_difficulty" in candidates.columns
        else None
    )

    candidates["_base_pos_priority"] = candidates["pos_norm"].map(
        lambda value: 0 if _has_derivation_base_pos(value) else 1
    )
    candidates["_source_priority"] = candidates.apply(_source_priority, axis=1)
    candidates["_rank_missing_priority"] = candidates["rank_5965"].map(
        lambda value: 1 if is_missing(value) else 0
    )
    candidates["_rank_sort"] = candidates["rank_5965"].map(
        lambda value: safe_float(value, default=float("inf"))
    )
    candidates["_difficulty_sort"] = (
        candidates[difficulty_col].map(lambda value: safe_float(value, default=float("inf")))
        if difficulty_col
        else float("inf")
    )
    candidates["_homograph_sort"] = candidates["homograph_no"].map(parse_homograph_no)

    sorted_candidates = candidates.sort_values(
        by=[
            "_base_pos_priority",
            "_source_priority",
            "_rank_missing_priority",
            "_rank_sort",
            "_difficulty_sort",
            "_homograph_sort",
        ],
        ascending=[True, True, True, True, True, True],
        kind="mergesort",
    )

    return sorted_candidates.iloc[0]


def adjust_derivational_difficulty(
    df: pd.DataFrame,
    config: LexiconBuildConfig,
) -> pd.DataFrame:
    """
    X하다/X되다/X시키다 파생 표제어의 난도를 base lemma 기준으로 완화한다.
    """
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
    grade_5, 5965 보조등급, 순위, 어종/분야를 바탕으로 difficulty를 계산한다.

    최종 확정 가중치:
    - 4만 5등급 기반 난도: 0.80
    - 5965 보조 난도: 0.10
    - 5965 순위 기반 난도: 0.05
    - 어종/분야 신호: 0.05
    """
    out = df.copy()

    max_rank = safe_float(out["rank_5965"].max(), default=None)

    out["grade5_diff"] = out["grade_5"].map(_safe_grade5_diff)
    out["rank_diff"] = out["rank_5965"].map(lambda x: _safe_rank_diff(x, max_rank))

    out["origin_domain_signal"] = out.apply(_origin_domain_signal_or_none, axis=1)

    difficulties: list[float] = []

    for _, row in out.iterrows():
        base_values = [
            row.get("grade5_diff"),
            row.get("aux_5965_diff"),
            row.get("rank_diff"),
        ]

        has_primary_signal = any(
            value is not None and not is_missing(value)
            for value in base_values
        )

        if not has_primary_signal:
            difficulties.append(clamp(config.default_difficulty))
            continue

        base = weighted_available(
            values=[
                row.get("grade5_diff"),
                row.get("aux_5965_diff"),
                row.get("rank_diff"),
                row.get("origin_domain_signal"),
            ],
            weights=[
                config.weight_grade5,
                config.weight_5965_aux,
                config.weight_rank,
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
    has_40k = _as_bool(row.get("source_40k"))
    has_5965 = _as_bool(row.get("source_5965"))

    if has_40k and has_5965:
        return "both"
    if has_40k:
        return "vocab_40k_only"
    if has_5965:
        return "vocab_5965_only"

    return "unknown"


def finalize_lexicon(df: pd.DataFrame) -> pd.DataFrame:
    """
    최종 컬럼 순서와 타입을 정리한다.
    """
    out = df.copy()

    out["source"] = out.apply(_source_label, axis=1)

    # 대표 품사.
    # 4만 품사를 우선하고, 없으면 5965 품사를 사용한다.
    out["pos"] = out["pos_40k"].fillna("")
    out.loc[out["pos"].eq(""), "pos"] = out.loc[out["pos"].eq(""), "pos_5965"].fillna("")

    out["homograph_no"] = out["homograph_no"].map(parse_homograph_no)

    # 정렬 안정성을 위해 entry_id 생성.
    out = out.sort_values(
        by=[
            "lemma",
            "homograph_no",
            "pos",
            "source",
            "difficulty",
        ],
        ascending=[True, True, True, True, True],
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
        "pos_40k",
        "pos_5965",
        "grade_5",
        "grade_5965_raw",
        "rank_5965",
        "origin",
        "original_form",
        "meaning",
        "gloss_5965",
        "domain",
        "source",
        "match_method",
        "grade5_diff",
        "aux_5965_diff",
        "rank_diff",
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

    # 빈값 정리.
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
    두 어휘 엑셀을 읽어 lexicon_master.csv를 생성하고 DataFrame을 반환한다.
    """
    if config is None:
        config = LexiconBuildConfig()

    main_df = load_vocab_40k(config)
    aux_df = load_vocab_5965(config)

    merged_main, matched_aux_ids = _merge_main_with_aux(main_df, aux_df)
    aux_only = _make_aux_only_rows(aux_df, matched_aux_ids)

    if aux_only.empty:
        combined = merged_main.copy()
    else:
        combined = pd.concat([merged_main, aux_only], ignore_index=True, sort=False)

    combined = add_difficulty_columns(combined, config)
    final = finalize_lexicon(combined)

    output_path = Path(config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    final.to_csv(output_path, index=False, encoding=config.encoding)

    return final


def build_lexicon_from_paths(
    vocab_5965_path: str | Path = "data/raw/vocab_5965.xls",
    vocab_40k_path: str | Path = "data/raw/vocab_40k.xlsx",
    output_path: str | Path = "data/processed/lexicon_master.csv",
) -> pd.DataFrame:
    """
    경로만 직접 넘겨서 lexicon을 만들 때 사용하는 편의 함수.
    """
    config = LexiconBuildConfig(
        vocab_5965_path=vocab_5965_path,
        vocab_40k_path=vocab_40k_path,
        output_path=output_path,
    )
    return build_lexicon(config)


def summarize_lexicon(df: pd.DataFrame) -> dict[str, Any]:
    """
    생성된 lexicon의 간단한 요약 통계를 반환한다.
    """
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
    """
    python -m sentdiff.lexicon_builder
    형태로 실행 가능.
    """
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
