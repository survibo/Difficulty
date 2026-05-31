# 문장 난이도 측정 파이프라인 — 계산식 중심 개요

## 0. sentdiff 모듈 실행 순서

| 순서 | 모듈                   | 역할                                                      | 의존                                |
| ---- | ---------------------- | --------------------------------------------------------- | ----------------------------------- |
| 1    | `normalize.py`       | 텍스트 정규화, 등급→난도 변환, 유틸리티                  | —                                  |
| 2    | `lexicon_builder.py` | vocab_40k →`lexicon_master.csv` 생성                   | normalize                           |
| 3    | `morph.py`           | Kiwi 형태소 분석 →`MorphToken` 리스트                  | normalize                           |
| 4    | `lexical.py`         | 사전 lookup → 내용어 난도 → 어휘 점수(lexical)          | normalize, morph                    |
| 5    | `structure.py`       | 품사 태그 8개 지표 → 구조 점수(structure)                | morph                               |
| 6    | `negation.py`        | 부정 표지 분석 → 부정 처리 부담 점수(negation)           | morph                               |
| 7    | `pipeline.py`        | `SentenceScorer` — lexical + structure + negation 통합 | morph, lexical, structure, negation |

> **실행 흐름:** `pipeline.score("문장")` → morph.analyze → lexical.compute + structure.score + negation.analyze → 가중합산

---

## 1. 최종 점수

```
score = min(1.0, 0.5 × lexical + 0.5 × structure + 0.3 × negation)
```

- `lexical`: 문장에 쓰인 낱말(어휘)의 난이도
- `structure`: 문장 구조의 복잡도 (8개 지표)
- `negation`: 부정 처리 부담 — **보너스** (최대 +0.3). 이중/삼중 부정이 없는 보통 문장은 `0.5×lexical + 0.5×structure`로 1.0까지 도달 가능.

---

## 2. 어휘 점수 (lexical)

### 2.1 기본 원리

각 내용어(명사, 동사, 형용사, 부사 등)를 사전(lexicon)에서 찾아 **0.0~1.0** 사이의 난도 값을 가져온다.
사전에 없는 낱말은 **0.30**의 난도를 부여한다.

### 2.2 낱말 lookup 순서

1. **(lemma, POS)** 정확 일치
2. **base + POS** → (base, "명사") → (base, "어근") 순서로 시도(예: "분석되다" → base "분석" + "명사")
3. **lemma만** 일치
4. **base만** 일치
5. 없으면 **unknown** (난도 0.30)

### 2.3 점수 공식

내용어 개수(`capped`)에 따라 세 가지 가중치 집합을 선택한다.

| 내용어(capped) | `mean_all` | `mean_top_3` | `max` |
|:---:|:---:|:---:|:---:|
| ≤4  | **0.50** | **0.25** | **0.25** |
| 5–7 | **0.35** | **0.40** | **0.25** |
| ≥8  | **0.25** | **0.50** | **0.25** |

짧은 문장일수록 `mean_all`의 비중이 높아 단일 단어가 점수를 크게 좌우하지 않는다.
긴 문장(8+)은 기존과 동일하게 상위 3개의 평균이 좌우한다.

동일 (lemma, POS) 쌍이 반복될 때마다 교차로 유지/제외한다 (1, 3, 5...번째만 capped list에 포함).

### 2.4 예시

문장: **"이 문제는 생각보다 어렵다"**

| 낱말   | 난도 | 비고                  |
| ------ | ---- | --------------------- |
| 문제   | 0.20 |                       |
| 생각   | 0.25 |                       |
| 보다   | 0.22 |                       |
| 어렵다 | 0.00 | 사전에 0.0으로 등록됨 |

- mean_all = (0.20 + 0.25 + 0.22 + 0.00) / 4 = **0.1675**
- mean_top_3 = (0.25 + 0.22 + 0.20) / 3 = **0.2233**
- max = **0.25**
- capped=4 → 가중치 (0.50, 0.25, 0.25)
- lexical = 0.50×0.1675 + 0.25×0.2233 + 0.25×0.25 = **0.2021**

---

## 3. 구조 점수 (structure)

### 3.1 기본 원리

형태소 분석 결과의 품사 태그(Sejong 품사 체계 기준)를 바탕으로
문장 구조의 복잡도를 8개 지표로 측정한다.
각 지표는 일정 임계값을 넘으면 1.0이 된다.

### 3.2 8개 지표

