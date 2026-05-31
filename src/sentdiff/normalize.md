# normalize.py — 공통 정규화 유틸리티

**위치:** `src/sentdiff/normalize.py`

## 역할

문장 난이도 측정 프로젝트 전반에서 공통으로 사용하는 정규화·변환 유틸리티.
엑셀/CSV 문자열 정리, 동형어번호 분리, 등급→난도 변환, 품사명 정규화, 어종/분야 신호,
경동사 파생 접미사 분리 등을 제공한다.

## flow 단계

**1단계** — 모든 모듈이 의존하는 기반 유틸리티. 독립 실행 불가.

## 세부 기능

### 1. 결측값·문자열 정규화

| 함수 | 역할 |
|------|------|
| `is_missing(v)` | None/NaN/빈문자열/결측표기 판정 |
| `normalize_text(v)` | NFC 정규화, zero-width 제거, 공백 축소 |
| `normalize_lemma(v)` | 사전 표제어 정규화 |
| `normalize_column_name(v)` | 컬럼명 정규화 |

### 2. 동형어번호 처리

```
split_homograph_suffix("가격03") → ("가격", 3)
split_homograph_suffix("가게")   → ("가게", 0)
```

5965 목록처럼 표제어 끝 두 자리 숫자가 동형어번호인 경우 분리.

### 3. 등급→난도 변환

| 함수 | 입력 | 출력 | 용도 |
|------|------|------|------|
| `parse_grade5(v)` | "1등급"~"5등급" | 1~5 정수 | 4만 목록 등급 파싱 |
| `grade5_to_difficulty(g)` | 1~5 등급 | 0.00, 0.25, ..., 1.00 | 4만 목록 메인 난도 |
| `grade5965_to_aux_difficulty(g)` | A/B/C | 0.00 / 0.00 / 0.25 | 5965 보조 난도 |

**grade5_to_difficulty 공식:**

```
difficulty = (grade - 1) / 4
```

**grade5965_to_aux_difficulty 기준:**
- A, B → 0.00 (쉬움)
- C → 0.25 (2등급성 보조값)

### 4. 순위→난도 변환

```
rank_difficulty = (log(1 + rank) - log(2)) / (log(1 + max_rank) - log(2))
```

순위가 클수록 덜 기본적인 단어 → 로그 스케일로 0~1 변환.

### 5. 품사명 정규화

```
normalize_pos("명")  → "명사"
normalize_pos("VV")  → "동사"
normalize_pos("부사/명사") → "부사/명사"  (복합 품사 보존)
```

영문 태그·약어·한글 품사명을 통일된 한글 품사명으로 변환.

### 6. 어종/분야 신호

| 값 | origin_score | 용도 |
|----|-------------|------|
| 고유어 | 0.00 | 가장 쉬움 |
| 한자어 | 0.40 | 약간 어려움 |
| 외래어 | 0.50 | |
| 혼종어 | 0.45 | |

domain_score: 일반어=0.00, 일반어 포함=0.40, 전문분야=1.00

최종 신호 = `max(origin_score, domain_score)` (0~1, 비중 0.05)

### 7. 경동사 파생 접미사 분리

```
split_light_predicate_suffix("가공하다") → ("가공", "하다", 0.03)
split_light_predicate_suffix("사용되다") → ("사용", "되다", 0.04)
```

| 접미사 | penalty |
|--------|---------|
| 하다 | 0.03 |
| 되다 | 0.04 |
| 시키다 | 0.05 |

base lemma lookup fallback과 파생어 난도 보정에 사용.

### 8. 가중 평균 유틸리티

```
weighted_available(values, weights, default=None)
```

결측값 제외 후 가용한 값만으로 가중 평균 계산.

## 의존성

- **import:** stdlib만 사용 (`math`, `re`, `unicodedata`, `typing`)
- **사용처:** 모든 sentdiff 모듈 (`lexicon_builder.py`, `morph.py`, `lexical.py`, `structure.py`, `negation.py`, `pipeline.py`)
