# 02_score_sentences.py — CLI 문장 분석기

**위치:** `scripts/02_score_sentences.py` (154줄)

## 역할
명령줄에서 문장 난도를 측정하는 CLI 도구. 3가지 모드 지원.

## 실행 모드

```powershell
# 1. 인라인 문장
python scripts/02_score_sentences.py "문장을 분석한다."

# 2. 파일 입력
python scripts/02_score_sentences.py --file data/sentences.txt

# 3. 인터랙티브 모드
python scripts/02_score_sentences.py

# 세부 정보 출력
python scripts/02_score_sentences.py --debug "문장을 분석한다."
```

## 출력 예시

```
  sentence:        문장을 분석한다.
  score_10:        3.12
  lexical_score:   2.89
  structure_score: 3.67
  content_words:   4
  unknown_words:   1
```

## CLI 옵션

| 옵션 | 설명 |
|------|------|
| `sentence` | 분석할 문장 (따옴표) |
| `--file, -f` | 문장이 한 줄씩 있는 파일 경로 |
| `--lexicon, -l` | lexicon CSV 경로 (기본: data/processed/lexicon_master.csv) |
| `--debug` | 점수 세부 구성 요소 출력 |

## 의존성
- **import:** `sentdiff.pipeline`, `sentdiff.lexical`