| 지표                      | 측정 대상                                                | 임계값        | 가중치         |
| ------------------------- | -------------------------------------------------------- | ------------- | -------------- |
| **predicate**       | 서술어(VV, VA, VCP, VCN, VX, XSV, XSA) 개수**(-1 보정)** | 8개 → 1.0    | **0.20** |
| **structural_span** | 직전 절 경계~ETM/ETN/EC까지 절 구간 내용어 합계          | 20.0개 → 1.0 | **0.20** |
| **embedding**       | 관형형/명사형 전성어미(ETM, ETN) + 부사형 EC(-게/-도록/-듯이) 개수 | 5개 → 1.0    | **0.15** |
| **length**          | 내용어(명사/동사 등) 개수                                | 23개 → 1.0   | **0.15** |
| **logical**         | 논리부사·강한어미 가중합                                | 4 → 1.0      | **0.10** |
| **modifier**        | 최장 명사 연쇄 길이**(-1 보정)**                         | 5개 → 1.0    | **0.08** |
| **repetition**      | 단어 반복 부담 (반복 횟수×난도×다의성 계수 합계)       | 3.5 → 1.0    | **0.07** |
| **connective**      | 연결어미(EC) 개수                                        | 4개 → 1.0    | **0.05** |

### 3.3 점수 공식

```
structure = 0.20×predicate + 0.15×embedding
          + 0.15×length + 0.20×structural_span
          + 0.10×logical + 0.08×modifier
          + 0.07×repetition + 0.05×connective
```

### 3.4 각 지표 계산 방식

8개 지표 모두 같은 구조로 계산된다:

```
raw = <원시값>
score = min(1.0, raw / <full_score_at>)
```

---

**length** — 내용어 개수 (태그: NNG, NNP, NNB, VV, VA, MAG, XR, NP, NR, XSN, XSV, XSA 등 `is_content=True`인 토큰)

```
raw = max(0, content_count - 5)
score = min(1.0, raw / 18)
```

내용어가 5개 이하 → 0.0, 23개 이상 → 1.0.

---

**predicate** — 서술어 태그 개수

- 태그: VV, VA, VCP, VCN, VX, XSV, XSA
- 조정: 모든 문장에 서술어 최소 1개 필수 → **-1 보정**

```
raw = max(0, predicate_count - 1)
score = min(1.0, raw / 7)
```

서술어가 8개 이상(보정 후 7) → 1.0.

---

**embedding** — 관형형/명사형 전성어미 + 부사형 연결어미 개수

- ETM (`-은`, `-는`, `-을` 등), ETN (`-음`, `-기` 등)
- 부사형 EC: surface/lemma가 `게`, `도록`, `듯이`에 해당하는 연결어미

```
raw = adnominal_count + nominalizer_count + adverbial_ending_count
score = min(1.0, raw / 5)
```

5개 이상 → 1.0.

---

**structural_span** — 절 구간 내용어 합계

ETM/ETN/EC가 나타날 때, 직전 절 경계(EC/EF/SF/SP/SE) 이후부터 해당 marker까지 누적된 내용어 개수들의 **합계**.

```
segment_content_count = 0
spans = []

for token in tokens:
    if token.is_content:
        segment_content_count += 1
    if token.tag in {ETM, ETN, EC} and segment_content_count > 0:
        spans.append(segment_content_count)
    if token.tag in {EC, EF, SF, SP, SE}:
        if not (token.tag == "EC" and 뒤에 VX가 3토큰 이내):
            segment_content_count = 0

raw = sum(spans)
score = min(1.0, raw / 20.0)
```

- EC는 marker이면서 boundary → span 기록 후 segment 초기화
- 단, **aux EC** (EC + 3토큰 이내 VX)는 boundary로 보지 않음. `먹고 싶다`, `유지하고 있다` 식의 보조용언 연결은 절 경계가 아니므로 segment를 유지한다.
- `고(EC)` + `싶(VX)` 또는 `고(EC)` + `있(VX)` 형태가 aux EC에 해당한다.
- ETM/ETN은 boundary가 아니므로 span만 기록, segment 유지
- marker 직전 내용어가 없으면(`segment_content_count == 0`) 해당 marker 제외
- 측정 대상 marker가 없으면 score = 0.0

**full_score_at = 20.0** (모든 절 구간 내용어 합계가 20개 이상이면 1.0)

예시:

- **"경제 성장의 둔화 때문에 유지하고 있다"** → `고(EC)`는 aux EC (뒤에 `있(VX)`) → boundary 아님 → 내용어 9개 단일 구간 → spans=[9], raw=9, **score=0.45**
- **"뛰고 점프하며"** → 두 EC 모두 일반 EC → spans=[1,1], raw=2, **score=0.10**
- **"즉 세계의 근원적 질서인 이념의..."** (변증법 문장) → 6구간 총합 ~23 → **score=1.0**

---

