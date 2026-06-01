# morph.py — Kiwi 형태소 분석 래퍼

**위치:** `src/sentdiff/morph.py`

## 역할

kiwipiepy의 형태소 분석 결과를 프로젝트 공통 `MorphToken` 리스트로 변환한다.
문자열 정규화, Sejong 태그→품사명 변환, 내용어 판정, lemma 후보 생성 등 형태소 수준의
전처리를 담당한다.

## flow 단계

**3단계** — normalize.py에 의존. lexical, structure, negation이 모두 morph token을 입력으로 받는다.

## 핵심 데이터 구조

### MorphToken (`@dataclass(frozen=True)`)

| 필드 | 설명 | 출처 |
|------|------|------|
| `surface` | 표면형 | `token.form` |
| `lemma` | lookup용 후보 lemma | `token_to_lemma_candidate(surface, tag)` |
| `tag` | Sejong POS 태그 | `token.tag` |
| `pos` | 한글 품사명 | `sejong_tag_to_pos(tag)` |
| `start` | 문장 내 시작 위치 | `token.start` |
| `end` | 문장 내 끝 위치 | 계산됨 |
| `is_content` | 내용어 여부 | `is_content_tag(tag)` |

## 주요 함수

### 1. 태그→품사명 변환 (`sejong_tag_to_pos`)

```
"NN" → "명사"
"VV" → "동사"
"VCP"/"VCN" → "지정사"
"VX" → "보조용언"
"MAG" → "부사"
etc.
```

규칙 기반 매핑. 불명 태그는 원래 문자열 반환.

### 2. Lemma 후보 생성 (`token_to_lemma_candidate`)

```
"먹", "VV" → "먹다"   (VV/VA에 "다" 추가)
"세계", "NNG" → "세계" (그대로)
```

사전 lookup용. VV/VA는 어간 형태이므로 "다"를 붙여 기본형 생성.

### 3. 기능 표지 판정 (`is_excluded_lexical_tag`)

어휘 난도 계산에서 제외할 태그를 판정한다.
제외 대상: VX, XSV, XSA, XPN, XSN, J\*(조사), E\*(어미), S\*(기호)

### 4. 내용어 판정 (`is_content_tag`)

lexical/structure 양쪽에서 공용. `is_excluded_lexical_tag`가 아니면서
명사/대명사/수사/동사/형용사/부사/어근/외국어/한자인 경우 true.
단, `NNB` 의존명사는 lexical/content 후보에서 제외한다.

**POS 기준:**

```
is_content = not is_excluded AND (
    (starts_with("NN") AND tag != "NNB") OR
    in {"NP", "NR", "VV", "VA", "MAG", "XR", "SL", "SH"}
)
```

### 5. Token 변환 (`_token_to_morph_token`)

Kiwi token의 각 속성을 읽어 `MorphToken` 객체로 변환.
`end` 위치는 Kiwi의 `end` 속성 또는 `start + len`으로 계산.

## 클래스

### KiwiMorphAnalyzer

| 메서드 | 역할 |
|--------|------|
| `analyze(sentence)` | 문장 분석 → MorphToken 리스트 |
| `content_tokens(sentence)` | 내용어만 필터링 |

분석 결과가 비었거나 빈 문장이면 빈 리스트 반환.

**분석 방식:** `kiwi.analyze(text, top_n=1)` — 1-best 결과만 사용.

## 의존성

- **import:** `normalize`, `kiwipiepy` (optional, 런타임에 import)
- **사용처:** `lexical.py` `score_tokens()`, `structure.py` `score_tokens()`, `negation.py` `analyze()`, `pipeline.py`
