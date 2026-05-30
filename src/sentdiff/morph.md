# morph.py — Kiwi 형태소 분석 래퍼

**위치:** `src/sentdiff/morph.py` (210줄)

## 역할
Kiwi(kiwipiepy)를 래핑해 문장을 `MorphToken` 리스트로 변환. 각 토큰에 표면형, 원형, 세종 태그, 품사, 내용어 여부를 부착한다.

## 주요 클래스/함수

| 이름 | 설명 |
|------|------|
| `@dataclass MorphToken` | surface / lemma / tag / pos / is_content |
| `sejong_tag_to_pos(tag)` | `"NNG"` → `"명사"` |
| `token_to_lemma_candidate(surface, tag)` | lookup용 lemma 후보 생성 (VV/VA에 `"다"` 추가) |
| `is_excluded_lexical_tag(tag)` | 기능 표지(조사/어미/접사/기호) 판단 |
| `is_content_tag(tag)` | 내용어(명/동/형/부/어근/외/한) 여부 |
| `KiwiMorphAnalyzer` | kiwipiepy → 1-best 분석 |

## 분석 결과 예시
```
Input:  "날씨가 좋다"
Output: [MorphToken(surface="날씨", lemma="날씨", tag="NNG", ...),
         MorphToken(surface="가", lemma="가", tag="JKS", ...),
         MorphToken(surface="좋다", lemma="좋다", tag="VA", ...)]
```

## 의존성
- **import:** `normalize.py`, 외부 `kiwipiepy`
- **사용처:** `lexical.py`, `pipeline.py`
