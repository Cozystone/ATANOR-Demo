# -*- coding: utf-8 -*-
"""Build the ATANOR / BELIFE business-plan PDF — Primer format, black & white."""
import math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable,
)

pdfmetrics.registerFont(TTFont("M", r"C:\Windows\Fonts\malgun.ttf"))
pdfmetrics.registerFont(TTFont("MB", r"C:\Windows\Fonts\malgunbd.ttf"))

BLACK = colors.HexColor("#000000")
INK = colors.HexColor("#111111")
GREY = colors.HexColor("#666666")
FAINT = colors.HexColor("#e8e8e8")
ZEBRA = colors.HexColor("#f4f4f4")

def S(n, sz, ld, f="M", c=INK, sb=0, sa=6, al=TA_LEFT, li=0):
    return ParagraphStyle(n, fontName=f, fontSize=sz, leading=ld, textColor=c,
                          spaceBefore=sb, spaceAfter=sa, alignment=al, leftIndent=li)

st_h1   = S("h1", 15, 20, "MB", BLACK, sb=14, sa=7)
st_h2   = S("h2", 11.5, 16, "MB", INK, sb=8, sa=3)
st_body = S("body", 10.2, 16, "M", INK, sa=5)
st_bul  = S("bul", 10.2, 15.4, "M", INK, sa=3, li=11)
st_small= S("sm", 8.6, 12.4, "M", GREY, sa=2)
st_cell = S("cell", 9.1, 12.6, "M", INK)
st_cellb= S("cellb", 9.1, 12.6, "MB", INK)
st_cellw= S("cellw", 9.1, 12.6, "MB", colors.white)
st_field= S("field", 9.6, 13.5, "MB", GREY, sa=1)

def h1(t): return Paragraph(t, st_h1)
def h2(t): return Paragraph(t, st_h2)
def p(t): return Paragraph(t, st_body)
def b(t): return Paragraph("·&nbsp;" + t, st_bul)
def sp(h=6): return Spacer(1, h)

class Rule(Flowable):
    def __init__(self, w, c=BLACK, t=1.6): super().__init__(); self.w=w; self.c=c; self.t=t
    def wrap(self,*a): return (self.w, self.t)
    def draw(self):
        self.canv.setStrokeColor(self.c); self.canv.setLineWidth(self.t); self.canv.line(0,0,self.w,0)

class Field(Flowable):
    """Primer-form style label + value block."""
    def __init__(self, label, value, w=170*mm):
        super().__init__(); self.label=label; self.value=value; self.w=w
        self.pl=Paragraph(value, S("fv",10,14.5,"M",INK))
        _, self.vh = self.pl.wrap(w-2*mm, 1000)
    def wrap(self,*a): return (self.w, self.vh+15)
    def draw(self):
        c=self.canv
        c.setFont("MB",8.4); c.setFillColor(GREY); c.drawString(0, self.vh+5, self.label)
        self.pl.drawOn(c, 0, 0)
        c.setStrokeColor(FAINT); c.setLineWidth(0.6); c.line(0,-3,self.w,-3)

def laurel(c, cx, cy, R, col=colors.white):
    """Draw an open laurel wreath (open at top) — two symmetric leafed branches."""
    c.setFillColor(col); c.setStrokeColor(col)
    for side in (-1, 1):
        # branch arc from bottom (~ -95deg) up to top (~ 75deg)
        a0, a1, n = -95, 78, 9
        for i in range(n):
            t = i/(n-1)
            ang = math.radians(a0 + (a1-a0)*t) * 1  # base angle on the circle
            # mirror by side: x mirrored
            bx = cx + side * R*math.cos(ang)
            by = cy + R*math.sin(ang)
            # leaf: small ellipse pointing outward-tangent
            c.saveState(); c.translate(bx, by)
            lean = math.degrees(ang) + 90*side  # tangent-ish
            c.rotate(lean)
            lw = R*0.30; lh = R*0.12
            c.ellipse(-lw*0.15, -lh/2, lw*0.85, lh/2, fill=1, stroke=0)
            c.restoreState()
        # stem line
    # crossing stems at bottom
    c.setLineWidth(max(1.0, R*0.03))
    c.line(cx, cy-R*0.96, cx - R*0.34, cy - R*0.62)
    c.line(cx, cy-R*0.96, cx + R*0.34, cy - R*0.62)

