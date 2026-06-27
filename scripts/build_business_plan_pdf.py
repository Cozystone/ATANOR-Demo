# -*- coding: utf-8 -*-
"""ATANOR business plan PDF — standard structure, black & white brand.

Logo: if assets/atanor_logo.png exists it is embedded as-is; otherwise a vector
laurel + outlined ATANOR wordmark is drawn in the same monochrome style.
"""
import math, os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable

ROOT = r"C:\0.ASKIM ALL-VIN\ATANOR-live-selfhood-scheduler"
LOGO = os.path.join(ROOT, "assets", "atanor_logo.png")
pdfmetrics.registerFont(TTFont("M", r"C:\Windows\Fonts\malgun.ttf"))
pdfmetrics.registerFont(TTFont("MB", r"C:\Windows\Fonts\malgunbd.ttf"))

BLACK=colors.HexColor("#0a0a0a"); INK=colors.HexColor("#141414"); GREY=colors.HexColor("#6a6a6a")
FAINT=colors.HexColor("#e6e6e6"); ZEBRA=colors.HexColor("#f5f5f5")

def S(n,sz,ld,f="M",c=INK,sb=0,sa=6,al=TA_LEFT,li=0):
    return ParagraphStyle(n,fontName=f,fontSize=sz,leading=ld,textColor=c,spaceBefore=sb,spaceAfter=sa,alignment=al,leftIndent=li)
st_h1=S("h1",15,20,"MB",BLACK,sb=2,sa=8); st_h2=S("h2",11.3,16,"MB",INK,sb=9,sa=3)
st_body=S("b",10.2,16,"M",INK,sa=5); st_bul=S("bu",10.2,15.4,"M",INK,sa=3,li=11)
st_lead=S("ld",10.6,16.4,"M",INK,sa=6); st_small=S("sm",8.5,12.3,"M",GREY,sa=2)
st_cell=S("c",9.1,12.7,"M",INK); st_cellb=S("cb",9.1,12.7,"MB",INK); st_cellw=S("cw",9.1,12.7,"MB",colors.white)
st_kick=S("k",9.4,13,"MB",GREY,sa=2)
def h1(n,t): return Paragraph(f'<font color="#9a9a9a">{n}</font>&nbsp;&nbsp;{t}', st_h1)
def h2(t): return Paragraph(t, st_h2)
def P(t): return Paragraph(t, st_body)
def lead(t): return Paragraph(t, st_lead)
def b(t): return Paragraph("·&nbsp;&nbsp;"+t, st_bul)
def sp(h=6): return Spacer(1,h)

class Rule(Flowable):
    def __init__(s,w,c=BLACK,t=1.4): super().__init__(); s.w=w;s.c=c;s.t=t
    def wrap(s,*a): return (s.w,s.t)
    def draw(s): s.canv.setStrokeColor(s.c); s.canv.setLineWidth(s.t); s.canv.line(0,0,s.w,0)

def laurel(c,cx,cy,R,col):
    c.setFillColor(col); c.setStrokeColor(col); c.setLineWidth(max(0.5,R*0.05))
    for side in (-1,1):
        a0,a1,n=-100,82,11
        for i in range(n):
            t=i/(n-1); ang=math.radians(a0+(a1-a0)*t)
            bx=cx+side*R*math.cos(ang); by=cy+R*math.sin(ang)
            c.saveState(); c.translate(bx,by); c.rotate(math.degrees(ang)+90*side)
            lw=R*0.34; lh=R*0.13
            p=c.beginPath(); p.moveTo(0,0); p.curveTo(lw*0.4,lh, lw*0.85,lh*0.5, lw,0)
            p.curveTo(lw*0.85,-lh*0.5, lw*0.4,-lh, 0,0); c.drawPath(p,fill=1,stroke=0)
            c.restoreState()
    c.setLineWidth(max(0.8,R*0.05))
    c.line(cx,cy-R*1.0, cx-R*0.36,cy-R*0.66); c.line(cx,cy-R*1.0, cx+R*0.36,cy-R*0.66)

