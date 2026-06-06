# pipeline.py — 문장 난도 통합 파이프라인

**위치:** `src/sentdiff/pipeline.py`

## 역할

KiwiMorphAnalyzer + LexiconScorer + PatternMatcher + StructureScorer + NegationAnalyzer를
내부에서 관리하여, 문장 하나를 받으면 최종 난도 점수까지 한 번에 처리한다.

파이프라인은 분석 단위를 세 층으로 분리한다.

- **형태소 토큰 (`MorphToken`)**: 구조 length·서술어·명사 연쇄와 부정 표지의 입력
- **어휘 단위 (`LexicalUnit`)**: 사전 난도와 reliability의 입력
- **논리·절 경계 span (`PatternMatch`)**: logical과 negation 경계 분류의 입력

## flow 단계

**7단계 (최종)** — morph, lexical, structure, negation 모두 의존.

## 실행 흐름

```
pipeline.score("문장")
  ↓
morph.analyze("문장")           → tokens (MorphToken 리스트)
  ↓
lexical.compute_sentence_score  → LexicalUnit 분할 + lexical_score + scored_words
patterns.match_*                → logical / strong ending / boundary spans
structure.score_tokens          → MorphToken + logical spans 기반 structure_score
negation.analyze                → MorphToken + boundary spans 기반 negation_score
  ↓
가중 합산 → 최종 score_0_1
```

## 점수 공식

```
score = min(1.0, 0.5 × lexical + 0.5 × structure + 0.2 × negation)
```

**가중치:**

| 항목 | 기호 | 값 | 설명 |
|------|------|-----|------|
| lexical | `_LEXICAL_WEIGHT` | 5.0 | 어휘 난도 (0~1) × 0.5 |
| structure | `_STRUCTURE_WEIGHT` | 5.0 | 구조 복잡도 (0~1) × 0.5 |
| negation | `_NEGATION_BONUS_COEFF` | 0.2 | 부정 보너스 (0~1) × 0.2 |

내부 계산:

```
score_0_1 = (0.5 × lexical_score) + (0.5 × structure_score) + (0.2 × negation_score)
score_0_1 = clamp(score_0_1, 0, 1)
```

- negation은 **보너스** — 이중/삼중 부정이 없는 보통 문장은 0.5×lexical + 0.5×structure로 1.0까지 도달 가능.
- `score_10 = score_0_1 × 10` — 0~10 스케일로 변환.

## 출력 구조

```python
{
    "sentence": str,                     # 원문
    "score_0_1": float,                  # 최종 점수 (0~1)
    "score_10": float,                   # 10배 스케일 (0~10)

    "lexical_score_0_1": float,          # 어휘 점수
    "lexical_score_10": float,
    "structure_score_0_1": float,        # 구조 점수
    "structure_score_10": float,
    "negation_score_0_1": float,         # 부정 점수
    "negation_score_10": float,

    "lexical_unit_count": int,           # 선택된 어휘 단위 개수
    "lexical_unit_count_capped": int,    # 반복 제거 후 어휘 단위 개수
    "unknown_lexical_unit_count": int,    # unknown 어휘 단위 개수
    "structure_content_token_count": int, # 구조 length용 MorphToken 내용어 수

    "morph_tokens": [dict],               # HTML/CLI 진단용 정규화 형태소 trace
    "scored_words_full": [dict],         # 전체 LexicalUnit 리스트
    "scored_words": [dict],              # 반복 제거된 LexicalUnit 리스트
    "score_parts": dict,                 # lexical 세부 + mean_all 실제 분모/0.0 제외 개수
    "structure_parts": dict,             # structure 7개 지표 + logical span + raw counts
    "negation_detail": dict,             # negation 4개 하위 점수 + boundary span

    "lexical_weight": 5.0,
    "structure_weight": 5.0,
    "negation_bonus_coefficient": 0.2,
    "reliability": float,
}
```

`scored_words_full`의 각 항목은 대표 `tag`와 구성 태그 전체 `tags`, 원문 문자 span,
토큰 span을 함께 제공한다. 기존 이름은 유지하지만 의미는 개별 형태소가 아니라 어휘 단위다.

`morph_tokens`는 점수 계산에 사용한 동일한 형태소 분석 결과를 직렬화한다. 각 항목은
`surface`, `lemma`, 원시 `tag`, 정규화된 `base_tag`, `pos`, 문자 span,
`is_content`, `structure_role`을 포함하며 HTML Debug 토글과 진단 도구가 사용한다.

`reliability`는 어휘 단위 기준으로 계산한다.

```
reliability = 1 - unknown_lexical_unit_count / lexical_unit_count
```

어휘 단위가 없으면 reliability는 1.0이다.

## 클래스

### SentenceScorer

| 메서드 | 설명 |
|--------|------|
| `__init__(lexicon_config, structure_config)` | 형태소·어휘·패턴·구조·부정 분석기 초기화 |
| `score(sentence)` | 문장 → 최종 난도 dict |

- `KiwiMorphAnalyzer` — 내부 생성 (kiwipiepy 자동 import)
- `LexiconScorer` — lexicon_config로 생성
- `PatternMatcher` — 고정 논리 표현, 강한 연결 표현, 절 경계 span 생성
- `StructureScorer` — structure_config로 생성
- `NegationAnalyzer` — 인자 없음

## 의존성

- **import:** `lexical.LexiconConfig, LexiconScorer`, `morph.KiwiMorphAnalyzer`,
  `patterns.PatternMatcher`, `negation.NegationAnalyzer`, `structure.StructureConfig, StructureScorer`
- **사용처:** `scripts/02_score_sentences.py` (CLI), 외부 API 진입점