def metric_table(rows, header, widths=(44*mm,60*mm,62*mm)):
    data=[[Paragraph(h, st_cellw) for h in header]]
    for r in rows: data.append([Paragraph(r[0],st_cellb)]+[Paragraph(x,st_cell) for x in r[1:]])
    t=Table(data, colWidths=list(widths))
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),BLACK),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,ZEBRA]),
        ("GRID",(0,0),(-1,-1),0.5,FAINT),("BOX",(0,0),(-1,-1),0.8,INK),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
    ])); return t

story=[]
# blank flowables on cover (cover drawn in onFirstPage)
story += [Spacer(1, 250*mm), PageBreak()]

# 1. 회사 및 제품 소개
story += [Rule(170*mm), sp(3), h1("1. 회사 및 제품 소개")]
story += [Field("회사이름", "ATANOR (아타노르) — <font color='#666666'>미설립, 가칭</font>")]
story += [Field("회사형태", "사업자 없음 (연구·개발 단계)")]
story += [Field("제품/서비스명", "ATANOR (엔진) · BELIFE (그 위의 개인 인텔리전스 서비스)")]
story += [Field("한 줄 소개", "온톨로지 기반 <b>탈중앙화 뉴로모픽 하이브리드 AI, ATANOR</b> — 환각하지 않고, GPU 없이 돌며, 모든 답의 출처를 증명한다.")]
story += [Field("서비스 URL", "https://github.com/Cozystone/ATANOR")]
story += [Field("CEO 1분 영상", "https://  <font color='#666666'>[프라이머2026-ATANOR-김안석 제목으로 업로드 후 입력]</font>")]
story += [sp(8)]

# 2. 창업자 / 팀
story += [Rule(170*mm), sp(3), h1("2. 창업자 (Founder)")]
story += [p("<b>김안석 (Kim Anseok) — 대표</b>")]
story += [b("<b>넥스트챌린지스쿨</b> 재학 — 서울시교육청 인가 <b>국내 첫 창업 특화 대안 고등학교</b>. "
            "AI·글로벌·창업 융합 커리큘럼, 글로벌 대학 교수·빅테크·스타트업 대표가 가르치며 Google·Intel·Thales 등과 협력하는 ‘테슬라 국제학교’.")]
story += [b("<b>시나브로</b> (문학인을 위한 SNS 플랫폼) — <b>학생창업유망팀 U300+ 도약트랙 최종선발</b>")]
story += [b("<b>WETHUS</b> (학생 창업 프로젝트 플랫폼) — <b>‘모두의 창업’ 1차 심사 통과</b>")]
story += [b("현재 <b>ATANOR + BELIFE</b> 개발 — 온톨로지 기반 탈중앙화 AI와 개인 인텔리전스 서비스")]
story += [sp(3), p("<b>왜 우리가 해낼 수 있는가 (Founder–Market Fit):</b> 시나브로(문학 커뮤니티)→WETHUS(창업 커뮤니티)→BELIFE까지, "
                   "저는 일관되게 <b>‘사람의 생각을 구조화하고 사람을 더 잘 연결하는 플랫폼’</b>을 만들어 왔고, 매번 외부 인정(U300+, 모두의창업)으로 검증받았습니다. "
                   "ATANOR는 그 플랫폼들이 진짜로 필요로 하던 <b>‘개인이 소유하는, 믿을 수 있는 AI’</b>를 직접 만드는 시도입니다.")]
story += [sp(8)]