def wordmark(c,x,y,size,col):
    c.saveState(); c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(max(0.6,size*0.018))
    t=c.beginText(x,y); t.setFont("M",size); t.setCharSpace(size*0.14); t.setTextRenderMode(1); t.textOut("ATANOR")
    c.drawText(t); c.restoreState()

def draw_logo(c,cx,cy,h,col):
    """Centered logo (laurel + ATANOR). h = laurel diameter-ish height."""
    if os.path.exists(LOGO):
        img=ImageReader(LOGO); iw,ih=img.getSize(); w=h*2.6*(iw/ih)
        c.drawImage(img, cx-w/2, cy-h*1.3/2, width=w, height=h*1.3, mask='auto'); return
    R=h*0.5
    laurel(c, cx-R*2.7, cy, R, col)
    wordmark(c, cx-R*1.4, cy-R*0.42, R*1.05, col)

def mtable(rows,header,widths):
    data=[[Paragraph(x,st_cellw) for x in header]]
    for r in rows: data.append([Paragraph(r[0],st_cellb)]+[Paragraph(x,st_cell) for x in r[1:]])
    t=Table(data,colWidths=list(widths))
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),BLACK),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,ZEBRA]),
        ("GRID",(0,0),(-1,-1),0.4,FAINT),("BOX",(0,0),(-1,-1),0.7,INK),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),7),("RIGHTPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    return t

def overview():
    rows=[("회사명","ATANOR (아타노르) · 미설립 가칭"),("형태","사업자 없음 — 연구·개발 단계"),
          ("제품/서비스","ATANOR — 온톨로지 기반 탈중앙화 뉴로모픽 하이브리드 AI"),
          ("한 줄 소개","환각하지 않고, GPU 없이 돌며, 모든 답의 출처를 증명하는 개인 소유 AI"),
          ("대표","김안석 (단독 창업)"),("URL","github.com/Cozystone/ATANOR"),
          ("CEO 1분 영상","추후 제출 (제목: 프라이머2026-ATANOR-김안석)")]
    data=[[Paragraph(k,st_cellb),Paragraph(v,st_cell)] for k,v in rows]
    t=Table(data,colWidths=[34*mm,136*mm])
    t.setStyle(TableStyle([("LINEBELOW",(0,0),(-1,-1),0.4,FAINT),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("BACKGROUND",(0,0),(0,-1),colors.HexColor("#fafafa")),("LEFTPADDING",(0,0),(-1,-1),8),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)])); return t

story=[]
story+=[Spacer(1,250*mm),PageBreak()]                      # cover (drawn in onFirstPage)

# ---- TOC ----
story+=[sp(4),Paragraph("목차",S("toc",20,26,"MB",BLACK,sa=12))]
toc=[("01","요약 (Executive Summary)"),("02","문제 (Problem)"),("03","솔루션 · 제품 (Solution & Product)"),
     ("04","핵심 차별점 — 측정된 사실 (Why ATANOR)"),("05","시장 (Market)"),("06","비즈니스 모델 (Business Model)"),
     ("07","경쟁 환경 (Competitive Landscape)"),("08","실행 로드맵 (Roadmap)"),("09","성과 · 현황 (Traction)"),
     ("10","팀 (Team)"),("11","재무 · 비전 (Financials & Vision)"),("—","부록 (Appendix)")]
for n,t in toc:
    story+=[Table([[Paragraph(f'<font color="#9a9a9a">{n}</font>',S("tn",11,16,"MB")),Paragraph(t,S("tt",11,16,"M",INK))]],
                  colWidths=[14*mm,156*mm], style=TableStyle([("LINEBELOW",(0,0),(-1,-1),0.4,FAINT),("BOTTOMPADDING",(0,0),(-1,-1),7),("TOPPADDING",(0,0),(-1,-1),5)]))]
story+=[PageBreak()]