**logical** — 논리 관계 표지(접속부사 + 강한의미 EC) 가중합

- `logical_score` = (논리표지 가중합 + 강한논리연결어미 가중합) / 4

```
ls = min(1.0, (논리표지_가중합 + 강한논리연결어미_가중합) / 4)
```

**논리표지** — 명시적 논리 접속 부사/표현 (가중치 0.5~1.0):

| 표지                 | 가중치  | 표지                     | 가중치  |
| -------------------- | ------- | ------------------------ | ------- |
| 즉, 곧               | 0.8~1.0 | 다시 말해, 말하자면      | 0.8~1.0 |
| 예컨대, 예를 들어    | 0.8     | 따라서, 그러므로         | 1.0     |
| 왜냐하면             | 1.0     | 그러나, 하지만, 그렇지만 | 1.0     |
| 반면, 반대로         | 0.9     | 오히려                   | 0.8     |
| 그럼에도(불구하고)   | 0.9~1.0 | 만약, 만일               | 1.0     |
| 또한, 더불어, 아울러 | 0.7     | 결국, 요컨대, 종합하면   | 0.9~1.0 |
| 뿐만 아니라, 아니라  | 0.5~0.9 |                          |         |

**강한 논리 연결어미** — EC 태그 중 인과/조건/양보를 나타내는 연결어미 (가중치 0.6~1.0):

| 연결어미     | 가중치  | 연결어미               | 가중치  |
| ------------ | ------- | ---------------------- | ------- |
| -(으)므로    | 1.0     | -기에                  | 0.9     |
| -때문에      | 1.0     | -(으)면, -다면, -라면  | 0.8~1.0 |
| -지만, -으나 | 0.9~1.0 | -더라도, -(으)ㄹ지라도 | 1.0     |
| -아/어도     | 0.9     | -려고/으려고           | 0.7     |
| -도록        | 0.8     | -는데/-은데/-ㄴ데      | 0.6     |

---

**modifier** — 최장 명사 연쇄 길이

- 체인 태그: NNG, NNP, NNB, XR (연쇄 시작 가능), XSN (연쇄 이어주기만 가능)
- 조정: 모든 연쇄는 최소 1개 명사 포함 → **-1 보정**
- 예: `경제(NNG) 성장(NNG) 둔화(NNG)` → chain length = 3, 보정 후 2

```
raw = max(0, max_noun_chain - 1)
score = min(1.0, raw / 4)
```

명사 연쇄가 5개 이상(보정 후 4) → 1.0.

---

**repetition** — 단어 반복 처리 부담

같은 표면형을 가진 내용어가 여러 번 등장하면, 다의어/동형어 판별 부담이 추가된다.

```
raw = Σ (count - 1) × difficulty × polysemy
      (반복된 각 단어 표면형에 대해, 제외 lemma 제외)
score = min(1.0, raw / 3.5)
```

**제외 lemma**: `것`, `수`, `때`, `말`, `점`, `등`, `바`, `데` (의존명사/고빈도 형식명사)

**계산 상세**:

- 각 **표면형** 기준으로 등장 횟수 count를 센다
- count > 1이고 lemma가 제외 목록에 없으면 반복 부담 계산
- `difficulty`: 해당 단어의 lexical lookup 난도값
- `polysemy`: Kiwi로 해당 표면형을 분석했을 때 나오는 가능한 품사 태그의 가짓수
- 예: `밥을 먹고 밥을 마신다` → `밥` count=2, difficulty=0.15, polysemy=2 → (2-1)×0.15×2 = 0.30

**derivational**(명사파생접미사 XSN)은 구조 점수 가중합에서는 제외되었지만,
계산 자체는 유지되어 구조 진단 정보로 출력된다.

---

**connective** — 연결어미(EC) 개수

```
cs = min(1.0, EC_개수 / 4)
```

---



## 4. 부정 점수 (negation)

### 4.1 기본 원리

형태소 분석 결과에서 부정 표지(안/못/않/못하/말/없다/아니다)를 찾아
**부정 처리 부담(negation processing burden)** 을 4개 하위 점수로 계산하고
그 중 최댓값을 최종 점수로 사용한다.

### 4.2 4개 하위 점수

| 점수                   | 측정 대상                    | 공식                                                       |
| ---------------------- | ---------------------------- | ---------------------------------------------------------- |
| **local**        | 동일 국소 단위 내 부정 중복  | `min(1.0, max(0, (local_max - 1) / 2))`                  |
| **construction** | 조건절 분할 부정 (조건절 앞 긍정 + 이후 부정) | `1.0` if conditional link + 직전 unit 부정 없음 + 이후 unit 부정 있음 |
| **embedded**     | 인용절/명사절 내 부정        | `min(1.0, embedded_links / 2)`                           |
| **density**      | hard segment 내 부정 밀집    | `0.5 × min(1.0, max(0, seg_neg - 1) / 3)`               |

