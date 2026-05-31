# pipeline.py — 문장 난도 통합 파이프라인

**위치:** `src/sentdiff/pipeline.py`

## 역할

KiwiMorphAnalyzer + LexiconScorer + StructureScorer + NegationAnalyzer를 내부에서 관리하여,
문장 하나를 받으면 최종 난도 점수까지 한 번에 처리한다.

## flow 단계

**7단계 (최종)** — morph, lexical, structure, negation 모두 의존.

## 실행 흐름

```
pipeline.score("문장")
  ↓
morph.analyze("문장")           → tokens (MorphToken 리스트)
  ↓
lexical.compute_sentence_score  → lexical_score + scored_words
structure.score_tokens          → structure_score + structure_parts
negation.analyze                → negation_score + negation_detail
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

    "content_token_count": int,          # 내용어 개수
    "content_token_count_capped": int,   # 반복 제거 후 개수
    "unknown_token_count": int,          # unknown 판정 개수

    "scored_words": [dict],              # 개별 어휘 난도 리스트(surface, lemma, tag, pos 등)
    "score_parts": dict,                 # lexical 세부 (mean_all, mean_top_n, max)
    "structure_parts": dict,             # structure 8개 지표 + raw counts
    "negation_detail": dict,             # negation 4개 하위 점수

    "lexical_weight": 5.0,
    "structure_weight": 5.0,
    "negation_bonus_coefficient": 0.2,
}
```

## 클래스

### SentenceScorer

| 메서드 | 설명 |
|--------|------|
| `__init__(lexicon_config, structure_config)` | 4개 분석기 초기화 |
| `score(sentence)` | 문장 → 최종 난도 dict |

- `KiwiMorphAnalyzer` — 내부 생성 (kiwipiepy 자동 import)
- `LexiconScorer` — lexicon_config로 생성
- `StructureScorer` — structure_config로 생성
- `NegationAnalyzer` — 인자 없음

## 의존성

- **import:** `lexical.LexiconConfig, LexiconScorer`, `morph.KiwiMorphAnalyzer`, `negation.NegationAnalyzer`, `structure.StructureConfig, StructureScorer`
- **사용처:** `scripts/02_score_sentences.py` (CLI), 외부 API 진입점