# ---- 01 EXEC ----
story+=[h1("01","요약")]
story+=[overview(), sp(8)]
story+=[lead("<b>ATANOR는 외부 거대언어모델(LLM)을 쓰지 않고, 명시적 지식 그래프와 실시간 검색으로 답하는 로컬-first AI입니다.</b> "
            "답은 그래프에서 파생되거나 공개 웹에서 그대로 인용되며, 모든 답에 출처와 추론 증명서가 붙습니다. 근거가 없으면 지어내지 않고 ‘모르겠다’라고 합니다. "
            "‘더 큰 모델’이 아니라 <b>‘더 인간다운 기억 구조’</b>로, 개인 기억은 로컬에 보존하고 공용 지식은 검증 가능한 그래프로 키웁니다.")]
story+=[h2("자체 실측 핵심 지표")]
story+=[mtable([("환각률(거짓 단정)","~0%","프런티어 LLM ~1.5–6%"),("출처/인용","100%","LLM 기본 0%"),
    ("답변 시 GPU","0","LLM 수백 W"),("질문당 에너지","~0.001 Wh","LLM ~0.3–3 Wh"),
    ("모델 가중치/VRAM","0 GB / 0","LLM 2.4–40 GB / 4–48 GB"),("설치","~11 MB + 그래프","GPU 없는 기기도 구동")],
    ("지표","ATANOR (실측)","비교"),(46*mm,58*mm,62*mm))]
story+=[PageBreak()]

# ---- 02 PROBLEM ----
story+=[h1("02","문제")]
story+=[P("AI 시장은 빠르게 성장하지만, 대부분의 서비스는 <b>중앙집중형 클라우드 LLM</b>에 의존합니다. 강력하지만 네 가지 구조적 한계로 신뢰 영역의 도입이 막힙니다.")]
story+=[b("<b>비용·에너지</b> — 질문마다 GPU 추론(~0.3–3 Wh, 수백 W). 개인·소팀이 자기 AI를 장기 운영하기엔 부담.")]
story+=[b("<b>데이터 주권</b> — 더 좋은 답을 받으려면 개인·기업의 지식을 외부 클라우드로 보내야 함.")]
story+=[b("<b>장기 기억·개인화의 한계</b> — 사람처럼 경험을 쌓고 ‘자라나는’ AI 구조가 부재.")]
story+=[b("<b>환각·출처 불투명</b> — 답이 어떤 근거에서 나왔는지 증명 불가 (의료·법률·교육·연구·기업 업무에 치명적).")]
story+=[sp(4),P("<b>기회:</b> 이 문제는 ‘더 큰 모델’이 아니라 <b>‘다른 구조’</b>로 풀립니다. 개인 기억은 로컬에 두고, 공용 지식은 후보(candidate)와 검증(verified)을 "
            "분리해 출처·중복·모순·품질을 통과해야 승격합니다. AI가 문장을 ‘생성’만 하는 게 아니라 지식을 <b>축적·발견·검증하며 로컬에서 성장</b>합니다.")]
story+=[PageBreak()]

# ---- 03 SOLUTION/PRODUCT ----
story+=[h1("03","솔루션 · 제품")]
story+=[P("ATANOR는 지식·기억·추론·표현·학습·검증을 모델 파라미터에 압축하지 않고 <b>분리된 모듈</b>로 구성한 <b>로컬-first AI 운영체제</b>입니다.")]
story+=[h2("핵심 구조")]
story+=[b("<b>Local Brain</b> — 개인 기억·문서·맥락·선호를 기기 안에만 보존하는 사적 계층 (자동 비전송 원칙)")]
story+=[b("<b>Cloud Brain</b> — 공개 지식 그래프. <b>후보↔검증 분리</b>, 출처·중복·모순·품질 검사 후에만 승격")]
story+=[b("<b>Surface Brain · CGSR · RHFC</b> — 그래프 지식을 자연어로 표현하는 표면화·생성·공명기억 계층")]
story+=[b("<b>Autonomy Kernel · Midnight Congress</b> — World/Self 모델의 결핍 신호로 ‘무엇이 부족한지’ 제안 (proposal-only, proof 단계)")]
story+=[b("<b>Tabularis Privacy Shield · Atlas Trust Router · Atlas Congress</b> — 프라이버시·신뢰 라우팅·P2P 지식 토론장의 초기 구조")]
story+=[h2("작동 방식")]
story+=[b("질문 → 그래프/기억에서 근거 탐색 → 근거가 있으면 그래프 파생 답, 없으면 공개 웹 인용 + 출처 표시")]
story+=[b("결정론적 <b>다단계 추론</b>: ‘A와 B 중 누가 먼저 태어났어?’(비교), ‘프랑스의 수도의 인구는?’(연쇄 2-hop) — LLM 없이")]
story+=[b("모든 답에 <b>추론 증명서</b>(근거·도출 방식·보증) 첨부 → 감사 가능")]
story+=[sp(2),P("ATANOR는 챗봇이 아니라, 개인 컴퓨터 안에서 기억을 키우고 공개 지식을 검증·승격하며, 장차 여러 로컬 AI가 안전하게 연결되는 <b>개인 AI 운영체제</b>입니다.")]
story+=[PageBreak()]

