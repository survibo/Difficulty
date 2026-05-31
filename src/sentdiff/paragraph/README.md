# paragraph — 문단 단위 난도 분석

문단 분석은 기존 문장 분석기(`SentenceScorer`)를 변경하지 않고, 문장별 결과를 문단 단위로 집계한다.

## 위치

- 패키지: `src/sentdiff/paragraph/`
- 진입점: `ParagraphScorer`

## 공식

```text
paragraph_score =
  0.80 × sentence_aggregate
+ 0.10 × information_density
+ 0.10 × concept_repetition
```

## sentence_aggregate

문단 안 문장 점수의 평균, 상위 3개 평균, 최댓값을 함께 사용한다.

```text
sentence_aggregate =
  0.40 × sentence_mean
+ 0.40 × sentence_top_3_mean
+ 0.20 × sentence_max
```

## discourse_marker_score

문장 단위 분석에서는 첫머리 logical marker를 제외하지만, 문단 분석에서는 참고 진단값으로 문장 첫머리 담화 표지를 집계한다. 현재 문단 최종 점수에는 반영하지 않는다.

예: `그러나`, `따라서`, `한편`, `결국`, `또한`, `그럼에도 불구하고`

```text
discourse_marker_score = min(1.0, discourse_marker_weighted / sentence_count)
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
문단 길이에 따라 기준을 조정하기 위해 `문장 수 × 10`을 1.0 기준으로 사용한다.

```text
information_density = min(1.0, unique_core_content_count / (sentence_count × 10))
```

## concept_repetition

문단 안에서 같은 핵심 내용어가 반복되면 중심 개념을 계속 추적해야 하므로 이해 부담이 커진다.
`concept_repetition`은 반복된 핵심 내용어의 반복 횟수, 어휘 난도, 여러 문장에 걸친 분포를 함께 반영한다.

```text
concept_repetition = min(1.0, concept_repetition_raw / 10.0)

concept_repetition_raw =
  Σ (count - 1) × difficulty × spread × pos_weight
```

계산 기준:

| 항목 | 의미 |
|------|------|
| `count` | 같은 `(lemma, 핵심품사)`의 문단 내 등장 횟수 |
| `difficulty` | 해당 어휘의 lexical difficulty. 여러 값이 있으면 최댓값 |
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
        "discourse_marker_score": float,
        "discourse_marker_weighted": float,
        "discourse_marker_count": int,
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