# 3. 시장의 문제점과 기회
story += [Rule(170*mm), sp(3), h1("3. 시장의 문제점과 기회")]
story += [p("AI 시장은 빠르게 성장하지만, 대부분의 서비스는 <b>중앙집중형 클라우드 LLM</b>에 의존합니다. 강력하지만 네 가지 구조적 한계를 가집니다.")]
story += [b("<b>비용·에너지</b> — 질문마다 GPU 추론(~0.3–3 Wh, 수백 W). 개인·소팀이 자기 AI를 장기 운영하기엔 부담.")]
story += [b("<b>데이터 주권</b> — 더 좋은 답을 받으려면 개인·기업의 지식을 외부 클라우드로 보내야 함.")]
story += [b("<b>장기 기억·개인화의 한계</b> — 사람처럼 ‘자라나는’ AI 구조가 부재.")]
story += [b("<b>환각·출처 불투명</b> — 답이 어떤 근거에서 나왔는지 증명하기 어려움 (의료·법률·교육·연구에 치명적).")]
story += [sp(3), p("<b>기회:</b> ATANOR는 이 문제를 ‘더 큰 모델’이 아니라 <b>‘다른 구조’</b>로 해결합니다. 개인 기억은 로컬에 보존하고, "
                   "공용 지식은 검증 가능한 그래프로 관리하며, 후보 지식은 안전하게 학습한 뒤 검증을 거쳐 승격합니다. "
                   "AI가 문장을 ‘생성’만 하는 게 아니라 지식을 <b>축적·발견·검증하며 로컬에서 성장</b>합니다.")]
story += [h2("시장 규모 (출처 기반)")]
story += [metric_table([
    ("엣지/온디바이스 AI", "$11.8B (2025) → $56.8B (2030)", "CAGR 36.9% — ATANOR 엔진의 시장 (GPU 없이 도는 AI)"),
    ("AI 컴패니언/개인 비서", "→ $242–318B (2030–33)", "CAGR 17–31% — BELIFE(개인 인텔리전스)의 시장"),
], ("시장", "규모", "비고 / 출처: BCC·Grandview·Precedence Research"))]
story += [sp(3), p("ATANOR는 ‘가장 똑똑한 모델’ 경쟁이 아니라 <b>‘틀리면 안 되고, 밖으로 나가면 안 되고, 싸게 돌아야 하는’</b> 세그먼트를 정조준합니다.")]
story += [h2("초기 고객")]
story += [b("자기 문서·코드·연구를 장기 기억으로 쌓고 싶은 <b>개발자·연구자</b>")]
story += [b("내부 지식을 외부 서버에 노출하지 않고 AI로 쓰고 싶은 <b>소규모 팀·스타트업</b>")]
story += [b("로컬-first·개인 지식주권·탈중앙 AI에 관심 있는 <b>고급 사용자·얼리어답터</b>")]
story += [PageBreak()]

# 4. 제품 상세
story += [Rule(170*mm), sp(3), h1("4. 제품/서비스 상세")]
story += [h2("ATANOR — 로컬-first AI 운영체제 (엔진)")]
story += [p("지식·기억·추론·표현·학습·검증을 모델 파라미터에 압축하지 않고 <b>분리된 모듈</b>로 구성합니다.")]
story += [b("<b>Local Brain</b> — 개인 기억·문서·맥락·선호를 기기 안에만 보존하는 사적 계층 (자동 비전송 원칙)")]
story += [b("<b>Cloud Brain</b> — 공개 지식 그래프. 후보(candidate)와 검증(verified)을 <b>분리</b>하고, 출처·중복·모순·품질 검사를 거쳐야 승격")]
story += [b("<b>Surface Brain · CGSR · RHFC</b> — 그래프 지식을 자연어로 표현하는 표면화·생성·공명기억 계층")]
story += [b("<b>Autonomy Kernel · Midnight Congress</b> — World/Self 모델의 결핍 신호로 ‘무엇이 부족한지’ 제안 (proposal-only, proof 단계)")]
story += [b("<b>Tabularis Privacy Shield · Atlas Trust Router · Atlas Congress</b> — 프라이버시·신뢰 라우팅·P2P 지식 토론장의 초기 구조")]
story += [sp(2), p("핵심: ATANOR는 챗봇이 아니라, 개인 컴퓨터 안에서 기억을 키우고 공개 지식을 검증·승격하며, 장차 여러 로컬 AI가 안전하게 연결되는 <b>개인 AI 운영체제</b>입니다.")]
story += [sp(3), h2("BELIFE — 개인 인텔리전스 서비스 (ATANOR 위의 첫 제품)")]
story += [p("ATANOR 엔진 위에서 <b>사용자의 생각·감정·가치관을 구조화</b>하고, 이를 <b>더 나은 인간 연결</b>로 확장하는 개인 인텔리전스 서비스. "
            "창업자가 시나브로·WETHUS에서 이어온 ‘사람을 연결하는 플랫폼’의 다음 단계이자, ATANOR의 로컬·정직·프라이버시 가치가 가장 빛나는 소비자 진입점입니다.")]
