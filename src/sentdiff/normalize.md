# normalize.py — 공통 정규화 유틸

**위치:** `src/sentdiff/normalize.py` (639줄)

## 역할
프로젝트 전반에서 사용하는 문자열/숫자 정규화, 등급↔난도 변환, 경동사 접미사 분리 등 공통 함수 모음.

## 주요 함수

| 함수 | 설명 |
|------|------|
| `normalize_text(value)` | None/NaN → `""`, NFC 정규화, 공백 축소 |
| `is_missing(value)` | None/NaN/빈문자열 등 결측치 판정 |
| `safe_int(value)` / `safe_float(value)` | 안전한 숫자 변환 (실패 시 None) |
| `split_homograph_suffix(word)` | `"가격03"` → `("가격", 3)` 동형어 번호 분리 |
| `parse_grade5(value)` / `grade5_to_difficulty(grade)` | 1~5등급 → 0.00~1.00 |
| `grade5965_to_aux_difficulty(grade)` | A=0.00, B=0.00, C=0.25 |
| `rank_to_difficulty(rank, max_rank)` | 순위 → 0~1 로그 변환 |
| `normalize_pos(value)` | `"명"`/`"VV"` → `"명사"`/`"동사"` |
| `normalize_origin(value)` / `normalize_domain(value)` | 어종/분야 정규화 |
| `origin_domain_signal(origin, domain)` | 어종·분야 → 0~1 보정값 |
| `weighted_available(values, weights)` | 결측 제외 가중 평균 |
| `split_light_predicate_suffix(lemma)` | `"가공하다"` → `("가공", "하다", 0.03)` |
| `is_valid_lemma(value)` | 표제어 유효성 검사 |

## 의존성
- **import:** stdlib만 사용 (다른 sentdiff 파일 import 없음)
- **사용처:** 모든 src 파일
