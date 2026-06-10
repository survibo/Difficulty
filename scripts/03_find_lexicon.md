# 03_find_lexicon.py - lexicon lemma 위치 검색

**위치:** `scripts/03_find_lexicon.py`

## 역할

`lexicon_master.csv`의 두 번째 열인 `lemma`를 검색해 해당 CSV 레코드의 시작 행 번호와
전체 비어 있지 않은 필드를 출력한다. 동형어처럼 같은 lemma가 여러 행에 있으면 모두 출력한다.

## 실행

```powershell
# 정확히 일치하는 lemma 검색
.\venv\Scripts\python.exe scripts\03_find_lexicon.py "유동성"

# lemma에 검색어가 포함된 행 검색
.\venv\Scripts\python.exe scripts\03_find_lexicon.py "유동" --contains

# 다른 CSV 파일 검색
.\venv\Scripts\python.exe scripts\03_find_lexicon.py "유동성" --file path\to\lexicon.csv
```

## 출력 예시

```text
2 match(es)
data\processed\lexicon_master.csv:12345
  entry_id: 12344
  lemma: 유동성
  difficulty: 0.7
  pos: 명사
  meaning: 흐르거나 움직일 수 있는 성질
```

`경로:행 번호`는 여러 줄짜리 `meaning` 셀이 있더라도 해당 CSV 레코드가 시작하는 실제
물리 행 번호를 가리킨다.

## 종료 코드

|  코드 | 의미                                              |
| ----: | ------------------------------------------------- |
| `0` | 하나 이상의 행을 찾음                             |
| `1` | 검색 결과 없음                                    |
| `2` | 파일 읽기 실패 또는 두 번째 열이 `lemma`가 아님 |
