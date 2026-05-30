# 01_build_lexicon.py — 사전 생성 스크립트

**위치:** `scripts/01_build_lexicon.py` (22줄)

## 역할
`lexicon_builder.build_lexicon()`을 호출해 `data/processed/lexicon_master.csv`를 생성한다.

## 실행

```powershell
python scripts/01_build_lexicon.py
```

## 출력 예시

```
lexicon_master.csv 생성 완료
n_entries: 42922
n_unique_lemmas: 37802
source_counts: {'vocab_40k_only': 36948, 'both': 3052, 'vocab_5965_only': 2922}
difficulty_mean: 0.65
difficulty_min: 0.0
difficulty_max: 1.0
```

## 의존성
- **import:** `sentdiff.lexicon_builder`
- **사용처:** `data/raw/vocab_40k.xlsx` + `vocab_5965.xls` 필요
