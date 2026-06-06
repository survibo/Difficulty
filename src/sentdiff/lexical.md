# lexical.py — 어휘 난도 점수

**위치:** `src/sentdiff/lexical.py`

## 역할

MorphToken 리스트에서 사전에 등록된 전체 표제어 span을 복원하여 비중첩 `LexicalUnit`
목록을 만들고, 각 어휘 단위를 `lexicon_master.csv`에 lookup하여 문장 단위 어휘 점수
(lexical score)를 산출한다.

형태소 토큰과 어휘 단위는 서로 다른 개념이다. 예를 들어 `가련/XR + 하/XSA + 다/EF`가
사전에 `가련하다`로 등록되어 있으면 세 형태소를 하나의 어휘 단위로 한 번만 채점한다.
전체 표제어를 찾지 못한 경우에만 개별 내용어 토큰으로 fallback한다.

## flow 단계

**4단계** — morph + `lexical_units.py` + normalize + lexicon_master.csv에 의존.

## 어휘 단위 resolver

`LexicalUnitResolver.resolve(sentence, tokens)`는 최대 8개 연속 토큰 범위에서 사전 lookup이
성공하는 span 후보와 단일 내용어 fallback 후보를 만든다. 원문에서 토큰 사이에 공백이 있는
범위는 하나의 어휘 단위로 합치지 않는다.

span 후보에는 다음 조합이 포함된다.

- 전체 표제어와 합성 명사
- `XR/NNG + XSA/XSV (+ EF)` 파생 용언
- `XR + XSM` 파생 부사
- `명사 + XSN` 파생 명사
- 그 밖의 연속 내용어·접사·종결어미 조합 중 사전 lookup에 성공한 표제어

후보가 겹치면 동적 계획법으로 문장 전체의 비중첩 분할을 선택한다. 실제 선택 우선순위는
`사전에 등록된 내용어 포괄 수 → 전체 내용어 포괄 수 → 알려진 span 수 → span 길이
→ unknown 최소화 → 단위 수 최소화`다. 선택된 span 내부의 구성 형태소는 별도로
중복 채점하지 않는다.

### LexicalUnit

| 필드 | 설명 |
|------|------|
| `surface`, `lemma`, `pos` | 어휘 단위의 원문 표면형, lookup lemma, 사전 품사 |
| `start`, `end` | 원문 문자 span |
| `token_start`, `token_end` | 원본 MorphToken 반열림 구간 |
| `tags` | span을 구성한 기본 Sejong 태그 전체 |
| `head_tag` | 대표 태그. `scored_words*.tag`로도 제공 |
| `difficulty` | 사전 난도 또는 unknown 기본값 |
| `match_method` | `exact`, `base_exact`, `lemma_only`, `base_lemma_only`, `unknown`과 `span_` 변형 |
| `matched_entry_id` | 선택된 사전 항목 ID. unknown이면 0 |

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

선택된 어휘 단위 중 같은 `(lemma, pos)`가 홀수 번째 등장할 때만 유지한다(짝수 제거).
예: 같은 어휘 단위가 3번 나오면 2번째 단위는 제외한다. 단순 중복에 의한 난도 왜곡을 막는다.

### 어휘 단위 개수에 따른 동적 가중치

어휘 단위(capped) 개수에 따라 세 가지 가중치 집합을 선택한다.

| 어휘 단위(capped) | `mean_top_5` | `mean_all` | `max` |
|:---:|:---:|:---:|:---:|
| ≤4  | **0.25** | **0.50** | **0.25** |
| 5–7 | **0.40** | **0.35** | **0.25** |
| ≥8  | **0.50** | **0.25** | **0.25** |

짧은 문장일수록 `mean_all` 비중을 높여 단일 단어의 영향력을 분산한다.

`lexical_unit_count_capped`가 10개 이상이면 난도 `0.0`인 어휘 단위는
`mean_all`의 합계와 분모에서 제외한다. 긴 문장에 쉬운 어휘가 많이 추가되어
전체 평균이 과도하게 낮아지는 현상을 줄이기 위한 보정이다. 9개 이하에서는
`0.0`도 기존처럼 포함하며, `mean_top_5`와 `max` 계산은 항상 기존 방식을 유지한다.

### 3개 하위 점수 → 최종 lexical score

```
raw = w_mean_top_5 × mean_top_5 + w_mean_all × mean_all + w_max × max
lexical_score = clamp(raw, 0, 1)
```

어휘 단위가 0개면 lexical_score = 0.0.

## 출력 구조

```python
{
    "lexical_score_0_1": float,         # 최종 lexical score (0~1)
    "lexical_unit_count": int,          # 선택된 어휘 단위 총 개수
    "lexical_unit_count_capped": int,   # 반복 제거 후 어휘 단위 개수
    "unknown_lexical_unit_count": int,  # unknown 어휘 단위 개수
    "scored_words_full": [              # 전체 scored word 리스트
        {
            "surface", "lemma", "tag", "tags", "pos", "difficulty",
            "match_method", "matched_entry_id", "start", "end",
            "token_start", "token_end"
        }
    ],
    "scored_words": [                   # 반복 제거된 LexicalUnit 리스트
        {
            "surface", "lemma", "tag", "tags", "pos", "difficulty",
            "match_method", "matched_entry_id", "start", "end",
            "token_start", "token_end"
        }
    ],
    "score_parts": {
        "mean_all": float,
        "mean_all_count": int,                # mean_all의 실제 분모
        "mean_all_zero_excluded_count": int,  # 긴 문장에서 제외된 0.0 개수
        "mean_top_n": float,
        "max": float,
        "lexical_weights": {
            "mean_all": float,   # 0.50 / 0.35 / 0.25
            "mean_top_n": float, # 0.25 / 0.40 / 0.50
            "max": float,        # 항상 0.25
        },
    }
}
```

`scored_words_full`과 `scored_words`라는 기존 필드명은 유지하지만, 각 항목의 의미는
형태소 토큰이 아니라 선택된 어휘 단위다. `tag`는 대표 태그, `tags`는 span 전체 태그다.

`reliability`는 pipeline에서 다음과 같이 계산한다.

```
reliability = 1 - unknown_lexical_unit_count / lexical_unit_count
```

## 의존성

- **import:** `pandas`, `lexical_units`, `normalize` (split_light_predicate_suffix)
- **사용처:** `pipeline.py`가 `LexiconScorer` 호출