# ---- 04 DIFF ----
story+=[h1("04","핵심 차별점 — 측정된 사실")]
story+=[P("기존 AI를 ‘더 큰 LLM’으로 이기는 게 아니라 <b>AI의 구조 자체를 다시 설계</b>합니다. 아래는 마케팅이 아니라 <b>자체 코드로 재현되는 실측값</b>입니다.")]
story+=[mtable([("환각률(거짓 단정)","~0%","존재하지 않는 개체 함정 전부 abstain (날조 0)"),("출처/인용","100%","모든 웹 답변이 실제 출처 URL 보유"),
    ("답변 시 GPU","0","모델 추론 없음 (LLM: 수백 W)"),("질문당 에너지","~0.001 Wh","LLM 대비 100–1000배 적음"),
    ("가중치/VRAM","0 GB / 0","LLM 2.4–40 GB / 4–48 GB"),("설치","~11 MB","GPU 없는 기기에서도 구동"),("프라이버시","로컬 우선","사적 메모리 비업로드")],
    ("지표","ATANOR","의미"),(44*mm,40*mm,82*mm))]
story+=[sp(3)]
story+=[b("<b>로컬-first</b> — 개인 맥락이 외부 모델에 흡수되지 않고 기기 안에 남음 (데이터 주권)")]
story+=[b("<b>온톨로지 그래프</b> — concept·relation·evidence·case-frame 구조화 → 추적 가능한 지식 경로")]
story+=[b("<b>candidate↔verified 분리</b> — 새 지식은 후보로만 쌓이고 검증 후 승격 → 환각·오염 차단")]
story+=[b("<b>저에너지·저footprint</b> — GPU 없이 도는 구조가 곧 단위 운영비(COGS) 우위로 직결")]
story+=[sp(3),P("<font color='#6a6a6a' size=9>정직한 한계: 그래프+검색 구조라 지식 커버리지는 프런티어 LLM보다 좁고, 일반 추론 깊이는 아직 얕습니다. "
            "캐시되지 않은 사실엔 인터넷이 필요합니다 — 설계상의 의도된 트레이드오프입니다.</font>")]
story+=[PageBreak()]

# ---- 05 MARKET ----
story+=[h1("05","시장")]
story+=[h2("시장 규모 (출처 기반)")]
story+=[mtable([("엣지/온디바이스 AI","$11.8B (2025) → $56.8B (2030)","CAGR 36.9% — GPU 없이 도는 AI의 핵심 시장"),
    ("프라이빗/온프레미스 AI 수요","엔터프라이즈 AI 내 별도 성장축","데이터 외부 유출 불가 조직의 구조적 수요")],
    ("구분","규모","비고 / 출처: BCC·Grandview·Precedence Research"),(40*mm,56*mm,70*mm))]
story+=[sp(3),P("ATANOR는 ‘가장 똑똑한 모델’ 경쟁이 아니라 <b>‘틀리면 안 되고, 밖으로 나가면 안 되고, 싸게 돌아야 하는’</b> 세그먼트를 정조준합니다.")]
story+=[h2("타깃 · 초기 고객")]
story+=[b("자기 문서·코드·연구를 장기 기억으로 쌓고 싶은 <b>개발자·연구자</b>")]
story+=[b("내부 지식을 외부 서버에 노출하지 않고 AI로 쓰려는 <b>소규모 팀·스타트업</b> (온프레미스)")]
story+=[b("규제·고신뢰 산업(<b>금융·의료·법률·공공</b>) — 환각·유출이 허용되지 않는 영역")]
story+=[b("로컬-first·개인 지식주권·탈중앙 AI에 관심 있는 <b>고급 사용자·얼리어답터</b>")]
story+=[PageBreak()]

