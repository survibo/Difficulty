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
- 형태소 분석기 태그를 사전 품사명으로 매핑

중요한 난도 정책:
- 4만 개 5등급 목록을 메인 기준으로 사용한다.
- 5965개 A/B/C 목록은 보조 기준으로만 사용한다.
- 5965 기준에서 A/B는 쉬운 어휘, C는 2등급성 보조값으로 본다.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Iterable, Optional, Sequence, Tuple


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


def split_homograph_suffix(word: Any) -> Tuple[str, int]:
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


def parse_grade3(value: Any) -> Optional[int]:
    """
    5965개 어휘 목록의 A/B/C 등급을 보조 등급으로 변환한다.

    확정 기준:
    - A -> 1
    - B -> 1
    - C -> 2

    주의:
    이 함수는 예전 이름과의 호환을 위해 유지한다.
    실제 난도값이 필요하면 grade5965_to_aux_difficulty()를 사용한다.
    """
    if is_missing(value):
        return None

    text = normalize_text(value).upper()

    letter_map = {
        "A": 1,
        "B": 1,
        "C": 2,
    }

    if text in letter_map:
        return letter_map[text]

    n = safe_int(text)
    if n == 1:
        return 1
    if n in {2, 3}:
        return 2

    return None


def parse_grade5965(value: Any) -> Optional[int]:
    """
    5965개 어휘 목록의 A/B/C 등급을 보조 등급으로 변환한다.

    parse_grade3()와 같은 동작이지만, 의미가 더 명확한 이름이다.
    """
    return parse_grade3(value)


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


def grade3_to_difficulty(grade: Any) -> Optional[float]:
    """
    5965개 A/B/C 보조 난도 변환.

    예전 코드와의 호환을 위해 함수명은 유지하지만,
    더 이상 A/B/C를 0.00/0.50/1.00으로 보지 않는다.

    현재 기준:
    - A -> 0.00
    - B -> 0.00
    - C -> 0.25
    """
    return grade5965_to_aux_difficulty(grade)


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


def sejong_tag_to_pos(tag: Any) -> str:
    """
    Kiwi/Sejong 계열 형태소 태그를 사전 품사명으로 변환한다.

    주요 태그:
    NNG, NNP -> 명사
    VV -> 동사
    VA -> 형용사
    MAG -> 부사
    MM -> 관형사
    NP -> 대명사
    NR -> 수사
    J* -> 조사
    E* -> 어미
    VX -> 보조용언
    XR -> 어근
    """
    t = normalize_text(tag)

    if not t:
        return ""

    if t.startswith("NN"):
        return "명사"
    if t == "NP":
        return "대명사"
    if t == "NR":
        return "수사"
    if t == "VV":
        return "동사"
    if t == "VA":
        return "형용사"
    if t in {"VCP", "VCN"}:
        return "지정사"
    if t == "VX":
        return "보조용언"
    if t == "MAG":
        return "부사"
    if t == "MAJ":
        return "접속부사"
    if t == "MM":
        return "관형사"
    if t.startswith("J"):
        return "조사"
    if t.startswith("E"):
        return "어미"
    if t.startswith("XS") or t == "XPN":
        return "접사"
    if t == "XR":
        return "어근"
    if t == "IC":
        return "감탄사"
    if t.startswith("S"):
        return "기호"
    if t.startswith("N"):
        return "명사"

    return t


def pos_matches(dictionary_pos: Any, analyzer_tag: Any) -> bool:
    """
    사전 품사와 형태소 분석기 태그가 대략적으로 일치하는지 판정한다.

    예:
    dictionary_pos="명사", analyzer_tag="NNG" -> True
    dictionary_pos="부사/명사", analyzer_tag="MAG" -> True
    """
    dpos = normalize_pos(dictionary_pos)
    apos = sejong_tag_to_pos(analyzer_tag)

    if not dpos or not apos:
        return False

    dpos_parts = set(dpos.split("/"))

    if apos in dpos_parts:
        return True

    # 보조용언은 동사/형용사 계열로 약하게 허용
    if apos == "보조용언" and {"동사", "형용사"} & dpos_parts:
        return True

    # 어근은 명사/동사/형용사 후보와 결합될 수 있어 직접 일치로 보지 않는다.
    return False


# ---------------------------------------------------------------------
# Lemma normalization for analyzer tokens
# ---------------------------------------------------------------------


def token_to_lemma_candidate(form: Any, tag: Any) -> str:
    """
    형태소 분석 결과를 사전 표제어 후보로 변환한다.

    Kiwi는 용언 어간을 주는 경우가 많으므로,
    VV/VA는 '-다'를 붙여 사전형 후보를 만든다.

    예:
    먹/VV -> 먹다
    가깝/VA -> 가깝다
    가능/NNG -> 가능
    """
    f = normalize_text(form)
    t = normalize_text(tag)

    if not f:
        return ""

    if t in {"VV", "VA"}:
        if f.endswith("다"):
            return f
        return f + "다"

    return f


def is_content_tag(tag: Any) -> bool:
    """
    문장 난이도 어휘 점수에서 내용어로 볼 품사인지 판정한다.

    포함:
    - 일반명사/고유명사/의존명사 계열
    - 동사
    - 형용사
    - 부사
    - 어근
    - 수사
    """
    t = normalize_text(tag)

    if not t:
        return False

    return (
        t.startswith("NN")
        or t in {"VV", "VA", "MAG", "XR", "NR", "NP"}
    )


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


