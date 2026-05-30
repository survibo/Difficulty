# lexicon_builder.py — 난도 사전 생성

**위치:** `src/sentdiff/lexicon_builder.py` (1060줄)

## 역할
두 개의 엑셀 원본(vocab_5965.xls, vocab_40k.xlsx)을 읽어 병합하고 난도를 계산해 `lexicon_master.csv`를 생성한다.

## 난도 계산식

| 요소 | 출처 | 가중치 |
|------|------|--------|
| 5등급 난도 | 4만 어휘 목록(1~5등급 → 0.0~1.0) | **0.80** |
| 보조 난도 | 5965 목록(A/B=0.0, C=0.25) | **0.10** |
| 순위 난도 | 5965 목록 내 순위 기반 | **0.05** |
| 어종/분야 신호 | 한자/전문 분야 보정 | **0.05** |

### 파생어 보정
`X-하다` / `X-되다` / `X-시키다` 형태는 base lemma(명사)의 난도를 상속받아 난도를 낮춘다.

## 처리 순서

```
vocab_40k.xlsx ──┐
                 ├── 병합 ──→ 난도 계산 ──→ 파생어 보정 ──→ 최종 CSV 저장
vocab_5965.xls  ─┘
```

## 주요 함수

| 함수 | 설명 |
|------|------|
| `load_vocab_40k(config)` | 40k 목록 로드 |
| `load_vocab_5965(config)` | 5965 목록 로드 |
| `_merge_main_with_aux()` | 두 목록 병합 |
| `add_difficulty_columns()` | 가중치 기반 난도 계산 |
| `adjust_derivational_difficulty()` | X-하다 계열 난도 보정 |
| `finalize_lexicon()` | 컬럼 정리, CSV 저장 |
| `build_lexicon()` | 메인 진입점 |

## 의존성
- **import:** `normalize.py`, 외부 `pandas`, `xlrd`, `openpyxl`
- **출력:** `data/processed/lexicon_master.csv` (~13MB, 42,000+ entries)
- **사용처:** `01_build_lexicon.py` (독립 실행)
