# paragraph — 문단 단위 난도 분석

문단 분석은 기존 문장 분석기(`SentenceScorer`)를 변경하지 않고, 문장별 결과를 문단 단위로 집계한다.

문단 분석은 문장이 **4개 이상**일 때만 수행한다. 문장이 3개 이하이면 점수를 계산하지 않고 오류를 낸다.

## 위치

- 패키지: `src/sentdiff/paragraph/`
- 진입점: `ParagraphScorer`

## 공식

```text
paragraph_score =
  0.85 × sentence_aggregate
+ 0.15 × information_density
+ 0.15 × concept_repetition
```

`concept_repetition`은 반복 핵심어 처리 부담을 더하는 **보너스** 항목이다. 최종 점수는 1.0을 넘지 않도록 clamp한다.

## sentence_aggregate

문단 안 문장 점수의 평균, 상위 3개 평균, 최댓값을 함께 사용한다.

```text
sentence_aggregate =
  0.40 × sentence_mean
+ 0.40 × sentence_top_3_mean
+ 0.20 × sentence_max
```

## information_density

문단 전체에서 서로 다른 **핵심 내용어** 수를 정보량으로 본다.
사전 난도(lexical difficulty)가 아니라 형태소 품사 기준으로 집계한다.

핵심 내용어 태그:

| 태그 | 의미 |
|------|------|
| `NNG` | 일반명사 |
| `NNP` | 고유명사 |
| `VV` | 동사 |
| `VA` | 형용사 |
| `XR` | 어근 |

`NNB` 의존명사, `NP` 대명사, `NR` 수사, `MAG` 부사, 외국어/한자 표기는 정보 밀도 집계에서 제외한다.
문단 길이에 따라 기준을 조정하기 위해 `문장 수 × 13`을 1.0 기준으로 사용한다.

```text
information_density = min(1.0, unique_core_content_count / (sentence_count × 13))
```

## concept_repetition

문단 안에서 같은 핵심 내용어가 반복되면 중심 개념을 계속 추적해야 하므로 이해 부담이 커진다.
`concept_repetition`은 반복된 핵심 내용어의 반복 횟수, 어휘 난도, 여러 문장에 걸친 분포를 함께 반영한다.

```text
concept_repetition = min(1.0, concept_repetition_raw / 10.0)

concept_repetition_raw =
  Σ (count - 1) × effective_difficulty × spread × pos_weight
```

계산 기준:

| 항목 | 의미 |
|------|------|
| `count` | 같은 `(lemma, 핵심품사)`의 문단 내 등장 횟수 |
| `effective_difficulty` | 해당 어휘의 lexical difficulty 최댓값을 사용하되, 반복 계산에서는 `max(0.1, min(0.5, difficulty ÷ 1.5))`로 보정 |
| `spread` | 여러 문장에 걸쳐 나오면 가산: `min(1.6, 1.0 + 0.2 × (등장 문장 수 - 1))` |
| `pos_weight` | `NNG/NNP/XR=1.0`, `VV/VA=0.8` |

제외 lemma: `것`, `수`, `때`, `말`, `점`, `등`, `바`, `데`

## 출력 구조

```python
{
    "paragraph": str,
    "score_0_1": float,
    "score_10": float,
    "sentence_count": int,
    "sentences": [dict],
    "paragraph_parts": {
        "sentence_aggregate": float,
        "sentence_mean": float,
        "sentence_top_3_mean": float,
        "sentence_max": float,
        "information_density": float,
        "information_density_full_score_at": int,
        "unique_core_content_count": int,
        "concept_repetition": float,
        "concept_repetition_raw": float,
        "concept_repetition_full_score_at": float,
        "repeated_core_content_count": int,
        "paragraph_weights": dict,
    },
}
```
