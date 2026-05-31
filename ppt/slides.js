const pptxgen = require("pptxgenjs");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "한국어 문장 난이도 자동 측정";

// 컬러 팔레트
const C = {
  navy:    "1B2A4A",
  blue:    "2563EB",
  sky:     "DBEAFE",
  white:   "FFFFFF",
  offwhite:"F8FAFC",
  gray:    "64748B",
  lgray:   "E2E8F0",
  black:   "0F172A",
  accent:  "F59E0B",
  green:   "059669",
  red:     "DC2626",
  teal:    "0D9488",
};

const makeShadow = () => ({ type: "outer", blur: 8, offset: 3, angle: 135, color: "000000", opacity: 0.10 });

// ── 슬라이드 1: 표지 ───────────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  // 왼쪽 강조 바
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.25, h: 5.625, fill: { color: C.blue }, line: { color: C.blue } });

  // 상단 작은 레이블
  s.addText("국어 문법 / 언어 정보 처리", {
    x: 0.55, y: 1.1, w: 8, h: 0.35,
    fontSize: 12, color: C.accent, bold: true, fontFace: "Calibri",
    margin: 0,
  });

  s.addText("한국어 문장 난이도\n자동 측정 시스템", {
    x: 0.55, y: 1.6, w: 8.5, h: 1.9,
    fontSize: 40, bold: true, color: C.white, fontFace: "Calibri",
    margin: 0,
  });

  s.addText("형태소 분석 기반 어휘·구조·부정 3축 모델", {
    x: 0.55, y: 3.55, w: 8, h: 0.45,
    fontSize: 16, color: "A0AEC0", fontFace: "Calibri", margin: 0,
  });

  // 우측 스코어 예시 카드
  s.addShape(pres.shapes.RECTANGLE, {
    x: 7.8, y: 1.3, w: 1.9, h: 2.8,
    fill: { color: C.blue, transparency: 75 },
    line: { color: C.blue, width: 1 },
    shadow: makeShadow(),
  });
  s.addText("score", { x: 7.8, y: 1.5, w: 1.9, h: 0.35, fontSize: 11, color: "93C5FD", align: "center", fontFace: "Calibri", margin: 0 });
  s.addText("6.85", { x: 7.8, y: 1.85, w: 1.9, h: 0.9, fontSize: 44, bold: true, color: C.white, align: "center", fontFace: "Calibri", margin: 0 });
  s.addText("/10", { x: 7.8, y: 2.7, w: 1.9, h: 0.3, fontSize: 13, color: "93C5FD", align: "center", fontFace: "Calibri", margin: 0 });
  s.addText("매우 어려움", { x: 7.8, y: 3.1, w: 1.9, h: 0.35, fontSize: 11, color: C.accent, align: "center", bold: true, fontFace: "Calibri", margin: 0 });
}

