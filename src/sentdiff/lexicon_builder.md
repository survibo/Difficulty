# lexicon_builder.py — 어휘 사전 구축

**위치:** `src/sentdiff/lexicon_builder.py`

## 역할

4만 개 5등급 어휘 목록(vocab_40k.xlsx)을 읽어 `lexicon_master.csv`를 생성한다.
생성된 사전은 `lexical.py`의 `LexiconScorer`가 lookup에 사용한다.

## flow 단계

**2단계** — normalize.py에 의존하여 사전을 만든다. 파이프라인 실행 전 1회만 실행.

## 입력

| 파일                      | 출처            | 시트    | 설명              |
| ------------------------- | --------------- | ------- | ----------------- |
| `data/raw/vocab_40k.xlsx` | 5등급 어휘 목록 | sheet 5 | 약 4만개, 1~5등급 |

## 계산 원리

### 1. 4만 목록 로드 (`load_vocab_40k`)

- 표준 컬럼: `lemma`, `homograph_no`, `pos_norm`, `grade_5`, `origin`, `domain`, `meaning`
- 원본 동형어번호 컬럼은 `표준동형어번호수정`이며, 빌드 시 `homograph_no`로 정규화한다.
- 유효 lemma 필터, 완전 중복 제거

### 2. 난도 계산 (`add_difficulty_columns`)

**2개 신호 가중 결합 (합 1.0):**

| 신호                     | 비중 | 출처                   |
| ------------------------ | ---- | ---------------------- |
| `grade5_diff`          | 0.95 | 4만 목록 5등급 → 1.00 |
| `origin_domain_signal` | 0.05 | 어종/분야 신호         |

**공식:**

```
difficulty = weighted_available(
    [grade5_diff, origin_domain_signal],
    [0.95, 0.05]
)
```

신호가 전혀 없으면 `default_difficulty = 0.30`.

### 3. 파생어 난도 보정 (`adjust_derivational_difficulty`)

X하다/X되다/X시키다 파생 표제어의 난도를 base lemma 기준으로 완화.

**공식:**

```
adjusted = (base_difficulty × 0.60) + (raw_difficulty × 0.40) + penalty
adjusted = max(adjusted, raw_difficulty - 0.35)  # 최대 하락 폭 제한
```

- 하향 조정만 허용 (`derivational_adjust_only_downward = True`)
- base lemma가 명사/어근 품사인 경우만 적용
- base lemma의 대표 행 선택: 명사/어근 품사 우선 → 난도 → 동형어번호

### 4. 최종 정리 (`finalize_lexicon`)

- 컬럼 정렬 및 타입 정리
- `entry_id` 생성 (1부터 시작)
- `source` 레이블: `vocab_40k_only`
- write to `data/processed/lexicon_master.csv`

## 의존성

- **import:** `pandas`, `numpy`, `normalize`
- **사용처:** `lexical.py`가 `lexicon_master.csv`를 읽어 lookup에 사용