# ---- 06 BIZ MODEL ----
story+=[h1("06","비즈니스 모델")]
story+=[P("B2C·B2B를 함께 봅니다. 핵심: <b>추론에 GPU가 들지 않아 단위 운영비(COGS)가 극히 낮아</b> 가격·마진·엣지 배포 모두에서 구조적 이점입니다.")]
story+=[mtable([("개인 로컬 AI OS 구독","월 9,900–29,000원","로컬 그래프 관리·백그라운드 학습·동기화"),
    ("Pro (개발자·연구자)","월 39,000–99,000원","대규모 문서/코드 인덱싱·프로젝트 브레인·Answer Quality Lab"),
    ("팀/기업 온프레미스","구축+월유지+시트","데이터 외부 노출 없이 사내에서 운영하는 지식 AI"),
    ("Graph Cartridge 마켓","수수료/구독","도메인 지식 그래프(법률·의료·창업) 거래"),
    ("Atlas Network (장기)","기여 보상","공개 지식 검증 기여자 credit·생태계 수익공유")],
    ("수익 모델","가격(검토)","내용"),(40*mm,38*mm,88*mm))]
story+=[sp(3),P("초기에는 <b>개발자·연구자용 Pro</b>와 <b>팀용 온프레미스</b>로 매출을 검증하고, 이후 Cartridge 마켓·Atlas Network로 확장합니다.")]
story+=[PageBreak()]

# ---- 07 COMPETITION ----
story+=[h1("07","경쟁 환경")]
story+=[mtable([("ChatGPT (OpenAI)","범용 추론·도구","중앙 클라우드 / 로컬 지식 소유·그래프 부재"),
    ("Claude (Anthropic)","긴 문맥·글쓰기","외부 모델 호출 중심 / 후보·검증 그래프 아님"),
    ("Perplexity","검색·출처 답변","검색 응답 위주 / 온톨로지 축적·로컬 브레인 연결 아님"),
    ("로컬 LLM (Llama·ollama)","오프라인 구동","환각(소형도 발생)·수 GB 가중치·VRAM 필요 → ATANOR는 0")],
    ("경쟁군","강점","ATANOR와의 차이"),(42*mm,42*mm,82*mm))]
story+=[sp(3),P("ATANOR는 이들을 직접 대체하기보다 <b>개인 기억(로컬) + 검증 가능한 공용 그래프</b>를 분리 관리하는 개인 AI 운영체제로 포지셔닝합니다. "
            "해자는 단일 기능이 아니라 <b>‘정직성 + 경량성 + 프라이버시’의 결합</b>이며, LLM 진영이 따라오려면 근본 아키텍처(생성형 가중치 모델)를 바꿔야 합니다. "
            "여기에 도메인 그래프 자산과 Atlas 네트워크 효과가 시간이 갈수록 방어력을 누적합니다.")]
story+=[PageBreak()]

# ---- 08 ROADMAP ----
story+=[h1("08","실행 로드맵")]
story+=[h2("단기 (0–6개월)")]
story+=[b("작동 프로토타입 → 클로즈드 베타; 개발자·연구자 대상 무료 체험으로 사용성 검증")]
story+=[b("공개 벤치마크 100문항 + 에너지·footprint 백서 공개 — ‘정직성’을 신뢰 마케팅 자산으로")]
story+=[h2("중기 (6–18개월)")]
story+=[b("팀용 온프레미스 패키지 + 도메인 그래프 팩(법률·의료·금융) 상용화")]
story+=[b("추론 코어 심화(PHFE: 위상 홀로그래픽 폴딩)로 일반 다단계 추론 강화")]
story+=[b("분산 컨트리뷰터 클라우드(Atlas Network) v1 — 다수 노드 공용 학습")]
story+=[h2("장기 비전")]
story+=[P("<b>‘프로그램 안에 사는 정직한 생명체’</b> — 모든 기기에서 GPU 없이 돌고, 환각하지 않으며, 모든 답을 증명하는 "
            "<b>신뢰 가능한 AI 인프라</b>. LLM이 ‘가장 똑똑한 답’을 겨룰 때, ATANOR는 ‘가장 믿을 수 있고 가장 가벼운 답’의 표준이 됩니다.")]
