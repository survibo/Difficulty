# flow.md — 문장 난이도 측정 파이프라인

```
사용자 입력
  │
  ▼
SentenceScorer.score("문장을 분석한다.")
  │
  ├── 1. KiwiMorphAnalyzer.analyze()
  │       └─→ list[MorphToken]
  │
  ├── 2. LexiconScorer.compute_sentence_score(tokens)
  │       └─→ lexical_score_0_1 + score_parts
  │
  ├── 3. StructureScorer.score_tokens(tokens)
  │       └─→ structure_score_0_1 + structure_parts
  │
  └── 4. score_0_1 = 0.70 × lexical + 0.30 × structure
          └─→ 최종 출력 dict
```

---

## 0. 진입점

### `SentenceScorer` (pipeline.py)

```python
scorer = SentenceScorer(lexicon_config, structure_config)
result = scorer.score("문장을 분석한다.")
```

생성자:

| 인자 | 기본값 | 설명 |
|---|---|---|
| `lexicon_config` | `LexiconConfig()` | 어휘 사전 경로/설정 |
| `structure_config` | `StructureConfig()` | 구조 점수 threshold/가중치 |

score() 출력 dict:

| 키 | 예시 | 출처 |
|---|---|---|
| `sentence` | `"문장을 분석한다."` | raw input |
| `score_0_1` | `0.1821` | 0.70×lexical + 0.30×structure |
| `score_10` | `1.82` | `round(score_0_1 × 10, 2)` |
| `lexical_score_0_1` | `0.2515` | LexiconScorer |
| `lexical_score_10` | `2.52` | `round(lexical × 10, 2)` |
| `structure_score_0_1` | `0.0200` | StructureScorer |
| `structure_score_10` | `0.20` | `round(structure × 10, 2)` |
| `content_token_count` | `2` | LexiconScorer |
| `unknown_token_count` | `0` | LexiconScorer |
| `scored_words` | `[...]` | LexiconScorer |
| `score_parts` | `{...}` | LexiconScorer |
| `structure_parts` | `{...}` | StructureScorer |
| `lexical_weight` | `0.70` | 고정 |
| `structure_weight` | `0.30` | 고정 |

---

## 1. 형태소 분석 — `KiwiMorphAnalyzer.analyze()`

**파일:** `morph.py`

Kiwi(open Korean tokenizer)로 문장을 형태소 단위로 분해한다.

### 입력
```python
"문장을 분석한다."
```

### 출력 — `list[MorphToken]`

MorphToken (frozen dataclass):

| 필드 | 타입 | 예시 | 설명 |
|---|---|---|---|
| `surface` | `str` | `"문장"` | 표면형 |
| `lemma` | `str` | `"문장"` | lemma 후보 (용언은 `-다` 붙임) |
| `tag` | `str` | `"NNG"` | Kiwi/Sejong 태그 (raw) |
| `pos` | `str` | `"명사"` | 사람이 읽는 품사명 |
| `start` | `int` | `0` | 문장 내 시작 offset |
| `end` | `int` | `2` | 문장 내 끝 offset |
| `is_content` | `bool` | `True` | 내용어 태그 여부 |

예시 출력:
```python
[
    MorphToken(surface="문장", lemma="문장", tag="NNG", pos="명사", start=0, end=2, is_content=True),
    MorphToken(surface="을", lemma="을", tag="JKO", pos="목적격조사", start=2, end=3, is_content=False),
    MorphToken(surface="분석", lemma="분석", tag="NNG", pos="명사", start=4, end=6, is_content=True),
    MorphToken(surface="하", lemma="분석하다", tag="XSV", pos="동사파생접미사", start=6, end=7, is_content=True),
    MorphToken(surface="ㄴ다", lemma="ㄴ다", tag="EF", pos="종결어미", start=7, end=9, is_content=False),
    MorphToken(surface=".", lemma=".", tag="SF", pos="마침표물음표느낌표", start=9, end=10, is_content=False),
]
```

### 주요 태그 목록

| 태그 | 품사 | 내용어 |
|---|---|---|
| `NNG`, `NNP`, `NNB` | 명사 | ✅ |
| `VV`, `VA` | 동사/형용사 | ✅ |
| `VCP`, `VCN` | 지정사 | ✅ |
| `MAG`, `MAJ` | 부사 | ✅ |
| `XR` | 어근 | ✅ |
| `IC` | 감탄사 | ✅ |
| `XSN`, `XSV`, `XSA` | 파생접미사 | ✅ |
| `JKS`, `JKC`, `JKO`, `JX` 등 | 조사 | ❌ |
| `EP`, `EF`, `EC`, `ETM`, `ETN` | 어미 | ❌ |
| `SF`, `SP`, `SS` | 문장부호 | ❌ |

