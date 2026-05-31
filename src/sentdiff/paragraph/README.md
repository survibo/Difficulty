# paragraph — 문단 단위 난도 분석

문단 분석은 기존 문장 분석기(`SentenceScorer`)를 변경하지 않고, 문장별 결과를 문단 단위로 집계한다.

## 위치

- 패키지: `src/sentdiff/paragraph/`
- 진입점: `ParagraphScorer`

## 공식

```text
paragraph_score =
  0.80 × sentence_aggregate
+ 0.20 × information_density
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

문단 전체에서 서로 다른 내용어 lexical item `(lemma, pos)` 수를 정보량으로 본다. 문단 길이에 따라 기준을 조정하기 위해 `문장 수 × 10`을 1.0 기준으로 사용한다.

```text
information_density = min(1.0, unique_content_lexical_count / (sentence_count × 10))
```

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
        "unique_content_lexical_count": int,
        "paragraph_weights": dict,
    },
}
```
