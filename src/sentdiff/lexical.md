# lexical.py — 어휘 난도 계산

**위치:** `src/sentdiff/lexical.py` (381줄)

## 역할
MorphToken 리스트의 내용어를 `lexicon_master.csv`에서 lookup해 각 단어 난도를 찾고, 문장 단위 어휘 난도 점수를 계산한다.

## lookup 순서 (fallback)
1. **(lemma, POS)** 정확 일치
2. **base + POS** → (base, 명사) → (base, 어근)
3. **lemma만** 일치
4. **base만** 일치
5. **unknown** (난도 0.30)

## 점수 공식

| 항목 | 설명 | 가중치 |
|------|------|--------|
| `mean_all` | 모든 내용어 난도의 평균 | **0.25** |
| `mean_top_3` | 상위 3개 낱말 난도 평균 | **0.50** |
| `max` | 최고 난도 낱말 1개 | **0.25** |

```
lexical = 0.25 × mean_all + 0.50 × mean_top_3 + 0.25 × max
```

## 주요 클래스

| 이름 | 설명 |
|------|------|
| `@dataclass LexiconConfig` | lexicon_path, unknown_difficulty(0.30), aggregation(min) |
| `@dataclass LexiconEntry` | entry_id, lemma, pos, difficulty |
| `@dataclass LexicalMatch` | surface, lemma, pos, difficulty, match_method |
| `LexiconScorer` | 사전 로딩 → lookup → 점수 계산 |

## 의존성
- **import:** `normalize.py`, 외부 `pandas`, `statistics`
- **사용처:** `pipeline.py`
