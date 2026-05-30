문장의 정량적 난이도 측정하기

sentence-difficulty/
│
├── requirements.txt
├── configs/
│   └── default.yaml
│
├── data/
│   ├── raw/
│   │   ├── vocab_5965.xlsx
│   │   └── vocab_40k.xlsx
│   ├── external/
│   │   ├── logic_markers.csv
│   │   ├── abstract_terms.csv
│   │   └── event_nouns.csv
│   └── processed/
│       └── lexicon_master.csv
│
├── src/
│   └── sentdiff/
│       ├── __init__.py
│       ├── normalize.py
│       ├── morph.py
│       ├── lexicon_builder.py
│       ├── lexical.py
│       ├── proposition.py
│       ├── embedding.py
│       ├── logic.py
│       ├── scoring.py
│       └── pipeline.py
│
└── scripts/
    ├── 01_build_lexicon.py
    └── 02_score_sentences.py

==

README.md
- 프로젝트 설명
- 설치 방법
- 실행 방법
- 지표 정의
- 출력값 설명

requirements.txt
- 필요한 Python 패키지 목록
- kiwipiepy, pandas, numpy, openpyxl, pyyaml, scikit-learn, stanza, openai 등

.env.example
- LLM API 키 예시
- OPENAI_API_KEY=your_api_key_here

.gitignore
- .env
- __pycache__/
- data/processed/
- outputs/
- *.pyc

configs/default.yaml
- 가중치 설정
- 파일 경로 설정
- LLM 사용 여부
- 형태소 분석기 설정
- 의존구문 분석기 사용 여부

==

data/raw/vocab_5965.xlsx
- 5965개 단어 1/2/3단계 또는 A/B/C 등급 엑셀 원본

data/raw/vocab_40k.xlsx
- 2억 어절 기반 4만 개 5등급 어휘 엑셀 원본

data/external/terminology.csv
- 전문어 목록
- term,domain,source 형태 권장

data/external/abstract_terms.csv
- 추상어/개념어 목록
- term,category,source 형태 권장

data/external/event_nouns.csv
- 사건명사 목록
- term,category,weight 형태 권장

data/external/logic_markers.csv
- 조건, 원인, 양보, 대조, 비교, 부정 표지 목록
- marker,relation,weight 형태 권장

data/processed/lexicon_master.csv
- vocab_5965.xlsx와 vocab_40k.xlsx를 병합한 최종 어휘 난도 사전
- 자동 생성 파일

data/processed/sentence_scores.csv
- 문장별 난이도 점수 결과
- 자동 생성 파일

==

src/sentdiff/__init__.py
- 패키지 초기화 파일

src/sentdiff/config.py
- YAML 설정 파일 로드
- 경로, 가중치, 옵션 관리

src/sentdiff/schemas.py
- 분석 결과 데이터 구조 정의
- SentenceScore, WordScore, LLMJudgeResult 같은 dataclass 또는 pydantic schema

src/sentdiff/resources.py
- lexicon_master.csv, terminology.csv, logic_markers.csv 등 외부 자원 로드
- 사전 lookup 기능 제공

src/sentdiff/normalize.py
- 단어 정규화
- 동형어번호 분리
- 등급 변환
- 품사명 통일
- 어종/분야 신호와 파생 표제어 suffix 처리

src/sentdiff/morph.py
- Kiwi 형태소 분석 래퍼
- 문장 → 형태소, 품사, 내용어 추출
- 동사/형용사 기본형 후보 생성

src/sentdiff/lexicon_builder.py
- vocab_5965.xlsx와 vocab_40k.xlsx 병합
- lemma + pos + homograph_no 기준 정리
- word_difficulty 계산
- lexicon_master.csv 생성

src/sentdiff/lexical.py
- 어휘·개념 난도 계산
- 평균 난도, 상위 2개 난도, 최대 난도 계산
- 전문어, 추상어, 미등록어 처리

src/sentdiff/proposition.py
- 명제 밀도 계산
- 서술어 수
- 명사화 표현 수
- 사건명사 수
- 판단 표현 후보 수

src/sentdiff/embedding.py
- 절 내포 깊이 계산
- 관형사형 어미 ETM
- 명사형 어미 ETN
- 연결어미 EC
- 인용절 표지
- 내포 깊이 근사값 계산

src/sentdiff/dependency.py
- 의존거리 계산
- Stanza 기반 분석
- 평균 의존거리
- 최대 의존거리
- 핵심 서술어 지연도

src/sentdiff/logic.py
- 논리 관계 복잡도 계산
- 조건, 원인, 양보, 대조, 비교, 부정 표지 탐지
- 이중부정 후보 탐지
- 논리 표지 기반 점수 계산

src/sentdiff/llm_judge.py
- LLM API 호출
- 동형어 선택
- 핵심 개념어 판정
- 명제 수 추정
- 논리 관계 중첩 판정
- JSON 응답 검증

src/sentdiff/scoring.py
- 5개 핵심 지표를 최종 점수로 합산
- 가중치 적용
- 0~10 스케일 변환
- confidence 반영

src/sentdiff/pipeline.py
- 전체 분석 파이프라인
- 문장 입력 → 형태소 분석 → 사전 lookup → 5개 지표 계산 → 최종 점수 산출

src/sentdiff/cli.py
- 터미널 실행용 인터페이스
- 단일 문장 분석
- txt/csv 파일 분석
==
scripts/01_build_lexicon.py
- raw 엑셀 2개를 읽어서 lexicon_master.csv 생성

scripts/02_score_sentences.py
- sample_sentences.txt의 문장들을 분석
- 결과를 outputs/scores/에 저장

scripts/03_score_csv.py
- sentence 컬럼이 있는 CSV 파일을 입력받아 대량 분석
- sentence_scores.csv 생성

scripts/04_evaluate_with_human_labels.py
- 사람이 매긴 난이도 라벨과 모델 점수 비교
- 상관계수, MAE, RMSE 계산
- Ridge/RandomForest 검증

scripts/05_error_analysis.py
- 모델이 크게 틀린 문장 추출
- 오류 유형 분석용 CSV 생성

==

tests/test_normalize.py
- 동형어번호 분리 테스트
- 등급 변환 테스트
- 품사명 정규화 테스트

tests/test_lexicon_builder.py
- 두 엑셀 병합 테스트
- difficulty 계산 테스트
- 결측값 처리 테스트

tests/test_lexical.py
- 어휘 난도 계산 테스트
- 미등록어 처리 테스트
- 상위 난도 단어 계산 테스트

tests/test_logic.py
- 조건/양보/부정 표지 탐지 테스트
- 이중부정 후보 탐지 테스트

tests/test_pipeline.py
- 전체 문장 분석 결과 형식 테스트
- total_score 산출 테스트