내용어 여부는 `is_content_tag(tag)` 함수로 결정한다.

---

## 2. 어휘 난도 — `LexiconScorer.compute_sentence_score()`

**파일:** `lexical.py`

### 2a. `score_tokens(tokens)` — 개별 토큰 lookup

content token만 필터링한 후, 각 토큰의 lemma+pos를 `lexicon_master.csv`에서 lookup한다.

#### lookup 우선순위 (5단계)

| # | 방법 | 조건 | 예 |
|---|---|---|---|
| 1 | **exact** | (lemma, pos) 일치 | `("분석", "명사")` → 0.2588 |
| 2 | **base_exact** | 하다/되다/시키다 → base + 명사/어근 lookup | `("분석하다", "동사")` → `"분석"(명사)` 0.2588 |
| 3 | **lemma_only** | lemma만 일치 (pos 무시) | `("분석", "동사")` → `"분석"` 0.2588 |
| 4 | **base_lemma_only** | base lemma만 일치 (명사/어근만) | `("분석되다", "동사")` → `"분석"` 0.2588 |
| 5 | **unknown** | 미등록어 → 기본값 0.30 |

방어 조건:
- base 길이 1이면 base fallback 생략
- base_exact는 명사/어근 entry가 있을 때만 성공

### 2b. `compute_sentence_score(tokens)` — 문장 단위 집계

**점수 공식:**
```
mean_all  = mean(모든 내용어 difficulty)
mean_top3 = mean(상위 3개 difficulty)
max       = max difficulty

lexical_score_0_1 = 0.30 × mean_all + 0.40 × mean_top3 + 0.30 × max
                  → [0.0, 1.0] 범위로 클리핑
```

**score_parts (디버그용 breakdown):**

| 키 | 설명 |
|---|---|
| `mean_all` | 전체 평균 |
| `mean_top3` | 상위 3개 평균 |
| `max` | 최대값 |

### 출력 예시
```python
{
    "lexical_score_0_1": 0.2515,      # 순수 어휘 난도 (0~1)
    "content_token_count": 2,
    "unknown_token_count": 0,
    "scored_words": [                  # 개별 토큰 점수
        {"surface": "문장", "lemma": "문장", "pos": "명사",
         "difficulty": 0.2405, "match_method": "exact", "matched_entry_id": 13586},
        {"surface": "분석", "lemma": "분석", "pos": "명사",
         "difficulty": 0.2588, "match_method": "exact", "matched_entry_id": 17155},
    ],
    "score_parts": {
        "mean_all": 0.2497,
        "mean_top3": 0.2497,
        "max": 0.2588,
    },
}
```

---

## 3. 구조 복잡도 — `StructureScorer.score_tokens()`

**파일:** `structure.py`

MorphToken 리스트를 받아 7개 지표를 계산하고 가중합으로 구조 점수를 산출한다.

### 지표별 계산 방식

| 지표 | 가중치 | 계산 방식 | threshold |
|---|---|---|---|
| `length_score` | 0.20 | `min(1.0, max(0.0, (content_count − 5) / 25))` | (고정) |
| `predicate_score` | 0.20 | VV+VA+VCP+VCN 개수 / threshold | 6 |
| `embedding_score` | 0.20 | ETM+ETN 개수 / threshold | 4 |
| `connective_score` | 0.15 | EC 개수 / threshold | 5 |
| `logical_score` | 0.15 | (marker_weighted + strong_ending_w + weak_connective_w) / threshold | 4 |
| `modifier_score` | 0.05 | 최대 명사 연쇄 길이 / threshold | 5 |
| `derivational_score` | 0.05 | XSN+XSV+XSA + 표면형 매칭 개수 / threshold | 5 |

모든 sub-score는 `[0.0, 1.0]` 범위로 클리핑된다.

### 논리 표지 가중치 체계

세 가지 dict로 관리되며, surface/lemma 둘 다 매칭:

| dict | 예시 | 가중치 범위 |
|---|---|---|
| `LOGICAL_MARKERS` | 즉(1.0), 따라서(1.0), 그러나(1.0), 또한(0.7) | 0.7~1.0 |
| `STRONG_LOGICAL_ENDINGS` | 으므로(1.0), 지만(1.0), 더라도(1.0), 는데(0.6) | 0.6~1.0 |
| `WEAK_CONNECTIVE_ENDINGS` | 고(0.3), 며(0.4), 면서(0.5) | 0.3~0.5 |

### 명사 연쇄

`NNG`/`NNP`/`NNB`/`XR`이 연속되면 chain 증가. `XSN`은 앞에 명사류가 있을 때만 연장.

