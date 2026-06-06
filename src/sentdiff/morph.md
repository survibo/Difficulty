# morph.py — Kiwi 형태소 분석 래퍼

**위치:** `src/sentdiff/morph.py`

## 역할

kiwipiepy의 형태소 분석 결과를 프로젝트 공통 `MorphToken` 리스트로 변환한다.
문자열 정규화, Sejong 태그→품사명 변환, 내용어 판정, lemma 후보 생성 등 형태소 수준의
전처리를 담당한다.

`MorphToken`은 구조 길이·서술어·명사 연쇄와 부정 표지를 판정하는 가장 작은 분석 단위다.
어휘 난도는 `MorphToken`을 그대로 하나씩 채점하지 않고, `lexical_units.py`가 여러 토큰을
하나의 `LexicalUnit`으로 묶은 뒤 채점한다. 논리 표현과 절 경계도 별도 span matcher가
`MorphToken`의 위치와 정규화된 형태를 사용해 판정한다.

## flow 단계

**3단계** — normalize.py에 의존. lexical unit resolver, structure, pattern matcher,
negation이 모두 morph token을 입력으로 받는다.

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

`tag`에는 Kiwi가 반환한 원본 태그를 보존한다. 실제 규칙 비교에는 `base_sejong_tag()`와
`normalize_morph_form()`을 사용한다.

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
Kiwi가 붙이는 `-I`, `-R` 등의 접미 표지는 원본 `MorphToken.tag`에는 보존하되,
품사 판정에서는 `base_sejong_tag()`로 제거한다. 따라서 `VA-I`, `VA-R`은 모두 형용사로 처리된다.

특수 태그의 품사명:

| 태그 | 품사명 | 점수 정책 |
|------|--------|-----------|
| `XSM` | 접사 | 독립 어휘로 채점하지 않고 파생 부사 어휘 단위의 구성 요소로 사용 |
| `W_*` | 웹표현 | 어휘·구조 점수에서 제외하고 원시 토큰/디버그 정보에만 보존 |
| `Z_*` | 분석보조 | 어휘·구조 점수에서 제외하고 원시 토큰/디버그 정보에만 보존 |

### 2. Lemma 후보 생성 (`token_to_lemma_candidate`)

```
"먹", "VV" → "먹다"   (VV/VA에 "다" 추가)
"그렇", "VA-I" → "그렇다"
"세계", "NNG" → "세계" (그대로)
```

사전 lookup용. VV/VA는 어간 형태이므로 "다"를 붙여 기본형 생성.
`-I`, `-R` 등의 접미 표지가 붙은 VV/VA도 같은 방식으로 처리한다.

### 3. 기능 표지 판정 (`is_excluded_lexical_tag`)

어휘 난도 계산에서 제외할 태그를 판정한다.
제외 대상: VX, XSV, XSA, XPN, XSN, XSM, `W_*`, `Z_*`,
J\*(조사), E\*(어미), S\*(기호)

제외된 접사도 어휘 단위 resolver가 전체 표제어를 복원할 때는 span 구성 요소로 사용할 수 있다.

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

이 값은 두 용도로 사용된다.

- structure의 `structure_content_token_count`: `is_content=True`인 형태소 토큰 수
- lexical unit resolver: 사전 span 후보가 실제 내용어를 포함하는지와 후보의 포괄 범위 판단

따라서 `structure_content_token_count`와 `lexical_unit_count`는 서로 다를 수 있다.

### 5. 공통 정규화 (`base_sejong_tag`, `normalize_morph_form`, `morph_tag_role`)

- `base_sejong_tag(tag)`: `VA-I`, `VV-R`, `EC-I`처럼 `-` 뒤에 붙은 Kiwi 부가 표지를
  제거하고 `VA`, `VV`, `EC`를 반환한다.
- `normalize_morph_form(value)`: 종성 자모 `ᆫ`, `ᆯ` 등을 비교 가능한 호환 자모
  `ㄴ`, `ㄹ`로 통일한다. 연결어미·인용·조건 경계 판정은 이 표준형을 사용한다.
- `morph_tag_role(tag)`: 구조 계산과 `--debug`가 공유하는 역할 이름을 반환한다.
  `XSM`은 `lexical_component`, `W_*`/`Z_*`는 `excluded`로 표시한다.

### 6. Token 변환 (`_token_to_morph_token`)

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
- **사용처:** `lexical_units.py`, `lexical.py`, `patterns.py`, `structure.py`, `negation.py`, `pipeline.py`
