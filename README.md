# 한국어 문장 난이도 측정 (sentdiff)

Kiwi 형태소 분석 기반으로 한국어 문장의 어휘 + 구조 난이도를 0~10점으로 측정.

스크립트 실행 순서

| 순서 | 스크립트                          | 역할                                                                                  | 사전 조건                                                |
| ---- | --------------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| 1    | `scripts/01_build_lexicon.py`   | vocab_40k →`data/processed/lexicon_master.csv` 생성    | `data/raw/vocab_40k.xlsx` |
| 2    | `scripts/02_score_sentences.py` | CLI 문장 난이도 측정 (인라인/파일/인터랙티브 3가지 모드)                              | 1번 완료                                                 |
| 3    | `scripts/test_server.py`        | HTTP 서버 실행 →`index.html` + 문장 `/api/score`, 문단 `/api/score-paragraph` API | 1번 완료                                                 |

> 2, 3은 병행 가능. 둘 다 1번이 선행되어야 함.

## 설치

```powershell
pip install -r requirements.txt
```

## 사용법

```powershell
# 1. 사전 생성
python scripts/01_build_lexicon.py

# 2. CLI 문장 분석
python scripts/02_score_sentences.py "이 문제는 생각보다 어렵다"

# 3. 웹 서버
python scripts/test_server.py  # http://localhost:8800
```

웹 UI는 문장 분석과 문단 분석을 모두 지원한다. 문단 분석은 4문장 이상에서만 작동한다.

## 의존성

- kiwipiepy (형태소 분석)
- pandas, openpyxl, xlrd (엑셀 처리)