story += [sp(8)]

# 5. 차별점 (measured)
story += [Rule(170*mm), sp(3), h1("5. 경쟁력 / 차별점 — 측정된 사실")]
story += [p("기존 AI를 ‘더 큰 LLM’으로 이기는 게 아니라 <b>AI의 구조 자체를 다시 설계</b>합니다. 아래 수치는 마케팅이 아니라 <b>자체 실측값</b>입니다.")]
story += [metric_table([
    ("환각률(거짓 단정)", "~0%", "존재하지 않는 개체 함정 전부 abstain (날조 0)"),
    ("출처/인용", "100%", "모든 웹 답변이 실제 출처 URL 보유"),
    ("답변 시 GPU", "0", "모델 추론 없음 (LLM: 수백 W)"),
    ("질문당 에너지", "~0.001 Wh", "LLM ~0.3–3 Wh → 100–1000배 적음"),
    ("모델 가중치 / VRAM", "0 GB / 0", "LLM: 2.4–40 GB / 4–48 GB"),
    ("설치 용량", "~11 MB + 그래프", "GPU 없는 기기에서도 구동"),
    ("프라이버시", "로컬 우선", "사적 메모리 비업로드"),
], ("지표", "ATANOR (실측)", "비교 / 의미"))]
story += [sp(3)]
story += [b("<b>로컬-first</b>: 개인 맥락이 외부 모델에 흡수되지 않고 기기 안에 남음")]
story += [b("<b>온톨로지 그래프</b>: concept·relation·evidence·case-frame으로 구조화 → 추적 가능한 지식 경로")]
story += [b("<b>candidate↔verified 분리</b>: 새 지식은 후보로만 쌓이고 검증 후 승격 → 환각·오염 차단")]
story += [b("<b>결정론적 다단계 추론</b>: ‘A와 B 중 누가 먼저?’(비교), ‘프랑스의 수도의 인구?’(연쇄 2-hop)를 LLM 없이")]
story += [sp(3), p("<font color='#666666' size=9>정직한 한계: 그래프+검색 구조라 지식 커버리지는 프런티어 LLM보다 좁고, 일반 추론 깊이는 아직 얕습니다. "
                   "캐시되지 않은 사실엔 인터넷이 필요합니다 — 설계상의 트레이드오프입니다.</font>")]
story += [PageBreak()]

