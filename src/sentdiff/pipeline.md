# pipeline.py — 통합 파이프라인

**위치:** `src/sentdiff/pipeline.py` (67줄)

## 역할
KiwiMorphAnalyzer + LexiconScorer + StructureScorer를 내부에서 조립해, 문장 하나를 입력받으면 최종 난도 점수까지 한 번에 계산하는 통합 인터페이스.

## 점수 공식

```
score = 0.60 × lexical_score + 0.40 × structure_score
```

## 주요 클래스

| 이름 | 설명 |
|------|------|
| `SentenceScorer` | 통합 파이프라인 |

## 사용법

```python
from sentdiff.pipeline import SentenceScorer

scorer = SentenceScorer()
result = scorer.score("문장을 분석한다.")
print(result["score_10"])  # 0~10 사이 최종 점수
```

## 반환 dict 구조

| 키 | 설명 |
|---|------|
| `score_0_1` / `score_10` | 최종 점수 |
| `lexical_score_0_1` / `lexical_score_10` | 어휘 점수 |
| `structure_score_0_1` / `structure_score_10` | 구조 점수 |
| `content_token_count` / `unknown_token_count` | 내용어/미등록어 개수 |
| `scored_words` | 각 내용어 lookup 결과 리스트 |
| `score_parts` | 어휘 점수 breakdown |
| `structure_parts` | 구조 점수 breakdown |
| `lexical_weight` / `structure_weight` | 현재 적용된 가중치 |

## 의존성
- **import:** `morph.py`, `lexical.py`, `structure.py`
- **사용처:** 외부 스크립트(`02_score_sentences.py`, `test_server.py`)
