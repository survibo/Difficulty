"""
normalize.py

한국어 문장 난이도 측정 프로젝트에서 공통으로 사용하는 정규화 유틸리티.

주요 역할:
- 엑셀/CSV에서 읽어 온 문자열 정리
- 5965 어휘 목록의 동형어번호 분리: 가격03 -> 가격, 3
- 4만 어휘 목록의 등급값 정리: 1등급 -> 1
- 5965 A/B/C 등급을 보조 난도 신호로 변환
- 품사명 정규화
- 어휘 난도 계산을 위한 등급/순위 변환
- 어종/분야 신호와 파생 표제어 suffix 처리

중요한 난도 정책:
- 4만 개 5등급 목록을 메인 기준으로 사용한다.
- 5965개 A/B/C 목록은 보조 기준으로만 사용한다.
- 5965 기준에서 A/B는 쉬운 어휘, C는 2등급성 보조값으로 본다.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Iterable, Optional, Sequence


# ---------------------------------------------------------------------
# Missing value / basic string normalization
# ---------------------------------------------------------------------


def is_missing(value: Any) -> bool:
    """
    pandas 없이도 None, NaN, 빈 문자열, 결측 표기를 안전하게 판정한다.
    """
    if value is None:
        return True

    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except TypeError:
        pass

    text = str(value).strip()
    if text == "":
        return True

    return text.lower() in {"nan", "none", "null", "na", "n/a", "-", "—"}


def normalize_text(value: Any) -> str:
    """
    일반 문자열 정규화.
    - None/NaN -> ""
    - Unicode NFC 정규화
    - 양끝 공백 제거
    - 여러 공백을 하나로 축소
    - zero-width character 제거
    """
    if is_missing(value):
        return ""

    text = str(value)
    text = unicodedata.normalize("NFC", text)

    # zero-width characters
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)

    # normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_lemma(value: Any) -> str:
    """
    사전 표제어 정규화.

    예:
    " 가격03 " -> "가격03"
    "가능 하다" -> "가능 하다"

    동형어번호 분리는 여기서 하지 않는다.
    필요한 경우 split_homograph_suffix()를 별도로 사용한다.
    """
    return normalize_text(value)


LIGHT_PREDICATE_SUFFIXES: dict[str, float] = {
    "시키다": 0.05,
    "되다": 0.04,
    "하다": 0.03,
}


def normalize_column_name(value: Any) -> str:
    """
    엑셀/CSV 컬럼명 정규화.
    """
    return normalize_text(value)


def normalize_columns(columns: Iterable[Any]) -> list[str]:
    """
    컬럼명 리스트 정규화.
    pandas DataFrame에 적용할 때 사용 가능.

    예:
    df.columns = normalize_columns(df.columns)
    """
    return [normalize_column_name(c) for c in columns]


# ---------------------------------------------------------------------
# Numeric parsing
# ---------------------------------------------------------------------


def safe_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """
    값을 int로 변환한다.
    실패하면 default를 반환한다.
    """
    if is_missing(value):
        return default

    text = normalize_text(value)

    # "1.0" 같은 엑셀 숫자 문자열 대응
    try:
        return int(float(text))
    except ValueError:
        pass

    m = re.search(r"-?\d+", text)
    if m:
        return int(m.group())

    return default


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    값을 float로 변환한다.
    실패하면 default를 반환한다.
    """
    if is_missing(value):
        return default

    text = normalize_text(value).replace(",", "")

    try:
        return float(text)
    except ValueError:
        return default


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """
    값을 lower~upper 범위로 제한한다.
    """
    return max(lower, min(upper, value))


# ---------------------------------------------------------------------
# Homograph number handling
# ---------------------------------------------------------------------


_HOMOGRAPH_SUFFIX_RE = re.compile(r"^(.+?)(\d{2})$")


def split_homograph_suffix(word: Any) -> tuple[str, int]:
    """
    5965개 어휘 목록처럼 표제어 뒤에 두 자리 동형어번호가 붙은 값을 분리한다.

    예:
    가격03 -> ("가격", 3)
    가구04 -> ("가구", 4)
    가게   -> ("가게", 0)

    주의:
    - 무조건 숫자를 제거하지 않는다.
    - 끝의 숫자가 정확히 두 자리일 때만 동형어번호로 본다.
    """
    text = normalize_lemma(word)

    if not text:
        return "", 0

    m = _HOMOGRAPH_SUFFIX_RE.match(text)
    if not m:
        return text, 0

    lemma = m.group(1)
    homograph_no = int(m.group(2))

    return lemma, homograph_no


def parse_homograph_no(value: Any, default: int = 0) -> int:
    """
    4만 어휘 목록의 동형어번호 값을 정리한다.

    예:
    3 -> 3
    "03" -> 3
    "" -> 0
    NaN -> 0
    """
    parsed = safe_int(value, default=default)
    if parsed is None:
        return default
    return max(parsed, 0)