// ── 슬라이드 2: 문제 정의 ─────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("왜 만들었나?", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const cards = [
    { icon: "?", title: "기존 방식의 한계", body: "글자 수·음절 수 기반 공식\n(예: Flesch-Kincaid 한국어판)\n→ 어휘 난이도를 무시", color: C.red },
    { icon: "!", title: "국어 교육 현장의 필요", body: "교재 지문, 시험 문항의\n난이도를 객관적으로\n수치화하고 싶다", color: C.blue },
    { icon: "✓", title: "이 시스템의 목표", body: "어휘 + 문법 구조 + 부정\n세 축을 동시에 고려한\n0~10점 자동 채점", color: C.green },
  ];

  cards.forEach((c, i) => {
    const x = 0.4 + i * 3.1;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.1, w: 2.9, h: 3.8,
      fill: { color: C.white },
      line: { color: C.lgray, width: 1 },
      shadow: makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.1, w: 2.9, h: 0.1, fill: { color: c.color }, line: { color: c.color } });
    s.addText(c.icon, { x, y: 1.3, w: 2.9, h: 0.6, fontSize: 28, align: "center", color: c.color, fontFace: "Calibri", margin: 0 });
    s.addText(c.title, { x: x+0.15, y: 2.0, w: 2.6, h: 0.5, fontSize: 14, bold: true, color: C.black, fontFace: "Calibri", margin: 0 });
    s.addText(c.body, { x: x+0.15, y: 2.55, w: 2.6, h: 2.1, fontSize: 12, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 3: 전체 구조 ─────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("시스템 구조 한눈에 보기", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  // 최종 공식 박스
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.4, y: 1.05, w: 9.2, h: 0.85,
    fill: { color: C.navy }, line: { color: C.navy }, shadow: makeShadow(),
  });
  s.addText("score  =  min(1.0,   0.5 × lexical   +   0.5 × structure   +   0.3 × negation)   × 10", {
    x: 0.4, y: 1.05, w: 9.2, h: 0.85,
    fontSize: 15, bold: true, color: C.white, align: "center", fontFace: "Consolas", margin: 0,
  });

  // 3개 박스
  const cols = [
    { label: "LEXICAL", sub: "어휘 난이도", desc: "내용어를 4만 단어 사전에서\n조회해 0~1 난도 부여\nmean_all · mean_top3 · max\n가중 평균", color: C.blue, x: 0.4 },
    { label: "STRUCTURE", sub: "문법 구조 복잡도", desc: "형태소 품사 태그 기반\n8개 지표 가중합\n서술어·내포절·논리어미\n절 구간 스팬 등", color: C.teal, x: 3.7 },
    { label: "NEGATION", sub: "부정 처리 부담", desc: "이중·삼중 부정만 카운팅\n단순 부정은 0점\n4개 하위 점수 중 최댓값\n(보너스 +0.3)", color: C.accent, x: 7.0 },
  ];

  cols.forEach(c => {
    s.addShape(pres.shapes.RECTANGLE, {
      x: c.x, y: 2.05, w: 2.85, h: 3.3,
      fill: { color: C.white }, line: { color: C.lgray, width: 1 }, shadow: makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x: c.x, y: 2.05, w: 2.85, h: 0.55, fill: { color: c.color }, line: { color: c.color } });
    s.addText(c.label, { x: c.x, y: 2.08, w: 2.85, h: 0.3, fontSize: 13, bold: true, color: C.white, align: "center", fontFace: "Calibri", margin: 0 });
    s.addText(c.sub, { x: c.x, y: 2.38, w: 2.85, h: 0.22, fontSize: 10, color: C.white, align: "center", fontFace: "Calibri", margin: 0 });
    s.addText(c.desc, { x: c.x+0.15, y: 2.7, w: 2.55, h: 2.5, fontSize: 12, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 4: 어휘 점수 ─────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.blue }, line: { color: C.blue } });
  s.addText("어휘 점수 (Lexical)", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  // 공식
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 1.0, w: 9.2, h: 0.65, fill: { color: C.sky }, line: { color: C.blue, width: 1 } });
  s.addText("lexical  =  w₁ × mean_all  +  w₂ × mean_top3  +  w₃ × max", {
    x: 0.4, y: 1.0, w: 9.2, h: 0.65, fontSize: 14, bold: true, color: C.blue, align: "center", fontFace: "Consolas", margin: 0,
  });

  // 왼쪽: 가중치 테이블
  const tableData = [
    [
      { text: "내용어 수", options: { bold: true, color: C.white, fill: { color: C.navy } } },
      { text: "mean_all", options: { bold: true, color: C.white, fill: { color: C.navy } } },
      { text: "mean_top3", options: { bold: true, color: C.white, fill: { color: C.navy } } },
      { text: "max", options: { bold: true, color: C.white, fill: { color: C.navy } } },
    ],
    ["≤ 4 (짧은 문장)", "0.50", "0.25", "0.25"],
    ["5~7 (중간 문장)", "0.35", "0.40", "0.25"],
    ["≥ 8 (긴 문장)", "0.25", "0.50", "0.25"],
  ];
  s.addTable(tableData, {
    x: 0.4, y: 1.8, w: 5.5, h: 2.0,
    fontSize: 12, fontFace: "Calibri",
    border: { pt: 1, color: C.lgray },
    colW: [1.8, 1.2, 1.2, 1.0],
  });

  // 오른쪽: 왜 이렇게?
  s.addShape(pres.shapes.RECTANGLE, { x: 6.1, y: 1.8, w: 3.5, h: 2.0, fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow() });
  s.addText("왜 문장 길이에 따라 다른 가중치?", { x: 6.25, y: 1.85, w: 3.2, h: 0.4, fontSize: 12, bold: true, color: C.blue, fontFace: "Calibri", margin: 0 });
  s.addText([
    { text: "짧은 문장", options: { bold: true, breakLine: false } },
    { text: "은 단어 1개가 점수 전체를\n지배하므로 mean_all 비중↑\n\n", options: {} },
    { text: "긴 문장", options: { bold: true, breakLine: false } },
    { text: "은 어려운 단어 여러 개의\n조합이 중요하므로 mean_top3 비중↑", options: {} },
  ], { x: 6.25, y: 2.3, w: 3.2, h: 1.4, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });

  // 사전 설명
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 4.0, w: 9.2, h: 1.35, fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow() });
  s.addText("사전 lookup 방식", { x: 0.6, y: 4.05, w: 3, h: 0.35, fontSize: 13, bold: true, color: C.black, fontFace: "Calibri", margin: 0 });
  s.addText([
    { text: "① (lemma, POS) 정확 일치  →  ② base + POS  →  ③ lemma만  →  ④ base만  →  ⑤ unknown (난도 0.30 기본값 부여)", options: {} },
    { text: "\n사전 규모 40,000 단어 · 각 단어 0.0~1.0 난도값 보유", options: { color: C.gray } },
  ], { x: 0.6, y: 4.45, w: 8.8, h: 0.8, fontSize: 11, color: C.black, fontFace: "Calibri", margin: 0 });
}