# 6. 수익모델
story += [Rule(170*mm), sp(3), h1("6. 수익모델")]
story += [p("장기적으로 B2C·B2B를 함께 봅니다. 핵심: <b>추론에 GPU가 들지 않아 단위 운영비(COGS)가 극히 낮습니다.</b>")]
story += [metric_table([
    ("개인 로컬 AI OS 구독", "월 9,900–29,000원", "로컬 그래프 관리·백그라운드 학습·동기화 등 고급 기능"),
    ("Pro (개발자·연구자)", "월 39,000–99,000원", "대규모 문서/코드 인덱싱·프로젝트 브레인·Answer Quality Lab"),
    ("팀/기업 온프레미스", "구축+월유지+시트", "데이터 외부 노출 없이 사내에서 운영하는 지식 AI"),
    ("Graph Cartridge 마켓", "수수료/구독", "도메인 지식 그래프(법률·의료·창업 등) 거래"),
    ("Atlas Network(장기)", "기여 보상", "공개 지식 검증 기여자 credit·생태계 수익공유"),
], ("모델", "가격(검토)", "내용"), widths=(40*mm,38*mm,88*mm))]
story += [sp(3), p("초기에는 <b>개발자·연구자용 Pro</b>와 <b>팀용 온프레미스</b>로 검증 → 이후 BELIFE(B2C)와 Cartridge·Atlas로 확장.")]
story += [sp(8)]

# 7. 경쟁 서비스
story += [Rule(170*mm), sp(3), h1("7. 유사 / 경쟁 서비스")]
story += [metric_table([
    ("ChatGPT (OpenAI)", "범용 추론·도구", "중앙 클라우드 / 로컬 지식 소유·그래프 부재"),
    ("Claude (Anthropic)", "긴 문맥·글쓰기", "외부 모델 호출 중심 / 후보·검증 그래프 구조 아님"),
    ("Perplexity", "검색·출처 답변", "검색 응답 위주 / 온톨로지 축적·로컬 브레인 연결 아님"),
], ("서비스", "강점", "ATANOR와의 차이"), widths=(40*mm,46*mm,80*mm))]
story += [sp(3), p("ATANOR는 이들을 직접 대체하기보다, <b>개인 기억(로컬) + 검증 가능한 공용 그래프</b>를 분리 관리하는 개인 AI 운영체제로 포지셔닝합니다. "
                   "해자는 단일 기능이 아니라 <b>‘정직성 + 경량성 + 프라이버시’의 결합</b>이며, LLM 진영이 따라오려면 근본 아키텍처를 바꿔야 합니다.")]
story += [sp(8)]

# 8. 성과/지표
story += [Rule(170*mm), sp(3), h1("8. 성과 / 지표 (개발 단계)")]
story += [p("매출·고객 단계가 아니므로 정량 매출 지표는 없습니다. 대신 <b>기술 검증 지표</b>가 실제 코드로 재현됩니다.")]
story += [b("최근 6개월: 아이디어 → 작동하는 <b>로컬-first AI 프로토타입</b> (GitHub 모노레포, FastAPI + Next.js + Python 패키지)")]
story += [b("공개 코퍼스 기반 <b>10k·100k candidate-only 검증</b> 완료 (100k run: 100,000 payload 처리, 66,304 승인)")]
story += [b("<b>persistent candidate learning daemon</b>로 6h 완료, 24h run 진행 — 학습 중 production·Local Brain 불변")]
story += [b("Production verified store(예): ~8,060 concepts · 33,032 relations · 8,364 evidence · 8,281 case-frames")]
story += [b("안전 불변조건 유지: production_store_mutated=false · local_brain_write=false · external_llm_used=false · mock_growth=false")]
story += [b("<b>측정 벤치마크</b>: 67문항 하니스 — 환각 0% · 인용 100% / 에너지·footprint 하드웨어 실측(GPU 0, ~0.001Wh, 가중치 0)")]
story += [sp(8)]