# ---------------------------------------------------------------------
# Grade parsing and difficulty transformation
# ---------------------------------------------------------------------


def parse_grade5(value: Any) -> Optional[int]:
    """
    4만 개 5등급 어휘 목록의 등급을 정수 1~5로 변환한다.

    예:
    "1등급" -> 1
    "5등급" -> 5
    3 -> 3
    """
    if is_missing(value):
        return None

    n = safe_int(value)
    if n is not None and 1 <= n <= 5:
        return n

    text = normalize_text(value)
    m = re.search(r"[1-5]", text)
    if not m:
        return None

    grade = int(m.group())
    if 1 <= grade <= 5:
        return grade

    return None


def grade5_to_difficulty(grade: Any) -> Optional[float]:
    """
    5등급 어휘 난도 변환.

    1등급 -> 0.00
    2등급 -> 0.25
    3등급 -> 0.50
    4등급 -> 0.75
    5등급 -> 1.00
    """
    g = parse_grade5(grade)
    if g is None:
        return None

    return clamp((g - 1) / 4)


def grade5965_to_aux_difficulty(grade: Any) -> Optional[float]:
    """
    5965개 A/B/C 보조 난도 변환.

    확정 기준:
    - A -> 0.00
    - B -> 0.00
    - C -> 0.25

    숫자 입력:
    - 1 -> 0.00
    - 2 -> 0.25
    - 3 -> 0.25

    이 값은 메인 난도값이 아니라 4만 사전 난도를 보조하는 약한 신호다.
    """
    if is_missing(grade):
        return None

    text = normalize_text(grade).upper()

    if text in {"A", "B"}:
        return 0.00
    if text == "C":
        return 0.25

    n = safe_int(text)
    if n == 1:
        return 0.00
    if n in {2, 3}:
        return 0.25

    return None


def rank_to_difficulty(rank: Any, max_rank: Any) -> Optional[float]:
    """
    순위를 0~1 난도로 변환한다.

    순위가 클수록 덜 기본적인 단어라고 보고 로그 변환한다.

    예:
    rank_difficulty = log(1 + rank) / log(1 + max_rank)
    """
    r = safe_float(rank)
    m = safe_float(max_rank)

    if r is None or m is None:
        return None

    if r <= 0 or m <= 1:
        return None

    return clamp(math.log1p(r) / math.log1p(m))


# ---------------------------------------------------------------------
# POS normalization
# ---------------------------------------------------------------------


def normalize_pos(value: Any) -> str:
    """
    사전의 한국어 품사명을 정규화한다.

    입력 예:
    "명", "명사", "NOUN" -> "명사"
    "동", "동사", "VERB" -> "동사"
    "형", "형용사", "ADJ" -> "형용사"
    "부", "부사", "ADV" -> "부사"

    복합 품사:
    "부사/명사"는 그대로 의미를 보존하되 공백만 정리한다.
    """
    text = normalize_text(value)

    if not text:
        return ""

    text = text.replace(" ", "")

    direct_map = {
        "명": "명사",
        "명사": "명사",
        "n": "명사",
        "noun": "명사",
        "NNG": "명사",
        "NNP": "명사",

        "동": "동사",
        "동사": "동사",
        "v": "동사",
        "verb": "동사",
        "VV": "동사",

        "형": "형용사",
        "형용사": "형용사",
        "adj": "형용사",
        "adjective": "형용사",
        "VA": "형용사",

        "부": "부사",
        "부사": "부사",
        "adv": "부사",
        "adverb": "부사",
        "MAG": "부사",

        "관": "관형사",
        "관형사": "관형사",
        "determiner": "관형사",
        "MM": "관형사",

        "대": "대명사",
        "대명사": "대명사",
        "pronoun": "대명사",
        "NP": "대명사",

        "수": "수사",
        "수사": "수사",
        "number": "수사",
        "NR": "수사",

        "조": "조사",
        "조사": "조사",
        "JKS": "조사",
        "JKC": "조사",
        "JKG": "조사",
        "JKO": "조사",
        "JKB": "조사",
        "JKV": "조사",
        "JKQ": "조사",
        "JX": "조사",
        "JC": "조사",

        "어미": "어미",
        "EP": "어미",
        "EF": "어미",
        "EC": "어미",
        "ETN": "어미",
        "ETM": "어미",

        "감": "감탄사",
        "감탄사": "감탄사",
        "IC": "감탄사",

        "접사": "접사",
        "XPN": "접사",
        "XSN": "접사",
        "XSV": "접사",
        "XSA": "접사",
    }

    lower = text.lower()
    if text in direct_map:
        return direct_map[text]
    if lower in direct_map:
        return direct_map[lower]

    # "부사/명사", "부사·명사" 같은 복합 품사 처리
    parts = re.split(r"[/,;·]+", text)
    normalized_parts = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        normalized = direct_map.get(part) or direct_map.get(part.lower()) or part
        normalized_parts.append(normalized)

    if normalized_parts:
        return "/".join(normalized_parts)

    return text