// ── 슬라이드 5: 구조 점수 ─────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.teal }, line: { color: C.teal } });
  s.addText("구조 점수 (Structure)", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const metrics = [
    { name: "predicate", w: "0.20", desc: "서술어 수 (−1 보정)", why: "절이 많을수록 복잡" },
    { name: "embedding", w: "0.20", desc: "관형형/명사형 전성어미", why: "내포절 = 인지 부담" },
    { name: "length",    w: "0.15", desc: "내용어 개수", why: "문장 정보량" },
    { name: "structural_span", w: "0.15", desc: "절 구간 내용어 합계", why: "한 절 안의 밀도" },
    { name: "logical",   w: "0.10", desc: "논리 접속부사·어미 가중합", why: "인과·조건·양보 관계" },
    { name: "modifier",  w: "0.08", desc: "최장 명사 연쇄 길이", why: "명사구 수식 중첩" },
    { name: "repetition", w:"0.07", desc: "반복 단어 부담", why: "다의어 판별 비용" },
    { name: "connective",w:"0.05", desc: "연결어미(EC) 개수", why: "단순 절 연결량" },
  ];

  const colW = [1.9, 0.6, 2.4, 2.4];
  const header = [
    { text: "지표", options: { bold: true, color: C.white, fill: { color: C.teal } } },
    { text: "가중치", options: { bold: true, color: C.white, fill: { color: C.teal } } },
    { text: "측정 대상", options: { bold: true, color: C.white, fill: { color: C.teal } } },
    { text: "선택 이유", options: { bold: true, color: C.white, fill: { color: C.teal } } },
  ];
  const rows = [header, ...metrics.map(m => [m.name, m.w, m.desc, m.why])];
  s.addTable(rows, {
    x: 0.4, y: 1.0, w: 9.2, h: 4.35,
    fontSize: 11, fontFace: "Calibri",
    border: { pt: 1, color: C.lgray },
    colW,
  });
}