```
예: 사회(0) 문화(1) 연구(2) 방법(3) → max_noun_chain = 4
     방법(0) 론(1,XSN) 적(2,XSN)      → max_noun_chain = 3
     화(0,XSN) 과정(1)               → XSN이 chain 시작 못함, max = 1 (과정)
```

### 최종 구조 점수

```python
structure_score_0_1 = (
    0.20 × length_score
    + 0.20 × predicate_score
    + 0.20 × embedding_score
    + 0.15 × connective_score
    + 0.15 × logical_score
    + 0.05 × modifier_score
    + 0.05 × derivational_score
) → [0.0, 1.0] 범위로 클리핑
```

### 출력 예시
```python
{
    "structure_score_0_1": 0.0200,
    "structure_score_10": 0.20,
    "structure_parts": {
        # sub-scores
        "length_score": 0.0,
        "predicate_score": 0.0,
        "embedding_score": 0.0,
        "connective_score": 0.0,
        "logical_score": 0.0,
        "modifier_score": 0.2,
        "derivational_score": 0.2,
        # raw counts
        "content_token_count": 2,
        "predicate_count": 0,
        "ending_count": 1,
        "connective_ending_count": 0,
        "adnominal_count": 0,
        "nominalizer_count": 0,
        "logical_marker_weighted": 0.0,
        "logical_marker_count": 0,
        "strong_logical_ending_weighted": 0.0,
        "strong_logical_ending_count": 0,
        "weak_connective_weighted": 0.0,
        "weak_connective_count": 0,
        "derivational_suffix_count": 1,
        "max_noun_chain": 1,
    },
}
```

---

## 4. 최종 점수 결합 — pipeline.py

```python
score_0_1 = 0.70 × lexical_score_0_1 + 0.30 × structure_score_0_1
         → [0.0, 1.0] 범위로 클리핑

score_10 = round(score_0_1 × 10, 2)
```

Lexical에 비중 0.70, structure에 0.30을 준 이유:
- 어휘 난도는 사전 기반으로 비교적 신뢰 가능
- 구조 점수는 아직 POS 태그 기반 proxy이므로 보수적으로 반영

---

## 5. CLI 출력 — scripts/02_score_sentences.py

### 기본 출력
```
$ python scripts/02_score_sentences.py "문장을 분석한다."

  sentence:        문장을 분석한다.
  score_10:        1.82
  lexical_score:   2.52
  structure_score: 0.20
  content_words:   2
  unknown_words:   0
  scored_words:
    문장           0.2405   exact            (id=13586)
    분석           0.2588   exact            (id=17155)
```

### --debug 출력
```
$ python scripts/02_score_sentences.py --debug "문장을 분석한다."

  ... (기본 출력 + 아래 추가)

  [lexical_parts]
    mean_all:   0.2497
    mean_top3:  0.2497
    max:        0.2588
  [structure_parts]
    length_score:               0.0
    predicate_score:            0.0
    embedding_score:            0.0
    connective_score:           0.0
    logical_score:              0.0
    modifier_score:             0.2
    derivational_score:         0.2
    content_token_count:        2
    predicate_count:            0
    ending_count:               1
    connective_ending_count:    0
    adnominal_count:            0
    nominalizer_count:          0
    logical_marker_weighted:    0.0
    logical_marker_count:       0
    strong_logical_ending_w:    0.0
    strong_logical_ending_cnt:  0
    weak_connective_w:          0.0
    weak_connective_cnt:        0
    derivational_suffix_count:  1
    max_noun_chain:             1
```

### 3가지 실행 모드

| 모드 | 명령어 |
|---|---|
| 인라인 문장 | `python scripts/02_score_sentences.py "문장"` |
| 파일 입력 | `python scripts/02_score_sentences.py --file input.txt` |
| 인터랙티브 | `python scripts/02_score_sentences.py` (빈 줄로 종료) |

모든 모드에서 `--debug` 플래그 사용 가능.

---

## 파일 관계도

```
scripts/
  02_score_sentences.py ─── CLI 진입점
src/sentdiff/
  morph.py        ─── KiwiMorphAnalyzer (형태소 분석)
  lexical.py      ─── LexiconScorer (어휘 난도)
  structure.py    ─── StructureScorer (구조 복잡도)
  pipeline.py     ─── SentenceScorer (3개 통합)
  normalize.py    ─── 정규화 유틸리티
  lexicon_builder.py ─── lexicon_master.csv 생성
tests/
  test_morph.py
  test_lexical.py
  test_structure.py
  test_pipeline.py
data/
  processed/lexicon_master.csv ─── 어휘 난도 사전
```
