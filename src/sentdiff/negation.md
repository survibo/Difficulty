# 부정 처리 부담 점수 (negation)

## 개요

`NegationAnalyzer`는 문장 내 부정 표지의 **배치와 상호작용**에서 발생하는 처리 부담을
4개 하위 점수로 계량하고, 그 중 최댓값을 `negation_score`로 반환한다.

```
negation_score = max(local, construction, embedded, density)
```

부정 자체의 단순 존재보다 **중복·내포·분할**에 더 높은 점수를 부여하는 것이 핵심 설계이다.

---

## 1. 부정 표지 감지

`_is_negation_token()`은 다음 조건으로 부정 표지를 판별한다:

| 패턴 | 태그 | Lemma 조건 |
|------|------|-----------|
| `안` | MAG | lemma 또는 surface가 "안" |
| `못` | MAG | lemma 또는 surface가 "못" |
| `않` | VX, VV | stem이 "않"으로 시작 |
| `못하` | VX, VV | stem이 "못하"로 시작 |
| `말` | VX, VV | stem이 "말"로 시작 |
| `없다`/`없` | VA | stem == "없" |
| `아니다`/`아니` | VCN | stem == "아니" |

stem은 lemma 또는 surface에서 종성 "다"를 제거한 형태이다.
(`않다 → 않`, `없다 → 없`, `아니다 → 아니`)

MAG는 lemma뿐 아니라 surface("안", "못")도 확인한다.
이는 Kiwi 분석 결과에 따라 lemma가 다르게 등장할 경우를 대비한다.

---

## 2. 절 경계 분류 (_boundary_kind)

각 토큰의 경계 성질을 8가지로 분류한다:

| 경계 종류 | 판단 기준 | hard/soft | 예 |
|-----------|----------|-----------|-----|
| `none` | 일반 내용어, 용언, 조사, 어미 아님 | — | NNG, VV, JX, EF |
| `aux` | EC + (JX/JKO/JKC)* + VX (연속 lookahead) | — | `지 않`, `지는 않` |
| `punct` | SP, SF, SE, SS* | hard | `,`, `.`, `"`, `'` |
| `coordinate` | EC: 고/며/으며/거나/든지 | hard | `-고`, `-며` |
| `subordinate` | 그 외 EC (서/니까/지만/는데 등) | hard | `-서`, `-지만` |
| `quote` | EC: 라고/이라고/다고/냐고/자고 | soft | `-라고`, `-다고` |
| `conditional` | EC: 면/으면/다면/라면 | soft | `-면`, `-으면` |
| `nominal` | ETM/ETN + NNB/NNG + JX/JKS/JKO/JKC | soft | `-ㄴ 것은` |

### aux 판정 알고리즘

EC 토큰에서 시작:
```
j = i + 1
while j < len(tokens):
    if tokens[j].tag == "VX":  → "aux"
    if tokens[j].tag in {JX, JKO, JKC}:  → skip
    break
```

즉, EC 다음에 보조사(JX 등)가 끼어들 수 있지만 그 너머에 VX가 있어야 aux로 인정한다.
용언(VV/VA)이나 다른 어미(EC/EF)가 등장하면 lookahead를 중단한다.

예:
- `지 않` → aux (EC + VX)
- `지는 않` → aux (EC + JX + VX)
- `고 싶` → aux (EC + VX)
- `고 자` → not aux (EC + VV → coordinate)

### ETM/ETN 예외 처리

관형형 전성어미(ETM)와 명사형 전성어미(ETN)는
명사절을 형성할 때만(`-ㄴ 것은`, `-기가`) nominal 경계가 된다.
보조 용언 구성(`-ᆯ 수 없`, `-ᆫ 것 같`)은 경계 없이 현재 unit에 포함된다.

판단: 다음 2토큰이 각각 NNB/NNG + JX/JKS/JKO/JKC인 경우만 nominal.
그 외는 `none`.

```
"간 것은 아니다" → ETM + NNB(것) + JX(은) → nominal
"할 수 없다"     → ETM + NNB(수) + VA(없) → none (같은 unit)
```

---

## 3. 부정 단위 (negation unit)

`_build_negation_units()`는 boundary_kind를 따라 토큰을 분할한다:

```
┌────────────────────────────────────────────────────────┐
│ tokens: [토큰0, 토큰1, ..., 토큰n]                       │
│                                                         │
│ for i, token in tokens:                                  │
│   kind = _boundary_kind(tokens, i)                       │
│                                                         │
│   kind in (none, aux) → 현재 unit에 추가                  │
│   kind in (punct, coordinate, subordinate) →             │
│       flush unit (hard_seg_id++)                         │
│   kind in (quote, conditional, nominal) →                │
│       flush unit (prev_link=kind, hard_seg_id 유지)      │
└────────────────────────────────────────────────────────┘
```

각 unit은 다음 속성을 가진다:
- `tokens`: 해당 unit의 토큰 리스트
- `neg_count`: 부정 표지 개수
- `prev_link`: 직전 soft boundary 종류 (quote/conditional/nominal/None)
- `hard_segment_id`: hard boundary 단위 ID

### hard vs soft segment