// ── 슬라이드 6: 구조 — 핵심 지표 설명 ───────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.teal }, line: { color: C.teal } });
  s.addText("구조 점수 — 핵심 지표 상세", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const boxes = [
    {
      title: "embedding (가중치 0.20)",
      body: "ETM(-은/-는/-을)·ETN(-음/-기) 개수\n4개 이상 → score 1.0\n\n예: \"그가 어렸을 때 살던 마을에서 자랐던 친구가\n      활동하는 예술가가 되었다는 소식을 들었다\"\n→ ETM 4개 → embedding 1.0",
      color: C.teal,
    },
    {
      title: "structural_span (가중치 0.15)",
      body: "ETM/ETN/EC 직전 절 구간의 내용어 합계\n합계 20 이상 → score 1.0\n보조용언 연결(고 있다/고 싶다)은 경계로 보지 않음\n\n절이 길수록 독해 작업 메모리 부담 증가를 반영",
      color: C.blue,
    },
    {
      title: "logical (가중치 0.10)",
      body: "논리 접속부사(따라서·왜냐하면·그러나 등)\n+ 강한 연결어미(-(으)므로·-지만·-더라도)\n\n단순 나열(-고 0.3)과 논리적 종속(-므로 1.0)을\n가중치로 구분 → connective와 차별화",
      color: C.accent,
    },
  ];

  boxes.forEach((b, i) => {
    const x = 0.3 + i * 3.25;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.05, w: 3.1, h: 4.3,
      fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.05, w: 3.1, h: 0.5, fill: { color: b.color }, line: { color: b.color } });
    s.addText(b.title, { x: x+0.1, y: 1.08, w: 2.9, h: 0.44, fontSize: 12, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(b.body, { x: x+0.12, y: 1.65, w: 2.86, h: 3.6, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 7: 부정 점수 ─────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.accent }, line: { color: C.accent } });
  s.addText("부정 점수 (Negation)", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  // 설계 원칙
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 1.0, w: 9.2, h: 0.6, fill: { color: "FEF3C7" }, line: { color: C.accent } });
  s.addText("단순 부정(먹지 않았다)은 0점 — 이중/삼중 부정부터 처리 부담을 계산", {
    x: 0.4, y: 1.0, w: 9.2, h: 0.6, fontSize: 13, bold: true, color: "92400E", align: "center", fontFace: "Calibri", margin: 0,
  });

  // 4개 하위 점수
  const scores = [
    { name: "local", formula: "min(1, (max_local−1)/2)", desc: "같은 단위 안에\n부정 중복" },
    { name: "construction", formula: "1.0 if hit", desc: "조건절 앞 긍정\n+ 뒤 부정" },
    { name: "embedded", formula: "min(1, links/2)", desc: "인용절/명사절\n안의 부정" },
    { name: "density", formula: "0.5×min(1,(n−1)/3)", desc: "한 절 안에\n부정 밀집" },
  ];

  scores.forEach((sc, i) => {
    const x = 0.4 + i * 2.3;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.75, w: 2.15, h: 2.5,
      fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow(),
    });
    s.addText(sc.name, { x, y: 1.78, w: 2.15, h: 0.38, fontSize: 13, bold: true, color: C.accent, align: "center", fontFace: "Calibri", margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 2.16, w: 2.15, h: 0.02, fill: { color: C.lgray }, line: { color: C.lgray } });
    s.addText(sc.formula, { x: x+0.1, y: 2.22, w: 1.95, h: 0.55, fontSize: 10, color: C.blue, fontFace: "Consolas", margin: 0 });
    s.addText(sc.desc, { x: x+0.1, y: 2.85, w: 1.95, h: 1.3, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });
  });

  s.addText("최종 negation_score = max(local, construction, embedded, density)", {
    x: 0.4, y: 4.35, w: 9.2, h: 0.45, fontSize: 12, bold: true, color: C.black, align: "center", fontFace: "Consolas",
    fill: { color: C.lgray }, margin: 0,
  });

  // construction 예시
  s.addShape(pres.shapes.RECTANGLE, { x: 0.4, y: 4.85, w: 9.2, h: 0.65, fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow() });
  s.addText([
    { text: "construction 판정 예: ", options: { bold: true } },
    { text: "\"가면 모르지 않는다\"", options: { color: C.green, bold: true } },
    { text: " → 조건절 앞 긍정 + 뒤 부정 → hit   /   ", options: {} },
    { text: "\"안 하면 안 된다\"", options: { color: C.red, bold: true } },
    { text: " → 앞도 부정 → miss", options: {} },
  ], { x: 0.55, y: 4.88, w: 9.0, h: 0.58, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });
}

