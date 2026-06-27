# -*- coding: utf-8 -*-
"""Build the ATANOR business-plan PDF (Korean, Malgun Gothic)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Flowable,
)

pdfmetrics.registerFont(TTFont("Malgun", r"C:\Windows\Fonts\malgun.ttf"))
pdfmetrics.registerFont(TTFont("MalgunBd", r"C:\Windows\Fonts\malgunbd.ttf"))

INK = colors.HexColor("#14181f")
BLUE = colors.HexColor("#3a63d8")
BLUE_D = colors.HexColor("#22327a")
GREY = colors.HexColor("#5a6478")
LIGHT = colors.HexColor("#eef2fb")
LINE = colors.HexColor("#d4dcf0")

def S(name, size, leading, font="Malgun", color=INK, space_before=0, space_after=6, align=TA_LEFT, left=0):
    return ParagraphStyle(name, fontName=font, fontSize=size, leading=leading, textColor=color,
                          spaceBefore=space_before, spaceAfter=space_after, alignment=align, leftIndent=left)

st_title   = S("title", 30, 36, "MalgunBd", INK, align=TA_CENTER, space_after=4)
st_sub     = S("sub", 13, 19, "Malgun", GREY, align=TA_CENTER, space_after=2)
st_h1      = S("h1", 16, 21, "MalgunBd", BLUE_D, space_before=16, space_after=7)
st_h2      = S("h2", 12.5, 17, "MalgunBd", INK, space_before=9, space_after=3)
st_body    = S("body", 10.3, 16.2, "Malgun", INK, space_after=5)
st_bullet  = S("bul", 10.3, 15.6, "Malgun", INK, space_after=3, left=12)
st_small   = S("small", 8.6, 12.5, "Malgun", GREY, space_after=2)
st_kicker  = S("kicker", 10.5, 14, "MalgunBd", BLUE, align=TA_CENTER, space_after=10)
st_cell    = S("cell", 9.2, 12.6, "Malgun", INK)
st_cellb   = S("cellb", 9.2, 12.6, "MalgunBd", INK)
st_cellw   = S("cellw", 9.2, 12.6, "MalgunBd", colors.white)

def h1(t): return Paragraph(t, st_h1)
def h2(t): return Paragraph(t, st_h2)
def p(t): return Paragraph(t, st_body)
def b(t): return Paragraph("• " + t, st_bullet)
def sp(h=6): return Spacer(1, h)

class Rule(Flowable):
    def __init__(self, w, color=BLUE, thick=2.4):
        super().__init__(); self.w=w; self.color=color; self.thick=thick
    def wrap(self, *a): return (self.w, self.thick)
    def draw(self):
        self.canv.setStrokeColor(self.color); self.canv.setLineWidth(self.thick)
        self.canv.line(0, 0, self.w, 0)

def metric_table(rows, header):
    data = [[Paragraph(header[0], st_cellw), Paragraph(header[1], st_cellw), Paragraph(header[2], st_cellw)]]
    for r in rows:
        data.append([Paragraph(r[0], st_cellb), Paragraph(r[1], st_cell), Paragraph(r[2], st_cell)])
    t = Table(data, colWidths=[46*mm, 60*mm, 60*mm])
    style = [
        ("BACKGROUND", (0,0), (-1,0), BLUE_D),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
        ("GRID", (0,0), (-1,-1), 0.5, LINE),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]
    t.setStyle(TableStyle(style)); return t

def simple_table(rows, widths, header_bg=BLUE_D):
    data = []
    for i, r in enumerate(rows):
        style_h = st_cellw if i == 0 else None
        data.append([Paragraph(c, st_cellw if i==0 else (st_cellb if j==0 else st_cell)) for j, c in enumerate(r)])
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), header_bg),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, LIGHT]),
        ("GRID", (0,0), (-1,-1), 0.5, LINE),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
        ("TOPPADDING", (0,0), (-1,-1), 5), ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ])); return t

story = []

# ---------- COVER ----------
story += [sp(120)]
story += [Paragraph("ATANOR", st_title)]
story += [Paragraph("그래프 네이티브 · 로컬 우선 · 환각하지 않는 AI", st_sub)]
story += [sp(10)]
story += [Paragraph("사업계획서 — Primer 배치 지원", S("c2", 14, 18, "MalgunBd", BLUE_D, align=TA_CENTER))]
story += [sp(24)]
story += [Paragraph("“외부 거대언어모델 없이, GPU 없이, 출처를 증명하며 답하는 AI”", S("tag", 12, 18, "Malgun", GREY, align=TA_CENTER))]
story += [sp(60)]
story += [Paragraph("작성일: 2026년 6월 · 본 문서의 성능 수치는 자체 실측값입니다 (부록 출처 참조)", st_small)]
story += [Paragraph("팀/재무/투자요청 항목의 [   ] 는 창업자가 채울 자리입니다.", st_small)]
story += [PageBreak()]

# ---------- 1. EXEC SUMMARY ----------
story += [Rule(170*mm), sp(3), h1("1. 한 줄 요약 (Executive Summary)")]
story += [p("<b>ATANOR는 외부 거대언어모델(LLM)을 쓰지 않고, 명시적 지식 그래프와 실시간 검색으로 답하는 로컬 우선(local-first) AI입니다.</b> "
            "답은 그래프에서 파생되거나 공개 웹(위키백과 등)에서 <b>그대로 인용</b>되며, 모든 답에 출처와 추론 증명서가 붙습니다. "
            "근거가 없으면 지어내지 않고 “모르겠다”라고 합니다.")]
story += [sp(4)]
story += [h2("자체 실측 핵심 지표")]
story += [metric_table([
    ("환각률(거짓 단정)", "~0% (존재하지 않는 개체 함정 0/N 날조)", "프런티어 LLM: ~1.5–6% (검색 시), 미검색 시 더 높음"),
    ("출처/인용", "100% (모든 웹 답변에 실제 URL)", "기본 0%, RAG여도 <100%"),
    ("답변 시 GPU", "0 (모델 추론 없음)", "수백 W의 GPU"),
    ("질문당 에너지", "~0.001 Wh", "~0.3–3 Wh"),
    ("모델 가중치 / VRAM", "0 GB / 0 VRAM", "2.4–40 GB 가중치 / 4–48 GB VRAM"),
    ("설치 용량", "핵심 의존성 ~11 MB + 그래프", "torch/CUDA ~4–5 GB + 가중치"),
    ("프라이버시", "로컬 우선 (사적 메모리 비업로드)", "클라우드 전송"),
], ("지표", "ATANOR (실측)", "프런티어 LLM (공개 추정)"))]
story += [sp(5), p("→ ATANOR는 <b>신뢰성(환각 0·완전 출처), 비용/에너지(GPU 0), 프라이버시(로컬), 설치 경량성</b>에서 구조적 우위를 가집니다. "
                   "대가는 <b>지식 커버리지와 일반 추론 깊이</b>가 프런티어 LLM보다 낮다는 점이며, 이는 설계상의 정직한 트레이드오프입니다.")]
story += [PageBreak()]

# ---------- 2. PROBLEM ----------
story += [Rule(170*mm), sp(3), h1("2. 문제 (Problem)")]
story += [p("거대언어모델(LLM)은 강력하지만, 신뢰가 핵심인 현장에서는 네 가지 구조적 한계로 도입이 막힙니다.")]
story += [b("<b>환각</b> — 그럴듯한 거짓을 자신 있게 만들어냅니다. 사실 검증이 중요한 업무에서 치명적입니다.")]
story += [b("<b>비용·에너지</b> — 질문마다 GPU 추론(질문당 ~0.3–3 Wh, 수백 W). 대규모/엣지 배포에 부담입니다.")]
story += [b("<b>프라이버시</b> — 프롬프트가 클라우드로 전송됩니다. 데이터 외부 유출이 금지된 산업에는 부적합합니다.")]
story += [b("<b>감사 불가능</b> — “왜 그렇게 답했는가”를 증명할 출처·근거 사슬이 없습니다.")]
story += [sp(5), p("결과적으로 <b>금융·의료·법률·공공·국방</b> 등 규제·고신뢰 영역과 <b>온디바이스/엣지·프라이버시 민감</b> 환경에서 "
                   "LLM 도입의 결정적 장벽이 됩니다. 이 시장은 ‘똑똑함’보다 ‘틀리지 않음·증명 가능함·안전함’을 더 원합니다.")]
story += [sp(6)]

# ---------- 3. SOLUTION / PRODUCT ----------
story += [Rule(170*mm), sp(3), h1("3. 솔루션 & 제품 (Solution & Product)")]
story += [p("ATANOR는 기억·출처·검색·복구·공개지식 교환을 하나의 원격 모델 호출 안에 숨기지 않고, <b>전부 명시적인 그래프 시스템</b>으로 둡니다.")]
story += [h2("두뇌 구조")]
story += [b("<b>베이스 브레인</b> — 사용자 데이터 없이도 기본 개념을 설명하는 로컬 시드 지식 그래프")]
story += [b("<b>클라우드 브레인</b> — 공개 웹에서 검증된 개념을 누적 학습하는 공개 그래프 (개인정보 비업로드)")]
story += [b("<b>로컬 브레인</b> — 대화에서 얻은 사용자 정보를 기기 안에만 쌓는 사적 메모리")]
story += [b("<b>서피스 브레인</b> — 그래프의 근거를 자연스러운 문장으로 실현(realization)")]
story += [b("<b>CGSR 라우팅·그라운딩</b> — 질문을 적절한 두뇌/검색으로 분기, 근거에 묶어 답 생성")]
story += [h2("핵심 기능")]
story += [b("<b>추출형 웹 그라운딩</b> — 근거가 없으면 공개 웹에서 검색해 문장을 인용하고 출처를 표시, 새 개념은 그래프에 누적")]
story += [b("<b>결정론적 다단계 추론</b> — “A와 B 중 누가 먼저 태어났어?”(검색→검색→비교), “프랑스의 수도의 인구는?”(연쇄 2-hop) 등을 LLM 없이")]
story += [b("<b>자기 모델</b> — 자신이 무엇이고 어떻게 작동하는지 일관되게 설명")]
story += [b("<b>추론 증명서</b> — 모든 답이 근거·도출 방식·보증(외부 LLM 미사용 등)을 함께 출력 → 감사 가능")]
story += [b("<b>살아있는 UI</b> — 파티클 ‘구슬’이 답하고, 출처 문서를 지니 효과로 띄우는 등 에이전트가 화면을 자율 제어")]
story += [b("<b>자율 누적 학습 + AGORA</b> — 밤사이 공개 웹을 정직하게 학습하고, 에이전트 커뮤니티(AGORA)와 상호작용")]
story += [PageBreak()]

# ---------- 4. DIFFERENTIATION ----------
story += [Rule(170*mm), sp(3), h1("4. 핵심 차별점 — 측정된 사실 (Why we are different)")]
story += [p("아래는 마케팅 수사가 아니라 <b>실제 측정값</b>입니다 (자체 벤치마크 하니스 + 하드웨어 계측, 부록 참조).")]
story += [sp(3), h2("정직성 & 신뢰")]
story += [b("환각률 <b>~0%</b>: 존재하지 않는 가짜 개체로 함정을 깔아도 전부 ‘모른다’고 abstain (날조 0건)")]
story += [b("인용 정밀도 <b>100%</b>: 모든 웹 답변이 답을 추출한 바로 그 출처 URL을 보유")]
story += [b("완전한 출처추적: 모든 답에 추론 증명서 — LLM은 ‘왜’를 증명하지 못함")]
story += [sp(3), h2("효율 & 배포")]
story += [b("답변 시 <b>서버 GPU 0</b> · 질문당 <b>~0.001 Wh</b> (프런티어 LLM 대비 ~100–1000배 적은 에너지)")]
story += [b("<b>모델 가중치 0 · VRAM 0 · 핵심 의존성 ~11 MB</b> → <b>GPU 없는 기기</b>에서도 구동")]
story += [b("<b>로컬 우선</b> 프라이버시 — 사적 메모리는 기기 밖으로 나가지 않음")]
story += [sp(4), p("<font color='#5a6478' size=9>정직한 한계: 그래프+검색 구조이므로 지식 커버리지가 프런티어 LLM보다 좁고, "
                   "일반 다단계 추론 깊이가 아직 얕습니다(현재 비교·연쇄 추론 단계). 캐시되지 않은 사실은 인터넷이 필요합니다.</font>")]
story += [sp(6)]

# ---------- 5. MARKET ----------
story += [Rule(170*mm), sp(3), h1("5. 시장 (Market)")]
story += [h2("타깃 고객")]
story += [b("<b>규제·고신뢰 산업</b>: 금융(컴플라이언스·리서치), 의료, 법률, 공공·국방 — 환각/유출이 허용되지 않는 영역")]
story += [b("<b>온디바이스 / 엣지 AI</b>: GPU 없이 도는 경량 AI가 필요한 단말·임베디드·오프그리드")]
story += [b("<b>프라이버시 우선 기업</b>: 데이터를 외부 LLM에 보낼 수 없는 조직 (온프레미스)")]
story += [b("<b>저전력·저자원 환경</b>: 에너지/하드웨어 비용이 결정적인 시장")]
story += [sp(3), h2("시장 규모 (방향성)")]
story += [p("전 세계 엔터프라이즈 AI 시장은 빠르게 성장 중이며, 그 안에서 <b>프라이빗/온프레미스·신뢰가능 AI</b>와 <b>온디바이스 AI</b> "
            "수요가 별도 축으로 커지고 있습니다. ATANOR는 ‘가장 똑똑한 모델’ 경쟁이 아니라 <b>‘틀리면 안 되고, 밖으로 나가면 안 되고, "
            "싸게 돌아야 하는’ 세그먼트</b>를 정조준합니다. <font color='#5a6478' size=9>[구체 TAM/SAM/SOM 수치 및 출처 — 창업자 보강]</font>")]
story += [PageBreak()]

# ---------- 6. BUSINESS MODEL ----------
story += [Rule(170*mm), sp(3), h1("6. 비즈니스 모델 (Business Model)")]
story += [simple_table([
    ["수익 모델", "대상", "근거/강점"],
    ["온프레미스 라이선스", "규제산업 엔터프라이즈", "데이터 외부 유출 불가 요구를 정조준; 로컬 구동이 곧 제품 가치"],
    ["per-seat / 사용량 SaaS", "팀·중소기업", "GPU 비용 0 → 낮은 운영비로 가격 경쟁력"],
    ["임베디드/엣지 라이선스", "단말·하드웨어 제조사", "0 VRAM·~11MB로 기기 내장 가능"],
    ["도메인 그래프 팩", "수직 산업(의료/법률 등)", "Graph Hub로 도메인 지식 큐레이션 판매"],
    ["컨트리뷰터 클라우드(AGORA)", "장기·네트워크 효과", "다수 사용자 PC에 거주하는 에이전트 공용 학습"],
], [40*mm, 48*mm, 78*mm])]
story += [sp(5), p("핵심: <b>추론에 GPU가 들지 않아 단위 운영비(COGS)가 극히 낮습니다.</b> 이는 가격·마진·엣지 배포 모두에서 구조적 이점입니다.")]
story += [sp(6)]

# ---------- 7. MOAT ----------
story += [Rule(170*mm), sp(3), h1("7. 경쟁 우위 / 해자 (Competition & Moat)")]
story += [simple_table([
    ["경쟁군", "그들의 강점", "ATANOR의 우위"],
    ["프런티어 LLM\n(OpenAI·Anthropic·Google)", "지식·일반 추론 폭", "환각 0·완전 출처·감사·프라이버시·에너지/비용"],
    ["로컬 LLM (Llama·ollama)", "오프라인·소유권", "환각(소형도 발생)·수GB 가중치·VRAM 필요 → 우리는 0"],
    ["RAG/검색 벤더", "검색+생성 결합", "외부 LLM 의존 제거 → 비용·프라이버시·인용 정밀도"],
], [44*mm, 50*mm, 72*mm])]
story += [sp(5), p("해자는 단일 기능이 아니라 <b>‘정직성 + 경량성 + 프라이버시’의 결합</b>입니다. LLM 진영이 이를 따라오려면 "
                   "근본 아키텍처(생성형 가중치 모델)를 바꿔야 합니다. 더불어 <b>도메인 그래프 자산</b>과 <b>AGORA 네트워크 효과</b>가 "
                   "시간이 지날수록 누적 방어력을 만듭니다.")]
story += [sp(6)]

# ---------- 8. ROADMAP ----------
story += [Rule(170*mm), sp(3), h1("8. 로드맵 & 비전 (Roadmap)")]
story += [h2("단기 (0–6개월)")]
story += [b("작동 프로토타입 → 클로즈드 베타; 규제산업 1–2곳 PoC")]
story += [b("공개 벤치마크 100문항 + 에너지/footprint 백서 공개 (신뢰 마케팅)")]
story += [h2("중기 (6–18개월)")]
story += [b("추론 코어 심화 — PHFE(위상 홀로그래픽 폴딩: 파동간섭 + 결정론적 폴딩)로 일반 다단계 추론 강화")]
story += [b("도메인 그래프 팩(의료·법률·금융) 상용화; 온프레미스 배포 패키지")]
story += [b("분산 컨트리뷰터 클라우드(AGORA) v1 — 다수 노드 공용 학습")]
story += [h2("장기 비전")]
story += [p("<b>‘프로그램 안에 사는 정직한 생명체’</b> — 모든 기기에서 GPU 없이 돌고, 환각하지 않으며, 모든 답을 증명하는 "
            "<b>신뢰 가능한 AI 인프라</b>. LLM이 ‘가장 똑똑한 답’을 겨룰 때, ATANOR는 ‘가장 믿을 수 있고 가장 가벼운 답’의 표준이 됩니다.")]
story += [PageBreak()]

# ---------- 9. TRACTION ----------
story += [Rule(170*mm), sp(3), h1("9. 현재 상태 / 트랙션 (Traction)")]
story += [b("작동하는 풀스택 프로토타입: 대시보드 UI + FastAPI 엔진 + 5개 두뇌 + 자율 학습 루프")]
story += [b("결정론적 다단계 추론(비교·연쇄) 구현 및 단위테스트 통과")]
story += [b("자체 측정 벤치마크 하니스(67문항) — 환각 0%·인용 100% 재현")]
story += [b("에너지·footprint 하드웨어 실측 백서 (GPU 0, ~0.001 Wh/질문, 가중치 0)")]
story += [sp(4), p("<font color='#5a6478' size=9>단계: 프로토타입/시드. 매출·계약·파일럿 등 정량 트랙션은 창업자가 보강 — [   ]</font>")]
story += [sp(6)]

# ---------- 10. TEAM ----------
story += [Rule(170*mm), sp(3), h1("10. 팀 (Team)")]
story += [p("<font color='#5a6478'>[창업자/공동창업자 이름 · 역할 · 핵심 이력 · 왜 우리가 이걸 해낼 수 있는가(Founder-Market Fit)를 채워주세요.]</font>")]
story += [b("[대표 — 성명 / 배경 / 강점]")]
story += [b("[기술 — 성명 / 배경 / 강점]")]
story += [b("[자문·초기 멤버 — 있다면]")]
story += [sp(6)]

# ---------- 11. ASK ----------
story += [Rule(170*mm), sp(3), h1("11. 투자 요청 & 자금 사용 (The Ask)")]
story += [p("<font color='#5a6478'>[라운드/금액/밸류 및 자금 사용처를 채워주세요. 아래는 참고용 골격입니다.]</font>")]
story += [simple_table([
    ["사용처", "비중(예시)", "목적"],
    ["제품·엔지니어링", "[ % ]", "추론 코어·온프레미스 패키지·도메인 그래프"],
    ["GTM·파일럿", "[ % ]", "규제산업 PoC·초기 고객 확보"],
    ["인프라·운영", "[ % ]", "벤치마크 공개·보안/컴플라이언스 인증"],
], [50*mm, 30*mm, 86*mm])]
story += [sp(5), p("목표(예시): [ ]개월 내 [ ]개 유료 파일럿 / 베타 사용자 [ ]명 / 벤치마크 공개로 신뢰 포지셔닝 확립.")]
story += [sp(8), Rule(170*mm, GREY, 0.8), sp(3)]

# ---------- APPENDIX ----------
story += [h1("부록 — 측정 출처 (Appendix)")]
story += [p("본 문서의 모든 성능 수치는 자체 코드/계측에서 재현 가능합니다:")]
story += [b("벤치마크 하니스: packages/answer_quality/factual_qa_benchmark.py (67문항, 환각·인용·정답·지연)")]
story += [b("벤치마크 비교: docs/ATANOR_BENCHMARK_COMPARISON.md · docs/ATANOR_VS_LLMS_NUMBERS.md")]
story += [b("에너지: docs/ATANOR_ENERGY_EFFICIENCY.md (RTX 5080 계측)")]
story += [b("설치 용량: docs/ATANOR_FOOTPRINT.md (가중치 0·VRAM 0·~11MB)")]
story += [b("추론 코어: comparison_reasoner.py · chained_reasoner.py")]
story += [sp(6), p("<font color='#5a6478' size=8.5>※ 프런티어/로컬 LLM 수치는 공개 모델카드·리더보드(MMLU·GSM8K·Vectara HHEM·ALCE·TruthfulQA) "
                   "추정값으로, 서로 다른 테스트셋이므로 방향성 비교입니다. 외부 모델을 동일 셋으로 직접 구동하지 않았습니다(설계상 외부 LLM 미사용).</font>")]

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Malgun", 8); canvas.setFillColor(GREY)
    canvas.drawString(20*mm, 12*mm, "ATANOR · 사업계획서 (Confidential)")
    canvas.drawRightString(190*mm, 12*mm, "%d" % doc.page)
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.5); canvas.line(20*mm, 15*mm, 190*mm, 15*mm)
    canvas.restoreState()

out = r"C:\0.ASKIM ALL-VIN\ATANOR-live-selfhood-scheduler\ATANOR_사업계획서.pdf"
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=20*mm,
                        title="ATANOR 사업계획서", author="ATANOR")
doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
print("WROTE", out)