# 9. 재무 및 기타
story += [Rule(170*mm), sp(3), h1("9. 재무 및 기타")]
story += [Field("외부투자 현황", "없음")]
story += [Field("회사 부채", "없음")]
story += [Field("분쟁/소송", "없음")]
story += [Field("투자 요청", "현재 없음 (연구·개발 단계) — 프라이머를 통해 기술 실험을 실제 제품·사업으로 발전시키고자 함")]
story += [sp(2), h2("기타 하고 싶은 이야기")]
story += [p("저는 고등학생 창업자입니다. 시나브로로 사람의 글을, WETHUS로 사람의 도전을 연결해왔고, 그때마다 부딪힌 질문은 같았습니다 — "
            "<b>‘이 사람들의 생각과 기억은 결국 누구의 것인가.’</b> 지금의 AI는 편리하지만 그 답을 거대 클라우드에 맡깁니다. "
            "ATANOR는 그 답을 사용자에게 돌려주려는, 작지만 끝까지 파고든 실제 코드입니다. ‘더 큰 모델’이 아니라 <b>‘더 인간다운 기억 구조’</b>로요. "
            "아직 사업 경험은 부족하지만, 저는 이걸 아이디어가 아니라 <b>작동하는 시스템</b>으로 만들어 측정 가능한 사실(환각 0·GPU 0)까지 확인했습니다.")]
story += [sp(8), Rule(170*mm, GREY, 0.7), sp(3)]
story += [Paragraph("부록 — 측정 출처: factual_qa_benchmark.py(67문항) · ATANOR_ENERGY_EFFICIENCY.md · ATANOR_FOOTPRINT.md · "
                    "ATANOR_VS_LLMS_NUMBERS.md · comparison_reasoner.py · chained_reasoner.py. "
                    "※ 비교 LLM 수치는 공개 리더보드(Vectara HHEM·ALCE·MMLU 등) 추정값으로 서로 다른 테스트셋이므로 방향성 비교입니다.", st_small)]

def cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(BLACK); canvas.rect(0, 0, A4[0], A4[1], fill=1, stroke=0)
    cx = A4[0]/2
    laurel(canvas, cx-34*mm, A4[1]-118*mm, 12*mm, colors.white)
    canvas.setFillColor(colors.white); canvas.setFont("MB", 30)
    canvas.drawString(cx-16*mm, A4[1]-122*mm, "ATANOR")
    canvas.setFont("M", 12); canvas.setFillColor(colors.HexColor("#cccccc"))
    canvas.drawCentredString(cx, A4[1]-140*mm, "탈중앙화 뉴로모픽 하이브리드 AI")
    canvas.setFont("MB", 13); canvas.setFillColor(colors.white)
    canvas.drawCentredString(cx, A4[1]-162*mm, "사업계획서 · Primer 2026 배치 지원")
    canvas.setStrokeColor(colors.HexColor("#444444")); canvas.setLineWidth(0.6)
    canvas.line(cx-30*mm, A4[1]-170*mm, cx+30*mm, A4[1]-170*mm)
    canvas.setFont("M", 11); canvas.setFillColor(colors.HexColor("#aaaaaa"))
    canvas.drawCentredString(cx, A4[1]-182*mm, "“환각하지 않고, GPU 없이, 출처를 증명하며 답하는 AI”")
    canvas.setFont("M", 9.5); canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawCentredString(cx, 40*mm, "대표 김안석 · 넥스트챌린지스쿨 · 2026.06")
    canvas.drawCentredString(cx, 33*mm, "성능 수치는 자체 실측값입니다 (부록 참조). 팀/재무 [   ]는 보강 예정.")
    canvas.restoreState()

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("M", 8); canvas.setFillColor(GREY)
    laurel(canvas, 22*mm, 13*mm, 2.6*mm, GREY)
    canvas.drawString(28*mm, 11.6*mm, "ATANOR · 사업계획서 (Confidential)")
    canvas.drawRightString(190*mm, 11.6*mm, "%d" % (doc.page-1))
    canvas.setStrokeColor(FAINT); canvas.setLineWidth(0.5); canvas.line(20*mm, 16*mm, 190*mm, 16*mm)
    canvas.restoreState()

out = r"C:\0.ASKIM ALL-VIN\ATANOR-live-selfhood-scheduler\ATANOR_사업계획서.pdf"
doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                        topMargin=18*mm, bottomMargin=20*mm, title="ATANOR 사업계획서", author="김안석")
doc.build(story, onFirstPage=cover, onLaterPages=footer)
print("WROTE", out)