// ── 슬라이드 8: 검증 — 전체 분포 ────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("검증 결과 — 난이도 분포", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const examples = [
    { sent: "비가 온다.", score: 0.06, level: "매우 쉬움", color: "22C55E" },
    { sent: "버스를 타고 학교에 갔다.", score: 0.43, level: "쉬움", color: "86EFAC" },
    { sent: "회의가 길어지면서 참석자들의 피로가 쌓였다.", score: 2.03, level: "보통", color: C.accent },
    { sent: "인구 고령화로 인한 생산가능인구 감소는...", score: 5.23, level: "어려움", color: "F97316" },
    { sent: "국제사법재판소의 관할권은 분쟁 당사국 모두의...", score: 5.97, level: "어려움", color: "F97316" },
    { sent: "피케티의 r>g 명제는 자본수익률이...", score: 6.85, level: "매우 어려움", color: C.red },
    { sent: "이 사건에서 피고가 고의로 허위 사실을...", score: 8.95, level: "최고 난이도", color: "7C3AED" },
  ];

  examples.forEach((e, i) => {
    const y = 1.05 + i * 0.62;
    const barW = (e.score / 10) * 6.5;
    s.addShape(pres.shapes.RECTANGLE, { x: 3.1, y: y + 0.12, w: 6.5, h: 0.35, fill: { color: C.lgray }, line: { color: C.lgray } });
    s.addShape(pres.shapes.RECTANGLE, { x: 3.1, y: y + 0.12, w: Math.max(barW, 0.05), h: 0.35, fill: { color: e.color }, line: { color: e.color } });
    s.addText(e.sent, { x: 0.3, y, w: 2.75, h: 0.58, fontSize: 9.5, color: C.black, fontFace: "Calibri", margin: 0 });
    s.addText(e.score.toFixed(2), { x: 9.65, y: y + 0.05, w: 0.6, h: 0.45, fontSize: 13, bold: true, color: e.color, fontFace: "Calibri", margin: 0, align: "right" });
    s.addText(e.level, { x: 3.15, y: y + 0.14, w: barW - 0.1, h: 0.31, fontSize: 9, color: C.white, bold: true, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 9: 검증 — 함정 케이스 ──────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("검증 — 함정 케이스", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const cases = [
    {
      type: "짧지만 어려운 어휘",
      sent: "그의 언사는 매우 오만방자했다.",
      score: "3.74",
      note: "content_words 5개뿐이지만\n'오만방자' 하나가 lexical을 끌어올림\n→ 짧아도 어려운 어휘는 반영됨",
      ok: true,
    },
    {
      type: "길지만 쉬운 단어 나열",
      sent: "나는 어제 학교에 가서 친구를 만나고...",
      score: "2.07",
      note: "EC가 많아 structure 3.83이지만\nlexical 0.30으로 희석됨\n→ 나열과 종속절을 구분하는 connective/logical 설계",
      ok: true,
    },
    {
      type: "이중 부정 (진짜)",
      sent: "그가 오지 않은 것은 아니다.",
      score: "2.25",
      note: "negation_score 5.0 → 최종 점수에\n+0.3×0.5=0.15 보너스 반영\n→ 쉬운 어휘인데도 중간 이상",
      ok: true,
    },
    {
      type: "오탐 수정 사례",
      sent: "규정상 예외가 인정되지 않는 한 처벌을 면할 수 없다.",
      score: "5.41",
      note: "'없는 한' 관용구를 부정으로 잘못 인식하는\n오탐을 예외 처리로 수정함\n→ construction 조건 재정의 후 정상화",
      ok: true,
    },
  ];

  cases.forEach((c, i) => {
    const x = 0.3 + (i % 2) * 4.9;
    const y = 1.05 + Math.floor(i / 2) * 2.3;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.6, h: 2.1,
      fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x, y, w: 0.12, h: 2.1, fill: { color: c.ok ? C.green : C.red }, line: { color: c.ok ? C.green : C.red } });
    s.addText(c.type, { x: x+0.2, y: y+0.08, w: 3.5, h: 0.3, fontSize: 11, bold: true, color: C.black, fontFace: "Calibri", margin: 0 });
    s.addText(`"${c.sent}"`, { x: x+0.2, y: y+0.4, w: 4.2, h: 0.35, fontSize: 10, color: C.blue, italic: true, fontFace: "Calibri", margin: 0 });
    s.addText(`score: ${c.score}`, { x: x+0.2, y: y+0.75, w: 1.5, h: 0.28, fontSize: 11, bold: true, color: C.teal, fontFace: "Calibri", margin: 0 });
    s.addText(c.note, { x: x+0.2, y: y+1.05, w: 4.2, h: 0.95, fontSize: 10, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 10: 개선 과정 ───────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("설계 반복 — 주요 개선 이력", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const history = [
    { v: "v1", title: "기초 3축 설계", desc: "lexical × 0.5 + structure × 0.5 + negation × 0.2\n단순 부정 포함, EC 순수 카운팅", issue: "단순 부정 과평가\n나열 문장 과평가" },
    { v: "v2", title: "negation 이중부정 조건화", desc: "단순 부정 → 0점\n이중/삼중 부정부터 카운팅\nnegation 계수 0.2 → 0.3", issue: "'없는 한' 오탐\nconstruction 조건 미흡" },
    { v: "v3", title: "construction 조건 강화", desc: "neg_before_boundary 필드 추가\n조건절 앞 부정 있으면 construction 제외\n'없는 한' 관용구 예외 처리", issue: "짧은 문장 lexical\n과평가 잔존" },
    { v: "v4", title: "lexical 가중치 길이 의존화", desc: "content_words ≤4: mean_all 0.50\ncontent_words 5~7: mean_all 0.35\ncontent_words ≥8: mean_all 0.25", issue: "미세 조정 필요\n(max 가중치 유지)" },
  ];

  history.forEach((h, i) => {
    const x = 0.3 + i * 2.35;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: 1.05, w: 2.2, h: 4.3,
      fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow(),
    });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 1.05, w: 2.2, h: 0.55, fill: { color: C.navy }, line: { color: C.navy } });
    s.addText(h.v, { x, y: 1.08, w: 0.7, h: 0.44, fontSize: 16, bold: true, color: C.accent, align: "center", fontFace: "Calibri", margin: 0 });
    s.addText(h.title, { x: x+0.7, y: 1.1, w: 1.45, h: 0.42, fontSize: 10, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });
    s.addText(h.desc, { x: x+0.12, y: 1.7, w: 1.96, h: 1.9, fontSize: 10, color: C.gray, fontFace: "Calibri", margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x, y: 3.65, w: 2.2, h: 0.02, fill: { color: C.lgray }, line: { color: C.lgray } });
    s.addText("남은 과제", { x: x+0.12, y: 3.72, w: 1.96, h: 0.25, fontSize: 9, bold: true, color: C.red, fontFace: "Calibri", margin: 0 });
    s.addText(h.issue, { x: x+0.12, y: 3.98, w: 1.96, h: 1.3, fontSize: 9.5, color: C.red, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 11: 한계 및 향후 과제 ──────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.offwhite };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.9, fill: { color: C.navy }, line: { color: C.navy } });
  s.addText("한계 및 향후 과제", { x: 0.4, y: 0.1, w: 9, h: 0.7, fontSize: 24, bold: true, color: C.white, fontFace: "Calibri", margin: 0 });

  const items = [
    {
      no: "01", title: "사전 커버리지",
      body: "'시원하다' 같은 기초 어휘가\nunknown 처리되는 사례 잔존\n→ 40,000 어휘 사전 지속 보완 필요",
      color: C.blue,
    },
    {
      no: "02", title: "와/과 명사구 병렬",
      body: "\"소득 불평등 심화와 사회적 이동성 저하\"처럼\n명사구가 와/과로 이어지는 구조를\nstructure가 충분히 반영하지 못함",
      color: C.teal,
    },
    {
      no: "03", title: "담화 수준 난이도",
      body: "문장 단위 측정이므로\n텍스트 전체의 응집성·논리 구조는\n현재 모델 범위 밖",
      color: C.accent,
    },
    {
      no: "04", title: "인간 평가 비교 검증",
      body: "교사/학습자 대상 주관적 난이도\n평가 데이터와의 상관 분석이\n아직 수행되지 않음",
      color: C.red,
    },
  ];

  items.forEach((it, i) => {
    const x = 0.3 + (i % 2) * 4.9;
    const y = 1.1 + Math.floor(i / 2) * 2.25;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y, w: 4.6, h: 2.05,
      fill: { color: C.white }, line: { color: C.lgray }, shadow: makeShadow(),
    });
    s.addText(it.no, { x: x+0.15, y: y+0.1, w: 0.55, h: 0.55, fontSize: 22, bold: true, color: it.color, fontFace: "Calibri", margin: 0 });
    s.addText(it.title, { x: x+0.72, y: y+0.15, w: 3.7, h: 0.45, fontSize: 14, bold: true, color: C.black, fontFace: "Calibri", margin: 0 });
    s.addShape(pres.shapes.RECTANGLE, { x: x+0.15, y: y+0.68, w: 4.3, h: 0.02, fill: { color: C.lgray }, line: { color: C.lgray } });
    s.addText(it.body, { x: x+0.15, y: y+0.78, w: 4.3, h: 1.15, fontSize: 11, color: C.gray, fontFace: "Calibri", margin: 0 });
  });
}

// ── 슬라이드 12: 마무리 ───────────────────────────────────────────
{
  const s = pres.addSlide();
  s.background = { color: C.navy };

  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 0.25, h: 5.625, fill: { color: C.accent }, line: { color: C.accent } });

  s.addText("핵심 요약", { x: 0.55, y: 0.7, w: 8, h: 0.45, fontSize: 14, color: C.accent, bold: true, fontFace: "Calibri", margin: 0 });

  const pts = [
    "형태소 분석 기반으로 어휘·구조·부정 세 축을 독립 계산 후 가중합산",
    "lexical은 사전 40,000어 + 문장 길이별 동적 가중치로 단어 지배 방지",
    "structure는 단순 나열과 종속절을 구분하는 8개 지표로 구성",
    "negation은 이중부정 이상만 계산, construction 오탐을 조건 재정의로 수정",
  ];

  pts.forEach((p, i) => {
    s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 1.3 + i * 0.72, w: 0.35, h: 0.35, fill: { color: C.blue }, line: { color: C.blue } });
    s.addText(`${i + 1}`, { x: 0.55, y: 1.3 + i * 0.72, w: 0.35, h: 0.35, fontSize: 13, bold: true, color: C.white, align: "center", fontFace: "Calibri", margin: 0 });
    s.addText(p, { x: 1.05, y: 1.3 + i * 0.72, w: 8.5, h: 0.35, fontSize: 13, color: "E2E8F0", fontFace: "Calibri", margin: 0 });
  });

  s.addShape(pres.shapes.RECTANGLE, { x: 0.55, y: 4.2, w: 9.1, h: 0.02, fill: { color: "334155" }, line: { color: "334155" } });
  s.addText("한국어 문장 난이도 자동 측정 시스템  ·  sentdiff", {
    x: 0.55, y: 4.3, w: 9.1, h: 0.4, fontSize: 12, color: "64748B", fontFace: "Calibri", margin: 0,
  });
}

pres.writeFile({ fileName: __dirname + "/sentdiff_presentation.pptx" })
  .then(() => console.log("done"))
  .catch(e => console.error(e));