def origin_bonus(origin: Any) -> float:
    """
    어종 기반 난도 보정값.

    주의:
    - 한자어/외래어가 항상 어려운 것은 아니므로 아주 약한 보정만 준다.
    - 이 함수는 기존 코드와의 호환을 위해 유지한다.
    - 새 compute_word_difficulty()는 origin_domain_signal()을 사용한다.
    """
    o = normalize_origin(origin)

    if not o:
        return 0.0

    if o == "외래어":
        return 0.05
    if o == "한자어":
        return 0.04
    if o == "혼종어":
        return 0.04

    return 0.0


def domain_bonus(domain: Any) -> float:
    """
    분야 기반 전문성 보정값.

    일반어만 있으면 0.
    일반어와 전문 분야가 함께 있으면 약한 보정.
    일반어가 아니면 더 큰 보정.

    이 함수는 기존 코드와의 호환을 위해 유지한다.
    새 compute_word_difficulty()는 origin_domain_signal()을 사용한다.
    """
    d = normalize_domain(domain)

    if not d:
        return 0.0

    if d == "일반어":
        return 0.0

    if "일반어" in d:
        return 0.04

    return 0.10


def origin_domain_signal(origin: Any = None, domain: Any = None) -> float:
    """
    어종/분야 기반 보정 신호를 0~1로 계산한다.

    이 값은 최종 compute_word_difficulty()에서 0.05 비중으로만 반영한다.

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


def make_lexicon_key(
    lemma: Any,
    pos: Any = "",
    homograph_no: Any = 0,
    include_pos: bool = True,
    include_homograph: bool = True,
) -> str:
    """
    사전 항목 식별용 key 생성.

    기본:
    lemma|pos|homograph_no

    예:
    make_lexicon_key("가격", "명사", 3) -> "가격|명사|3"
    """
    normalized_lemma = normalize_lemma(lemma)
    normalized_pos = normalize_pos(pos)
    normalized_homograph = parse_homograph_no(homograph_no)

    parts = [normalized_lemma]

    if include_pos:
        parts.append(normalized_pos)

    if include_homograph:
        parts.append(str(normalized_homograph))

    return "|".join(parts)


# ---------------------------------------------------------------------
# Difficulty construction helper
# ---------------------------------------------------------------------


def compute_word_difficulty(
    grade5: Any = None,
    grade5965: Any = None,
    grade3: Any = None,
    rank: Any = None,
    max_rank: Any = None,
    origin: Any = None,
    domain: Any = None,
    origin_domain_signal_value: Optional[float] = None,
    base_default: float = 0.60,
) -> float:
    """
    어휘 하나의 0~1 난도값을 계산한다.

    최종 기준:
    - 4만 5등급 기반 난도: 0.80
    - 5965 보조 난도: 0.10
    - 5965 순위 기반 난도: 0.05
    - 어종/분야 신호: 0.05

    결측값이 있으면 사용 가능한 값끼리 재가중한다.

    매개변수:
    - grade5: 4만 목록의 1~5등급 또는 "1등급" 같은 문자열
    - grade5965: 5965 목록의 A/B/C 등급
    - grade3: 예전 이름과의 호환용. grade5965가 없을 때만 사용
    - rank: 5965 목록 순위
    - max_rank: 5965 목록 최대 순위
    - origin/domain: 어종/분야
    - origin_domain_signal_value: 이미 계산된 0~1 어종/분야 신호
    """
    grade5_diff = grade5_to_difficulty(grade5)

    aux_grade = grade5965
    if is_missing(aux_grade):
        aux_grade = grade3

    aux5965_diff = grade5965_to_aux_difficulty(aux_grade)
    rank_diff = rank_to_difficulty(rank, max_rank)

    if origin_domain_signal_value is None:
        od_signal = origin_domain_signal(origin=origin, domain=domain)
    else:
        od_signal = clamp(float(origin_domain_signal_value))

    base = weighted_available(
        values=[
            grade5_diff,
            aux5965_diff,
            rank_diff,
            od_signal,
        ],
        weights=[
            0.80,
            0.10,
            0.05,
            0.05,
        ],
        default=base_default,
    )

    if base is None:
        base = base_default

    return clamp(float(base))


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


def contains_hangul(value: Any) -> bool:
    """
    문자열에 한글 음절/자모가 포함되어 있는지 확인한다.
    """
    text = normalize_text(value)
    return bool(re.search(r"[가-힣ㄱ-ㅎㅏ-ㅣ]", text))


def strip_parenthetical(text: Any) -> str:
    """
    괄호 안 설명을 제거한다.

    예:
    "가능하다(可能-)" -> "가능하다"
    """
    s = normalize_text(text)
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\[[^\]]*\]", "", s)
    return normalize_text(s)


__all__ = [
    "is_missing",
    "normalize_text",
    "normalize_lemma",
    "normalize_column_name",
    "normalize_columns",
    "safe_int",
    "safe_float",
    "clamp",
    "split_homograph_suffix",
    "parse_homograph_no",
    "parse_grade5",
    "parse_grade3",
    "parse_grade5965",
    "grade5_to_difficulty",
    "grade3_to_difficulty",
    "grade5965_to_aux_difficulty",
    "rank_to_difficulty",
    "normalize_pos",
    "sejong_tag_to_pos",
    "pos_matches",
    "token_to_lemma_candidate",
    "is_content_tag",
    "normalize_origin",
    "normalize_domain",
    "origin_bonus",
    "domain_bonus",
    "origin_domain_signal",
    "weighted_available",
    "make_lexicon_key",
    "compute_word_difficulty",
    "is_valid_lemma",
    "contains_hangul",
    "strip_parenthetical",
]