| 구분 | 경계 종류 | segment 전환 | 용도 |
|------|----------|-------------|------|
| hard | punct, coordinate, subordinate | `hard_seg_id++` | density 점수 기준 segment |
| soft | quote, conditional, nominal | `prev_link` 기록 | construction / embedded 추적 |

hard segment는 density 계산의 기본 단위가 된다.
같은 hard segment 내에서 soft boundary를 넘어 부정이 이어질 때
construction / embedded 점수가 계산된다.

---

## 4. 4개 하위 점수

### 4.1 local

**측정 대상**: 동일 부정 단위 내 부정 중복

```
local = min(1.0, max(0.0, (local_max - 1) / 2))
```

| local_max | score |
|-----------|-------|
| 0, 1 | 0.0 |
| 2 | 0.5 |
| 3 | 1.0 |

예:
- `안 간다` (local_max=1) → 0.0
- `안 할 수 없다` (local_max=2) → 0.5
- `안+못+없` in same unit (local_max=3) → 1.0

### 4.2 construction

**측정 대상**: 조건절이 양쪽 부정을 분할하는 구조

```
construction = 1.0  if construction_hits > 0, else 0.0
```

**조건**: 같은 hard segment 내에서
1. 첫 부정 등장
2. 그 후 `conditional` soft boundary 발생
3. 같은 segment 내에서 두 번째 부정 등장

→ construction hit 1회

예:
- `안 가면 안 된다` → [안] + conditional(면) + [안] → construction=1.0

### 4.3 embedded

**측정 대상**: 인용절·명사절 내 부정의 내포

```
embedded = min(1.0, embedded_links / 2)
```

**조건**: 같은 hard segment 내에서
1. 첫 부정 등장
2. 그 후 `quote` 또는 `nominal` soft boundary 발생
3. 같은 segment 내에서 두 번째 부정 등장

→ embedded link 1회

| embedded_links | score |
|----------------|-------|
| 0 | 0.0 |
| 1 | 0.5 |
| 2+ | 1.0 |

예:
- `아니라고 말할 수 없다` → [아니] + quote(라고) + [말...없] → embedded=0.5
- `아니라고 생각하지 않는다` → [아니] + quote(라고) + [않] → embedded=0.5
- `간 것은 아니라고 말할 수 없다` → [간...아니] + nominal + quote + [없] → embedded=1.0

### 4.4 density

**측정 대상**: hard segment 내 부정 밀집도

```
density = 0.5 × min(1.0, max(0, max_seg_neg - 1) / 3)
```

| max segment 내 부정 | score |
|-------------------|-------|
| 0, 1 | 0.0 |
| 2 | 0.17 |
| 3 | 0.33 |
| 4 | 0.50 |

density는 **segment 단위**로 계산된다.
여러 unit이 같은 hard segment에 속하면 unit들의 neg_count가 합산된다.
0.5를 cap으로 하여 다른 점수(local=1.0)보다 우선순위가 낮다.

---

## 5. link 추적 (segment-aware)

construction / embedded 점수 계산을 위한 link 추적 로직:

```
current_seg = None
last_neg_seen = False
links = set()

for unit in units:
    if unit.hard_segment_id != current_seg:
        # 새 hard segment → reset
        current_seg = unit.hard_segment_id
        last_neg_seen = False
        links.clear()

    if unit.prev_link in {quote, nominal, conditional}:
        links.add(unit.prev_link)

    if unit.neg_count > 0:
        if last_neg_seen:
            # 같은 segment에 두 번째 부정 등장
            if "conditional" in links:
                construction_hits += 1
            if quote 또는 nominal in links:
                embedded_links += count
        last_neg_seen = True
        links.clear()
```

hard segment가 바뀌면 모든 상태가 초기화된다.
이는 서로 다른 절의 부정을 병렬(score=0)로 처리하기 위함이다.

---

## 6. 종합 예시

| 문장 | total | local_max | embedded | construction | density | final |
|------|-------|-----------|----------|-------------|---------|-------|
| 그는 학교에 간다 | 0 | 0 | 0 | 0 | 0.00 | 0.0 |
| 그는 학교에 가지 않는다 | 1 | 1 | 0 | 0 | 0.00 | 0.0 |
| 그는 학교에 가지 않을 수 없다 | 2 | 2 | 0 | 0 | 0.17 | 0.5 |
| 안 가면 안 된다 | 2 | 1 | 0 | 1 | 0.17 | 1.0 |
| 나는 그가 오지 않았다고 말하지 않았다 | 2 | 1 | 1 | 0 | 0.17 | 0.5 |
| 이 문제를 그리 풀지 않는 것은 좋은 선택이 아니라고 말할 수 없다 | 3 | 1 | 2 | 0 | 0.33 | 1.0 |
| 안 먹고 자지 않았다 | 2 | 1 | 0 | 0 | 0.00 | 0.0 |

---

## 7. pipeline 통합

`SentenceScorer`에서 5:5:2 비율로 통합:

```
score = (5.0 × lexical + 5.0 × structure + 2.0 × negation) / 12.0
```

부정 점수의 출력 키:
- `negation_score_0_1`: round(negation_score, 4)
- `negation_score_10`: round(negation_score × 10, 2)
- `negation_detail`: {negation_count_total, negation_count_local_max, local_negation_score, construction_negation_score, embedded_negation_score, negation_density_score, negation_score}
- `negation_weight`: 2.0
