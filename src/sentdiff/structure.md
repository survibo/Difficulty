# structure.py — 문장 구조 복잡도 계산

**위치:** `src/sentdiff/structure.py`

## 역할

MorphToken의 POS 태그 패턴과 공통 논리 span matcher 결과를 기반으로 7개 지표로
문장 구조 복잡도를 측정한다.

구조 분석은 어휘 단위와 별개로 형태소 토큰을 사용한다. 따라서 length의
`structure_content_token_count`는 lexical의 `lexical_unit_count`와 다를 수 있다.

## flow 단계

**5단계** — morph에 의존.

## 점수 공식

```
structure = 0.27×length + 0.18×embedding + 0.16×predicate
          + 0.12×modifier + 0.11×repetition + 0.08×logical + 0.08×connective
```

## 7개 지표

Kiwi의 원본 `MorphToken.tag`에 `-I`, `-R` 등의 접미 표지가 붙어도 구조 판정은
기본 태그를 사용한다. 따라서 `VA-I`/`VA-R`은 `VA`, `EC-I`/`EC-R`은 `EC`와
동일하게 각 구조 지표에 포함된다.

| 지표 | 측정 대상 | 1.0이 되는 조건 | 가중치 |
|------|----------|----------------|--------|
| length | 내용어(명/동/형) token 수 | 29개 이상 | 0.27 |
| embedding | 관형형(ETM)+명사형(ETN)+부사형EC(게·도록·듯이) 개수 | 7개 이상 | 0.18 |
| predicate | 서술어(VV, VA, VX, XSV, XSA) 개수 (-1 보정) | 8개 이상 (7+1) | 0.16 |
| modifier | 최장 명사 연쇄 길이 (-1 보정) | 4개 이상 (3+1) | 0.12 |
| repetition | 단어 반복 부담 (반복 횟수×난도×다의성 계수 합계) | 6.0 이상 | 0.11 |
| logical | 논리표지·강한어미 가중합 | 4 이상 | 0.08 |
| connective | EC 개수 | 4개 이상 | 0.08 |

### 보정 설명
- **predicate**: 모든 문장에 서술어가 최소 1개 필수이므로 `predicate_count - 1` 후 score 계산.
- **modifier**: 모든 명사 연쇄는 최소 1개 명사를 포함하므로 `max_noun_chain - 1` 후 score 계산.
- **modifier chain**: NNG/NNP/NNB/XR은 연쇄를 시작·연장한다. XSN은 연쇄 길이에 포함하지 않지만, 앞뒤 명사류를 이어 주는 bridge로 본다. 예: `방법/NNG+론/XSN+적/XSN`은 1, `비교/NNG+적/XSN+안정세/NNG`는 2.

(~~structural_span~~ — 제거됨)

### logical 계산

명시적 논리 관계 표지와 강한 논리 연결 표현을 공통 `PatternMatcher`로 찾은 뒤 가중합을
4로 나눈다. 문장 단위 분석에서는 앞 문맥을 잇는 첫머리 담화 표지가 과대평가될 수 있으므로,
첫 유효 토큰에서 시작하는 논리표지는 제외한다.

```
ls = min(1.0, (첫 유효 토큰 제외 논리표지 가중합 + 강한어미 가중합) / 4)
```

- `따라서 ...`, `즉 ...`처럼 문장 첫 유효 토큰에 온 논리표지는 제외한다.
- 문장 내부 논리표지와 `-므로`, `-지만`, `-더라도` 같은 강한 논리 연결어미는 유지한다.

### 하이브리드 논리 span matcher

- 고정 논리 표현은 원문 문자 span에서 찾는다. 따라서 `다시 말해`, `예를 들어`,
  `그럼에도 불구하고`, `뿐만 아니라`처럼 여러 형태소와 공백으로 구성된 표현도 하나로 잡힌다.
- 겹친 표현은 가장 긴 비중첩 span만 선택한다. 예를 들어 `그럼에도 불구하고`가 매칭되면
  내부의 `그럼에도`를 다시 세지 않는다.
- 강한 연결 표현은 정규화된 형태소 패턴으로 찾는다. 단일 EC뿐 아니라
  `기/ETN + 에/JKB`의 `기에`, `때문/NNB + 에/JKB`의 `때문에`도 지원한다.
- `ᆫ다면`/`ㄴ다면`, `ᆫ데`/`ㄴ데`처럼 Kiwi 종성 자모 표기가 다른 형태는
  `normalize_morph_form()`을 거쳐 같은 규칙으로 판정한다.
- 매칭 결과는 `logical_matches`, `strong_ending_matches`에 원문 문자 span과 토큰 span으로 출력한다.

### repetition 계산

같은 표면형을 가진 내용어가 여러 번 등장할 때, 다의어 판별 부담을 반영한다.

```
표면형별로 등장 횟수 count 수집
제외 lemma: 것, 수, 때, 말, 점, 등, 바, 데

effective_difficulty = max(difficulty, 0.05)
raw = Σ (count - 1) × effective_difficulty × polysemy
score = min(1.0, raw / 6.0)
```

- `difficulty`: lexical lookup 난도값. 반복 계산에서는 최소 0.05로 보정한다.
- `polysemy`: Kiwi analyze(top_n=5) 결과 서로 다른 품사 태그 가짓수

> derivational(명사파생접미사 XSN)은 구조 점수 가중합에서는 제외되었으나,
> 계산 자체는 유지되어 구조 진단 정보로 출력된다.

### connective 계산

EC(연결어미) 개수를 4로 나눈다.

```
cs = min(1.0, EC_개수 / 4)
```

> 부정(negation) 지표는 structure에서 제거되었음.
> → `negation.py`의 `NegationAnalyzer`가 별도 점수로 처리.
> → pipeline에서 `0.5×lexical + 0.5×structure + 0.2×negation`로 통합.

## 논리 표지 예시
- **강한 접속 부사:** 즉, 따라서, 그러므로, 그러나, 만약, 결론적으로 (가중치 0.7~1.0)
- **강한 연결어미:** -(으)므로, -지만, -더라도 (가중치 0.6~1.0)

## 주요 클래스

| 이름 | 설명 |
|------|------|
| `@dataclass StructureConfig` | 7개 지표별 임계값 + 가중치 설정 |
| `StructureScorer` | 구조 점수 계산 |

## 주요 출력 필드

- `structure_parts.structure_content_token_count`: `MorphToken.is_content=True`인 구조용 내용어 토큰 수
- `structure_parts.logical_matches`: 첫 유효 토큰 제외 후 실제 계산에 포함된 고정 논리 표현 span
- `structure_parts.strong_ending_matches`: 실제 계산에 포함된 강한 논리 연결 span
- `structure_parts.derivational_suffix_count`: XSN 기반 진단값. 구조 가중합에는 포함하지 않음

## 의존성
- **import:** `morph.base_sejong_tag`, `patterns.PatternMatcher`
- **상수 export:** `LOGICAL_MARKERS`, `STRONG_LOGICAL_ENDINGS`, `DERIVATIONAL_SUFFIXES`, `ADVERBIAL_EC_FORMS`
- **사용처:** `pipeline.py`