story+=[PageBreak()]

# ---- 09 TRACTION ----
story+=[h1("09","성과 · 현황")]
story+=[P("매출·고객 단계가 아니므로 정량 매출 지표는 없습니다. 대신 <b>기술 검증 지표가 실제 코드로 재현</b>됩니다 (개발 단계).")]
story+=[b("최근 6개월: 아이디어 → 작동하는 <b>로컬-first AI 프로토타입</b> (GitHub 모노레포, FastAPI + Next.js + Python 패키지)")]
story+=[b("공개 코퍼스 기반 <b>10k·100k candidate-only 검증</b> 완료 (100k: 100,000 payload 처리, 66,304 승인)")]
story+=[b("<b>persistent candidate learning daemon</b> 6h 완료, 24h run 진행 — 학습 중 production·Local Brain 불변")]
story+=[b("Production verified store(예): ~8,060 concepts · 33,032 relations · 8,364 evidence · 8,281 case-frames")]
story+=[b("안전 불변조건 유지: production_store_mutated=false · local_brain_write=false · external_llm_used=false · mock_growth=false")]
story+=[b("<b>측정 벤치마크</b>: 67문항 하니스 — 환각 0% · 인용 100% / 에너지·footprint 하드웨어 실측(GPU 0, ~0.001 Wh, 가중치 0)")]
story+=[PageBreak()]

# ---- 10 TEAM ----
story+=[h1("10","팀")]
story+=[P("<b>김안석 — 대표 (단독 창업자)</b>")]
story+=[b("<b>넥스트챌린지스쿨</b> 재학 — 서울시교육청 인가 <b>국내 첫 창업 특화 대안 고등학교</b>. AI·글로벌·창업 융합 커리큘럼, "
            "글로벌 대학 교수·빅테크·스타트업 대표가 가르치며 Google·Intel·Thales 등과 협력하는 ‘테슬라 국제학교’.")]
story+=[sp(2),h2("창업 트랙레코드 — 일관된 ‘사람을 연결하는 플랫폼’")]
story+=[b("<b>시나브로</b> (문학인을 위한 SNS) — <b>학생창업유망팀 U300+ 도약트랙 최종선발</b>")]
story+=[b("<b>WETHUS</b> (학생 창업 프로젝트 플랫폼) — <b>‘모두의 창업’ 1차 심사 통과</b>")]
story+=[b("<b>BELIFE</b> (개인 인텔리전스 서비스) — 사용자의 생각·감정·가치관 구조화를 실험한 직전 프로젝트")]
story+=[sp(3),P("<b>Founder–Market Fit:</b> 시나브로(글)→WETHUS(도전)→BELIFE(생각)까지, 저는 일관되게 <b>‘사람의 생각을 구조화하고 사람을 더 잘 연결하는 플랫폼’</b>을 "
            "만들어 왔고 매번 외부 인정(U300+, 모두의창업)으로 검증받았습니다. ATANOR는 그 플랫폼들이 진짜로 필요로 하던 "
            "<b>‘개인이 소유하는, 믿을 수 있는 AI’</b>를 가장 아래 계층부터 직접 만드는 시도입니다. 고등학생이지만, 아이디어가 아니라 "
            "측정 가능한 사실(환각 0·GPU 0)까지 만들어낸 <b>실행력</b>이 가장 큰 강점입니다.")]
story+=[PageBreak()]

# ---- 11 FINANCE/VISION ----
story+=[h1("11","재무 · 비전")]
story+=[mtable([("외부투자","없음","연구·개발 단계"),("부채","없음","-"),("분쟁/소송","없음","-")],
    ("항목","현황","비고"),(40*mm,40*mm,86*mm))]
