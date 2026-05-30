# structure.py — 문장 구조 복잡도 계산

**위치:** `src/sentdiff/structure.py` (274줄)

## 역할
MorphToken의 POS 태그 패턴을 기반으로 7개 지표로 문장 구조 복잡도를 측정한다.

## 점수 공식

```
structure = 0.20×length + 0.20×predicate + 0.20×embedding
          + 0.15×connective + 0.15×logical
          + 0.05×modifier + 0.05×derivational
```

## 7개 지표

| 지표 | 측정 대상 | 1.0이 되는 조건 | 가중치 |
|------|----------|----------------|--------|
| length | 내용어(명/동/형) token 수 | 30개 이상 | 0.20 |
| predicate | 서술어(VV, VA, VCP, VCN) 개수 (-1 보정) | 7개 이상 (6+1) | 0.20 |
| embedding | 관형형(ETM)+명사형(ETN) 개수 | 4개 이상 | 0.20 |
| connective | 연결어미(EC) 개수 | 5개 이상 | 0.15 |
| logical | 논리표지+강한어미+약한어미 가중합 | 4.0 이상 | 0.15 |
| modifier | 최장 명사 연쇄 길이 (-1 보정) | 6개 이상 (5+1) | 0.05 |
| derivational | 파생 접사 개수 | 5개 이상 | 0.05 |

### 보정 설명
- **predicate**: 모든 문장에 서술어가 최소 1개 필수이므로 `predicate_count - 1` 후 score 계산.
- **modifier**: 모든 명사 연쇄는 최소 1개 명사를 포함하므로 `max_noun_chain - 1` 후 score 계산.

## 논리 표지 예시
- **강한 접속 부사:** 즉, 따라서, 그러므로, 그러나, 만약, 결론적으로 (가중치 0.7~1.0)
- **강한 연결어미:** -(으)므로, -지만, -더라도 (가중치 0.6~1.0)
- **약한 연결어미:** -고(0.3), -며(0.4), -거나(0.5)

## 주요 클래스

| 이름 | 설명 |
|------|------|
| `@dataclass StructureConfig` | 7개 지표별 임계값 + 가중치 설정 |
| `StructureScorer` | 구조 점수 계산 |

## 의존성
- **import:** stdlib만 사용 (다른 sentdiff 파일 import 없음)
- **사용처:** `pipeline.py`
