# structure.py — 문장 구조 복잡도 계산

**위치:** `src/sentdiff/structure.py`

## 역할

MorphToken의 POS 태그 패턴을 기반으로 7개 지표로 문장 구조 복잡도를 측정한다.

## flow 단계

**5단계** — morph에 의존.

## 점수 공식

```
structure = 0.20×predicate + 0.20×embedding
          + 0.15×connective_logical
          + 0.15×length + 0.15×structural_span
          + 0.08×modifier
          + 0.07×repetition

## 7개 지표

| 지표 | 측정 대상 | 1.0이 되는 조건 | 가중치 |
|------|----------|----------------|--------|
| predicate | 서술어(VV, VA, VCP, VCN, VX, XSV, XSA) 개수 (-1 보정) | 8개 이상 (7+1) | 0.20 |
| embedding | 관형형(ETM)+명사형(ETN) 개수 | 4개 이상 | 0.20 |
| connective_logical | (EC 개수/4 × 1 + 논리표지·강한어미 가중합/4 × 2) / 3 | 각각 1.0 | 0.15 |
| length | 내용어(명/동/형) token 수 | 23개 이상 | 0.15 |
| structural_span | 절 구간 내용어 합계 (모든 EC/ETM/ETN에서 기록된 구간 길이의 총합) | 20.0 이상 (내용어 20개) | 0.15 |
| modifier | 최장 명사 연쇄 길이 (-1 보정) | 5개 이상 (4+1) | 0.08 |
| repetition | 단어 반복 부담 (반복 횟수×난도×다의성 계수 합계) | 3.5 이상 | 0.07 |

### repetition 계산

같은 표면형을 가진 내용어가 여러 번 등장할 때, 다의어 판별 부담을 반영한다.

```
표면형별로 등장 횟수 count 수집
제외 lemma: 것, 수, 때, 말, 점, 등, 바, 데

raw = Σ (count - 1) × difficulty × polysemy
score = min(1.0, raw / 3.5)
```

- `difficulty`: lexical lookup 난도값
- `polysemy`: Kiwi analyze(top_n=5) 결과 서로 다른 품사 태그 가짓수

> derivational(명사파생접미사 XSN)은 구조 점수 가중합에서는 제외되었으나,
> 계산 자체는 유지되어 구조 진단 정보로 출력된다.

### connective_logical 계산

연결 구조와 논리 표지를 **1:2 가중평균**으로 결합한다.

```
cs = min(1.0, EC_개수 / 4)
ls = min(1.0, (논리표지 가중합 + 강한어미 가중합) / 4)
score = (cs × 1 + ls × 2) / 3
```

### 보정 설명
- **predicate**: 모든 문장에 서술어가 최소 1개 필수이므로 `predicate_count - 1` 후 score 계산.
- **modifier**: 모든 명사 연쇄는 최소 1개 명사를 포함하므로 `max_noun_chain - 1` 후 score 계산.

### structural_span 계산

ETM(관형형전성어미), ETN(명사형전성어미), EC(연결어미)가 나타날 때,
직전 절 경계(EC/EF/SF/SP/SE) 이후부터 해당 marker까지 누적된 내용어 개수의 **합계**를 측정한다.

```
segment_content_count = 0

for token in tokens:
    if token.is_content:
        segment_content_count += 1
    if token.tag in {ETM, ETN, EC} and segment_content_count > 0:
        spans.append(segment_content_count)
    if token.tag in {EC, EF, SF, SP, SE}:
        if not (token.tag == "EC" and 뒤에 VX가 3토큰 이내):
            segment_content_count = 0

raw = mean(spans)  →  raw = sum(spans)
normalized = raw / 5.5  →  normalized = raw / 20.0
score = min(1.0, normalized)
```

- EC는 marker이면서 boundary이므로, span 기록 후 segment를 초기화한다.
- 단, **aux EC** (EC + 3토큰 이내 VX)는 boundary로 보지 않는다. `먹고 싶다`, `유지하고 있다` 식의 보조용언 연결은 절 경계가 아니다.
- ETM/ETN은 boundary가 아니므로 span만 기록하고 segment는 유지한다.
- marker 직전 내용어가 없으면(segment_content_count == 0) 해당 marker는 제외한다.
- spans가 비어 있으면 0.0 반환.
- **full_score_at = 20.0** (모든 구간 내용어 합계가 20개 이상이면 1.0)

> 부정(negation) 지표는 structure에서 제거되었음.
> → `negation.py`의 `NegationAnalyzer`가 별도 점수로 처리.
> → pipeline에서 `0.5×lexical + 0.5×structure + 0.3×negation`로 통합.

## 논리 표지 예시
- **강한 접속 부사:** 즉, 따라서, 그러므로, 그러나, 만약, 결론적으로 (가중치 0.7~1.0)
- **강한 연결어미:** -(으)므로, -지만, -더라도 (가중치 0.6~1.0)

## 주요 클래스

| 이름 | 설명 |
|------|------|
| `@dataclass StructureConfig` | 7개 지표별 임계값 + 가중치 설정 |
| `StructureScorer` | 구조 점수 계산 |

## 의존성
- **import:** stdlib만 사용 (다른 sentdiff 파일 import 없음)
- **상수 export:** `LOGICAL_MARKERS`, `STRONG_LOGICAL_ENDINGS`, `WEAK_CONNECTIVE_ENDINGS`, `DERIVATIONAL_SUFFIXES`
- **사용처:** `pipeline.py`