story+=[sp(4),h2("자금 계획 (방향)")]
story+=[P("현재 별도 투자 유치 단계는 아닙니다. 프라이머를 통해 이 프로젝트를 <b>기술 실험에서 실제 제품·사업으로</b> 발전시키고자 하며, "
            "초기 자금은 ① 제품·온프레미스 패키지화, ② 개발자·연구자 베타 확보, ③ 벤치마크 공개를 통한 신뢰 포지셔닝에 집중할 계획입니다.")]
story+=[sp(2),h2("끝으로")]
story+=[P("저는 고등학생 창업자입니다. 시나브로로 사람의 글을, WETHUS로 사람의 도전을 연결해왔고, 그때마다 같은 질문에 부딪혔습니다 — "
            "<b>‘이 사람들의 생각과 기억은 결국 누구의 것인가.’</b> 지금의 AI는 편리하지만 그 답을 거대 클라우드에 맡깁니다. "
            "ATANOR는 그 답을 사용자에게 돌려주려는, 작지만 끝까지 파고든 실제 코드입니다.")]
story+=[sp(10),Rule(170*mm,GREY,0.6),sp(3)]
story+=[Paragraph("부록 — 측정 출처: factual_qa_benchmark.py(67문항) · ATANOR_ENERGY_EFFICIENCY.md · ATANOR_FOOTPRINT.md · "
            "ATANOR_VS_LLMS_NUMBERS.md · comparison_reasoner.py · chained_reasoner.py. "
            "※ 비교 LLM 수치는 공개 리더보드(Vectara HHEM·ALCE·MMLU 등) 추정값으로 서로 다른 테스트셋이라 방향성 비교입니다.", st_small)]

def cover(c,doc):
    c.saveState(); c.setFillColor(BLACK); c.rect(0,0,A4[0],A4[1],fill=1,stroke=0)
    cx=A4[0]/2
    draw_logo(c, cx, A4[1]-120*mm, 16*mm, colors.white)
    c.setFont("M",12); c.setFillColor(colors.HexColor("#cfcfcf"))
    c.drawCentredString(cx, A4[1]-150*mm, "온톨로지 기반 탈중앙화 뉴로모픽 하이브리드 AI")
    c.setStrokeColor(colors.HexColor("#3a3a3a")); c.setLineWidth(0.6); c.line(cx-26*mm,A4[1]-158*mm,cx+26*mm,A4[1]-158*mm)
    c.setFont("MB",13); c.setFillColor(colors.white)
    c.drawCentredString(cx, A4[1]-170*mm, "사업계획서 · Primer 2026 배치 지원")
    c.setFont("M",10.5); c.setFillColor(colors.HexColor("#9a9a9a"))
    c.drawCentredString(cx, A4[1]-182*mm, "“환각하지 않고, GPU 없이, 출처를 증명하며 답하는 AI”")
    c.setFont("M",9.5); c.setFillColor(colors.HexColor("#7a7a7a"))
    c.drawCentredString(cx, 38*mm, "대표 김안석 · 넥스트챌린지스쿨 · 2026.06")
    c.drawCentredString(cx, 31*mm, "본 문서의 성능 수치는 자체 실측값입니다 (부록 출처 참조)")
    c.restoreState()

def footer(c,doc):
    c.saveState(); c.setFont("M",8); c.setFillColor(GREY)
    laurel(c, 22*mm, 12.6*mm, 2.4*mm, GREY)
    c.drawString(27*mm,11.4*mm,"ATANOR · 사업계획서"); c.drawRightString(190*mm,11.4*mm,"%d"%(doc.page-1))
    c.setStrokeColor(FAINT); c.setLineWidth(0.5); c.line(20*mm,15.5*mm,190*mm,15.5*mm); c.restoreState()

out=os.path.join(ROOT,"ATANOR_사업계획서.pdf")
SimpleDocTemplate(out,pagesize=A4,leftMargin=20*mm,rightMargin=20*mm,topMargin=20*mm,bottomMargin=20*mm,
                  title="ATANOR 사업계획서",author="김안석").build(story,onFirstPage=cover,onLaterPages=footer)
print("WROTE",out,"| logo file used:",os.path.exists(LOGO))
