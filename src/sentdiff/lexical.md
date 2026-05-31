# lexical.py — 어휘 난도 점수

**위치:** `src/sentdiff/lexical.py`

## 역할

MorphToken 리스트의 내용어를 `lexicon_master.csv`에 lookup하여 개별 어휘 난도를 구하고,
문장 단위 어휘 점수(lexical score)를 산출한다.

## flow 단계

**4단계** — morph + normalize + lexicon_master.csv에 의존.

## Lookup 우선순위

```
1. exact           (lemma, pos)
2. base_exact      (base, pos) → (base, "명사") → (base, "어근")
3. lemma_only      lemma
4. base_lemma_only base
5. unknown         → config.unknown_difficulty (기본 0.30)
```

### 1차 exact: `(lemma, pos)` 쌍이 사전에 존재하면 즉시 반환.

### 2차 base_exact: 경동사 파생어(`split_light_predicate_suffix`)에서 base 추출 후
`(base, 원래pos)` → `(base, "명사")` → `(base, "어근")` 순서로 lookup.
base 길이가 2글자 이상이고 base가 명사/어근 품사인 경우만 유효.

### 3차 lemma_only: lemma만 일치하는 모든 항목을 aggregation 후 반환.

### 4차 base_lemma_only: base를 lemma_only lookup. base가 명사/어근인 경우만.

### 5차 unknown: 모든 lookup 실패 시 config.unknown_difficulty 반환.

## 다중 후보 집계 방식

`LexiconConfig.aggregation` (기본: `"min"`)

| 방식 | 동작 |
|------|------|
| `min` | 최소 난도 선택 (가장 쉬운 의미 채택) |
| `median` | 중앙값 |
| `mean` | 평균값 |

## 문장 점수 계산

### 반복 제거 (`_cap_repeats`)

같은 `(lemma, pos)`가 홀수 번째 등장할 때만 유지 (짝수 제거).
예: "것"이 3번 나오면 2번째 것은 제거. 단순 중복에 의한 난도 왜곡 방지.

### 3개 하위 점수 → 최종 lexical score

```
raw = 0.25 × mean_all + 0.50 × mean_top_3 + 0.25 × max
lexical_score = clamp(raw, 0, 1)
```

| 하위 점수 | 비중 | 설명 |
|-----------|------|------|
| `mean_all` | 0.25 | 모든 어휘 난도 평균 |
| `mean_top_n` | 0.50 | 상위 3개 평균 (어려운 단어 집중 반영) |
| `max` | 0.25 | 최고 난도 단어 |

내용어가 0개면 lexical_score = 0.0.

## 출력 구조

```python
{
    "lexical_score_0_1": float,         # 최종 lexical score (0~1)
    "content_token_count": int,         # 내용어 총 개수 (원본)
    "content_token_count_capped": int,  # 반복 제거 후 개수
    "unknown_token_count": int,         # unknown 판정 개수
    "scored_words": [                   # 반복 제거된 scored word 리스트
        {"surface", "lemma", "pos", "difficulty", "match_method", "matched_entry_id"}
    ],
    "score_parts": {
        "mean_all": float,
        "mean_top_n": float,
        "max": float,
    }
}
```

## 의존성

- **import:** `pandas`, `normalize` (split_light_predicate_suffix)
- **사용처:** `pipeline.py`가 `LexiconScorer` 호출
