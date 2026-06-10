# negation.py — 부정 처리 부담 점수

**위치:** `src/sentdiff/negation.py`

## 역할

MorphToken 리스트의 부정 표지를 분석하여 부정 처리 부담(negation processing burden)을
4개 하위 점수로 계산하고 그 중 최댓값을 최종 negation_score로 반환한다.
절 경계는 structure의 논리 표현 분석과 같은 `PatternMatcher`가 만든 `PatternMatch` span을
입력으로 사용한다.

## flow 단계

**6단계** — morph에 의존.

## 부정 토큰 판정

Kiwi의 `-I`, `-R` 등 접미 표지는 원본 토큰 태그에는 보존하지만 부정 토큰과
절 경계를 판정할 때는 제거한다. 예를 들어 `VA-I`/`VA-R`의 `없`도 `VA`의
`없`과 동일하게 부정으로 처리하고, `EC-I`/`EC-R`도 `EC` 경계로 처리한다.

연결어미 표면형은 `normalize_morph_form()`으로 종성 자모를 표준화한다. 따라서 Kiwi가
`ᆫ다고`, `ᆫ다면`, `ᆫ데`로 반환한 형태도 각각 `ㄴ다고`, `ㄴ다면`, `ㄴ데` 규칙과
동일하게 인용·조건·종속 경계로 분류한다.

`_is_negation_token` 기준:

| 태그 | 형태 | 예 |
|------|------|-----|
| MAG | 안, 못 | `안(부사)` |
| VX, VV | 않/아니하/못하/말로 시작하는 어간 | `않다`, `아니하다`, `못하다`, `말다` |
| VA | 없 | `없다` (단, `없는 한` 관용구 제외) |
| VCN | 아니 | `아니다` |

> **"없는 한" 관용구 예외:** VA `없` 바로 뒤가 ETM + NNB("한")이면 부정으로 카운트하지 않는다.
> 예: `없는 한`의 `없`은 부정 아님, `없지 않은 한`의 `없`은 부정 맞음.

## 절 경계 종류

NegationAnalyzer는 부정 단위를 나누기 위해 아래 경계/비경계 종류를 인식한다:

| 경계 종류 | 조건 | 영향 |
|-----------|------|------|
| `none` | 해당 없음 | segment 유지 |
| `aux` | EC 바로 뒤, 또는 JX/JKO/JKC 뒤에 VX (보조용언) | segment 유지 |
| `punct` | SP, SF, SE, SS* | hard break |
| `coordinate` | 고/며/거나 등 대등 연결 | hard break |
| `subordinate` | 종속 연결 | hard break |
| `conditional` | 면/으면/다면/라면 | link tracking |
| `quote` | 라고/다고/냐고/자고 | link tracking |
| `nominal` | ETM/ETN + NNB/NNG + JX/JKS/JKO/JKC | link tracking |

- **hard break** → `hard_segment_id` 증가, link 정보 초기화
- **link tracking** (conditional/quote/nominal) → `prev_link`에 저장, segment는 초기화되지만 hard_segment_id 유지
- `기/ETN + 에/JKB`와 `때문/NNB + 에/JKB`는 두 토큰 span 전체를 하나의
  `subordinate` 경계로 분류한다.
- pipeline이 한 번 계산한 `boundary_matches`를 전달하므로 negation과 디버그 출력이
  동일한 경계 판정을 공유한다.

`PatternMatch`에는 `kind`, `label`, 원문 `start`/`end`, 토큰 `token_start`/`token_end`가
들어간다. 분석 결과의 `boundary_matches`에는 `boundary_` 접두사를 제거한 kind가 출력된다.

## 4개 하위 점수

### 1. local — 동일 국소 단위 내 부정 중복

```
local_score = 0.0 if local_max <= 1 else min(1.0, (local_max - 1) ** 2 / 2.5)
```

같은 negation unit 내에 부정이 여러 개 있으면 중첩 부정으로 간주.
- `안 먹지 않았다` → 한 unit에 부정 2개 → 0.4
- `안 먹지 아니할 수 없었다` → 한 unit에 부정 3개 → 1.0

### 2. construction — 조건절 분할 부정

- **조건:** 조건절(면/으면/다면/라면) 앞 unit과 이후 unit에 모두 부정이 있음
- **동작:** 조건절 soft boundary 진입 시 `neg_before_boundary=True`이면 `pending_construction` 플래그 설정.
  이후 같은 hard segment 내에서 부정이 발견되면 1회 hit.

```
construction_score = 0.4  (조건절 앞 부정 있음 + 조건절 이후 부정 있음)
                     0.0  (그 외)
```

- `가면 모르지 않는다` → 조건절 앞(가) 긍정, 이후(모르지 않는다) 부정 → **0.0**
- `가지 않으면 안 된다` → 조건절 앞(가지 않)과 이후(안 된다) 모두 부정 → **0.4**
- `가지 않으면 모른다` → 조건절 앞 부정 있음 → **0.0**

> 조건절 이후에만 부정이 있는 경우는 일반적인 단일 부정이므로 construction에 해당하지 않는다.

### 3. embedded — 인용절/명사절 내 부정

```
embedded_score = min(1.0, embedded_links / 2)
```

인용절(라고/다고 등) 또는 명사절(ETM/ETN + NNB)을 건너 부정이 나타난 횟수.
2회 이상이면 1.0.

### 4. density — hard segment 수준 부정 밀도

```
segment_density = min(1.0, max(0, max_seg_neg - 1) / 3)
density_score = 0.5 × segment_density
```

동일 hard segment 내 최대 부정 개수를 기반으로 한 밀도 측정.
`max_seg_neg`가 4 이상이면 segment_density = 1.0, density_score = 0.5.

## 최종 점수

```
negation_score = max(local_score, construction_score, embedded_score, density_score)
```

4개 중 최댓값 채택. 범위 0~1.

## 출력 구조

```python
{
    "negation_count_total": int,         # 전체 부정 토큰 수
    "negation_count_local_max": int,     # 단위 내 최대 부정 수
    "negation_embedded_links": int,      # 내포 링크 건넌 횟수
    "negation_construction_hits": int,   # 조건절 분할 부정 적중 수
    "local_negation_score": float,       # local 점수
    "construction_negation_score": float, # construction 점수
    "embedded_negation_score": float,    # embedded 점수
    "negation_density_score": float,     # density 점수
    "negation_score": float,             # 최종 점수 (최댓값)
    "boundary_matches": [                # 공통 matcher가 분류한 절 경계 span
        {"kind", "label", "start", "end", "token_start", "token_end"}
    ],
}
```

## 의존성
- **import:** `morph.base_sejong_tag`, `patterns.PatternMatcher`
- **사용처:** `pipeline.py`가 `NegationAnalyzer` 호출