### 4.3 절 경계 (boundary_kind)

`EC`(연결어미)의 절 경계 판단:

| 경계 종류       | 판단 기준                                    | hard/soft                                |
| --------------- | -------------------------------------------- | ---------------------------------------- |
| `none`        | 일반 EC으로서 경계 없음                      | —                                       |
| `aux`         | EC + 다음 3토큰 내 VX (보조용언 연결)        | —                                       |
| `quote`       | `라고/이라고/다고/ㄴ다고/는다고/냐고/자고` | **soft** (same segment, link 기록) |
| `conditional` | `면/으면/다면/라면`                        | **soft** (same segment, link 기록) |
| `nominal`     | ETM/ETN + NNB/NNG + JX/JKS/JKO/JKC           | **soft** (same segment, link 기록) |
| `coordinate`  | `고/며/으며/거나/든지`                     | **hard** (new segment)             |
| `subordinate` | 나머지 EC (서/니까/므로/지만/으나/는데 등)   | **hard** (new segment)             |
| `punct`       | SP, SF, SE, SS*                              | **hard** (new segment)             |

soft boundary → 같은 hard segment로 유지, `prev_link` 기록
hard boundary → 새 hard segment 시작

**ETM 예외**: `할 수 없다` → ETM(ᆯ) + NNB(수) + VA(없) → JX가 아니므로 `none` (같은 unit 유지).
`간 것은 아니다` → ETM(ᆫ) + NNB(것) + JX(은) → `nominal`.

### 4.4 감지 대상 부정 표지

| 패턴     | 태그  | Lemma 조건               |
| -------- | ----- | ------------------------ |
| `안`   | MAG   | "안"                     |
| `못`   | MAG   | "못"                     |
| `않`   | VX/VV | lemma starts with "않"   |
| `못하` | VX/VV | lemma starts with "못하" |
| `말`   | VX/VV | lemma starts with "말"   |
| `없다` | VA    | lemma stem "없" (단, `없는 한` 관용구 제외) |
| `아니` | VCN   | lemma stem "아니"        |

### 4.5 link 추적 (construction / embedded)

같은 hard segment 내에서 부정 단위 간 link(prev_link)를 추적:

- conditional link와 직전 unit의 부정 여부를 `neg_before_boundary`로 저장
- 조건절 앞 unit에 부정이 없고(`neg_before_boundary=False`) 이후 unit에 부정이 등장 → **construction hit**
- 첫 부정 이후 `quote` 또는 `nominal` link가 있고 두 번째 부정 등장 → **embedded link**

**construction 예시:**

| 문장 | 조건절 앞 부정 | 조건절 이후 부정 | 결과 |
|------|:---:|:---:|:---:|
| `가면 모르지 않는다` | 없음 | 있음 | **1.0** |
| `가지 않으면 모른다` | 있음 | 없음 | 0.0 |
| `안 하면 안 된다` | 있음 | 있음 | 0.0 |

---

## 5. 현재 설정값 한눈에 보기

### 전체 공식

```
score = min(1.0, 0.5 × lexical + 0.5 × structure + 0.3 × negation)
```

| 구성 요소 | 가중치/계수            |
| --------- | ---------------------- |
| lexical   | **0.5**          |
| structure | **0.5**          |
| negation  | **0.3** (보너스) |

### 어휘 점수 내부 가중치

| 내용어(capped) | `mean_all` | `mean_top_3` | `max` |
|:---:|:---:|:---:|:---:|
| ≤4  | **0.50** | **0.25** | **0.25** |
| 5–7 | **0.35** | **0.40** | **0.25** |
| ≥8  | **0.25** | **0.50** | **0.25** |

### 구조 점수 내부 가중치 및 임계값

| 지표            | 가중치 | 1.0 되는 조건                    |
| --------------- | ------ | -------------------------------- |
| predicate       | 0.20   | 서술어 7개+1개(-1 보정)          |
| structural_span | 0.20   | 절 구간 내용어 합계 20.0 이상    |
| embedding       | 0.15   | 관형형/명사형/부사형(게·도록·듯이) 5개 이상 |
| length          | 0.15   | 내용어 23개 이상                 |
| logical         | 0.10   | 논리표지·강한어미 가중합 4 이상 |
| modifier        | 0.08   | 명사 연쇄 4개+1개(-1 보정)       |
| repetition      | 0.07   | 반복 부담 합계 3.5 이상          |
| connective      | 0.05   | EC 개수 4개 이상                 |