# ---------------------------------------------------------------------
# Origin / domain normalization and bonus
# ---------------------------------------------------------------------


def normalize_origin(value: Any) -> str:
    """
    어종 정규화.

    예:
    "고유어", "한자어", "외래어", "혼종어"
    """
    text = normalize_text(value)

    if not text:
        return ""

    if "고유" in text:
        return "고유어"
    if "한자" in text:
        return "한자어"
    if "외래" in text:
        return "외래어"
    if "혼종" in text:
        return "혼종어"

    return text


def normalize_domain(value: Any) -> str:
    """
    분야 정규화.
    """
    return normalize_text(value)


def origin_domain_signal(origin: Any = None, domain: Any = None) -> float:
    """
    어종/분야 기반 보정 신호를 0~1로 계산한다.

    이 값은 최종 어휘 난도 계산에서 0.05 비중으로만 반영한다.

    원칙:
    - 일반 고유어: 낮음
    - 한자어/외래어/혼종어: 약간 높음
    - 전문 분야: 높음
    """
    normalized_origin = normalize_origin(origin)
    normalized_domain = normalize_domain(domain)

    origin_score = 0.0
    if normalized_origin == "한자어":
        origin_score = 0.40
    elif normalized_origin == "외래어":
        origin_score = 0.50
    elif normalized_origin == "혼종어":
        origin_score = 0.45
    elif normalized_origin == "고유어":
        origin_score = 0.00

    domain_score = 0.0
    if normalized_domain:
        if normalized_domain == "일반어":
            domain_score = 0.00
        elif "일반어" in normalized_domain:
            domain_score = 0.40
        else:
            domain_score = 1.00

    return clamp(max(origin_score, domain_score))


# ---------------------------------------------------------------------
# Weighted utilities
# ---------------------------------------------------------------------


def weighted_available(
    values: Sequence[Optional[float]],
    weights: Sequence[float],
    default: Optional[float] = None,
) -> Optional[float]:
    """
    결측값을 제외하고 사용 가능한 값끼리만 가중 평균한다.

    예:
    values = [0.2, None, 0.8]
    weights = [0.6, 0.3, 0.1]

    실제 계산:
    (0.2*0.6 + 0.8*0.1) / (0.6+0.1)
    """
    if len(values) != len(weights):
        raise ValueError("values and weights must have the same length.")

    used_values: list[float] = []
    used_weights: list[float] = []

    for value, weight in zip(values, weights):
        if value is None:
            continue

        try:
            v = float(value)
        except (TypeError, ValueError):
            continue

        if math.isnan(v):
            continue

        if weight <= 0:
            continue

        used_values.append(v)
        used_weights.append(float(weight))

    if not used_values:
        return default

    total_weight = sum(used_weights)
    if total_weight <= 0:
        return default

    return sum(v * w for v, w in zip(used_values, used_weights)) / total_weight


# ---------------------------------------------------------------------
# Light validation helpers
# ---------------------------------------------------------------------


def is_valid_lemma(value: Any) -> bool:
    """
    표제어로 사용할 수 있는 값인지 간단히 확인한다.
    """
    lemma = normalize_lemma(value)

    if not lemma:
        return False

    # 완전히 기호만 있는 경우 제외
    if re.fullmatch(r"[\W_]+", lemma):
        return False

    return True


def split_light_predicate_suffix(lemma: Any) -> Optional[tuple[str, str, float]]:
    """
    하다/되다/시키다 파생 표제어를 base, suffix, penalty로 분리한다.

    예:
    가공하다 -> ("가공", "하다", 0.03)
    사용되다 -> ("사용", "되다", 0.04)
    훈련시키다 -> ("훈련", "시키다", 0.05)
    """
    text = normalize_lemma(lemma)

    if not text:
        return None

    for suffix, penalty in sorted(
        LIGHT_PREDICATE_SUFFIXES.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if text.endswith(suffix) and len(text) > len(suffix):
            base = text[: -len(suffix)]
            if base:
                return base, suffix, penalty

    return None


__all__ = [
    "is_missing",
    "normalize_text",
    "normalize_lemma",
    "LIGHT_PREDICATE_SUFFIXES",
    "normalize_column_name",
    "normalize_columns",
    "safe_int",
    "safe_float",
    "clamp",
    "split_homograph_suffix",
    "parse_homograph_no",
    "parse_grade5",
    "grade5_to_difficulty",
    "grade5965_to_aux_difficulty",
    "rank_to_difficulty",
    "normalize_pos",
    "normalize_origin",
    "normalize_domain",
    "origin_domain_signal",
    "weighted_available",
    "is_valid_lemma",
    "split_light_predicate_suffix",
]
