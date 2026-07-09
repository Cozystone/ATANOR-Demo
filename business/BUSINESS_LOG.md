# ATANOR 사업 로그

팀 공용 append-only 로그. 형식: `## YYYY-MM-DD HH:MM — 에이전트명` + 요약 + 다음 조치.

## 2026-07-09 — 시스템 구축 (Fable5)
- 에이전트 팀 헌장(TEAM.md) + 채널 플레이북 + 런치 시퀀스 + 승인 큐 구조 생성.
- 에이전트 5종 정의: chief / ops / dev / marketing / revenue (사용자 레벨 ~/.claude/agents/).
- 자동화 스케줄 3종 등록: 매일 ops 스윕, 월·목 그로스 배치, 월요일 주간 리포트.
- 표적 확인: 공개 리포 Cozystone/ATANOR + ATANOR-Demo, 랜딩 200 OK.
- [승인 대기] 첫 런치 콘텐츠 배치가 approval_queue에 생성되면 운영자 검토 필요.


## 2026-07-09 09:25 — atanor-ops
- 첫 베이스라인 헬스 스윕 완료(읽기 전용, 무수리). 리포트: `business/metrics/daily/2026-07-09.md` 생성(디렉터리 신규).
- 판정: 정상. 엔진 200 + 워치독 PID 25504 생존, VM /health 200, 랜딩 200, stars 2/0, dev :3200/:3400 LISTEN.
- 엣지 베이스라인: base-brain total_facts=25,885,995 (integrity 0.9999, grade A).
- [승인 대기 아님 · 관찰] 연속학습 데몬이 guarded_pause(RAM 가드) 상태. worker_alive=false, last_error=ram_available_below_1.5gb. 그러나 실측 ram_free=7.97GB로 여유 존재 — 프로파일 임계 판정과 스냅샷 시점 불일치로 추정. 자동 재개 설계이므로 조치 불요, 내일 스윕에서 재확인. 지속되면 원인 진단 후 보고.
- [정정 필요 · 자동화] 스윕 지시의 학습기 경로 `/learning/continuous/metrics`가 404. 실제 경로 `/api/cloud-brain/learning/continuous/metrics` 및 VM `/health`(루트 아님)를 자동 스윕 스크립트에 반영해야 오탐 방지. 운영자/자동화 정의 갱신 대상.

## 2026-07-09 — 첫 런치 콘텐츠 배치 (atanor-marketing)
- 실측 감사 후 3종 초안 생성 (전부 status: draft, 게시 안 함 — 인간 게이트 준수).
- 근거 확인: 두 리포 README를 `gh api ...readme`로 실제로 읽음(거의 동일, 정직 톤 양호); 라이브 랜딩 HTTP 200; `docs/ARCHITECTURE.md`로 기술 주장 접지. 리포 stars = ATANOR 2 / ATANOR-Demo 0 (ops 스윕과 일치).
- 산출물:
  - `approval_queue/2026-07-09_github_readme-audit.md` — README 감사 + 개선 전문 초안. 격차 6개(라이브 링크·30초 quickstart·데모 GIF·description/topics·두 리포 드리프트·데모 URL 불일치).
  - `approval_queue/2026-07-09_hackernews_show-hn.md` — Show HN 본문 + 첫 댓글 기술 해설 전문 + 예상 Q&A 5개 + 게시 시간.
  - `approval_queue/2026-07-09_x_launch-thread.md` — X 스레드 EN/KO, GIF 필요 지점 표기.
- 정직성 준수: "환각 0%"/"hallucination-free" 0건, 검증 불가 수치 미기재. "quotes its sources / reasoning record / 출처 없는 사실 안 지어냄"으로만. (참고: ops 실측 total_facts=25.9M은 공개 리포에서 검증 불가하므로 공개 문안에는 넣지 않음 — 데모+커밋된 proof 아티팩트로 대체.)
- [승인 대기] 운영자 검토 필요: (1) 3종 초안 승인/수정, (2) **데모 GIF 녹화**(인간 게이트, README·X 공용 자산 1개로 커버), (3) repo description/homepage/topics 설정, (4) 승인 후 게시 순서 = launch_sequence(D-3 README 머지 → D-day Show HN → D+2 X).
- 다음 조치: 운영자가 status를 approved로 바꾸면 dev 에이전트가 README 커밋 초안 준비.

## 2026-07-09 10:05 — atanor-marketing (게시)
- **첫 X 포스트 발행됨** (@ATANOR_AI): https://x.com/ATANOR_AI/status/2075023575057371151
- angle=big-honest-bet(EN), 랜딩 링크 포함, 텍스트-only(이미지 업로드는 chrome MCP 허용목록 제약으로 차단 — 세션 첨부/연결폴더만 허용).
- 운영자 승인("올려") 하에 최종 Post 클릭. 무인 발행 아님.
- [관찰·전략] X가 **graduated access** 안내 표시 = 신규 계정 도달 제한. 계정 워밍업(팔로우·답글·참여) 필요. 바이럴 채널은 계정 숙성 후.
- [미해결] 포스트 이미지 첨부 경로 = 세션 첨부만 허용. 자동 첨부하려면 미디어를 세션 공유 폴더에 두거나 og:image 카드에 의존.

## 2026-07-09 10:00 — atanor-marketing (그로스 배치, 무인 스케줄 실행)
- 무인 스케줄 배치. 게시 없음 — 초안만 생성(인간 게이트 준수).
- 채널 선정: launch_sequence(HN→r/LocalLLaMA→X→LinkedIn→r/MachineLearning) 상 draft 없는 첫 채널 = **r/LocalLLaMA**, 이어서 **LinkedIn**. (기존 큐: hackernews / x / github:readme 존재. X는 10:05 로그상 1건 발행됨 — @ATANOR_AI, 텍스트-only, graduated access 관측.)
- 산출물:
  - `approval_queue/2026-07-09_reddit_localllama.md` — r/LocalLLaMA 게시 본문 + 제목 3안 + 예상 Q&A + 대응 원칙. 앵글 = 로컬 퍼스트/프라이버시 + "no-LLM"이 이 서브에 신선. sLLM 대비 성능 우위가 아니라 트레이드오프로 프레이밍.
  - `approval_queue/2026-07-09_linkedin_founder-note.md` — LinkedIn 파운더 노트 EN/KO(운영자 개인 계정 1인칭). 문제→접근→검증→사전모집 구조, 1인 개발 서사.
- 근거 검증(작성 전 리포 실측):
  - `docs/ARCHITECTURE.md` 실독 — Local Brain/Cloud Brain 프라이버시 벽(원칙 1·2), Current Limitations(그래프 크기가 상한, 산술·창작 약함, 클라우드 proof-scale, 파서 결정론적 v0) 그대로 반영.
  - `apps/landing/assets/mini_atanor.js` 상단 주석 실독 — "GPU 0, server 0 after page load, no LLM ... 결정론적 그래프 조회 ... 방문자 브라우저 탭에서" 확인 → 브라우저 로컬 실동작 주장 접지. (owner-measured 실패 수정본 v3)
  - proof 아티팩트 실재 확인: `data/*/proofs/*`(base_brain/cloud_brain/brain_graph/cortex_g2/answer_quality 등) + `data/graph_hub/catalog/sample_graph_hub_catalog.json`.
- 정직성 준수: "환각 0%"/"hallucination-free"/"N% accurate" 0건. 검증 불가 수치(엣지 수·정확도 %) 미기재 — proof 아티팩트+데모로 유도. GPT/sLLM 비교는 breadth·fluency 차원 인정(트레이드오프)로만. (ops 실측 total_facts=25.9M은 공개 리포 검증 불가하여 공개 문안 미포함, 기존 배치와 동일 정책.)
- [승인 대기] 운영자 검토 필요: (1) 두 초안 승인/수정, (2) LinkedIn용 추론 인증서 캡처 1장(선택, 인간 게이트), (3) 승인 후 게시 순서 = launch_sequence상 r/LocalLLaMA는 HN 사회적 증거 후 + 서브 댓글 참여 선행, LinkedIn은 X 다음.
- 다음 배치(월·목): 5채널 중 미작성 = r/MachineLearning([P] 태그, 재귀 실현기·신뢰 필터 기술 깊이) 1건 남음. 또는 X posted 반응 지표가 metrics/에 기록되면 후속 콘텐츠.

## 2026-07-09 10:30 — 국면: 계정 워밍업 (운영자 결정)
- 전략: 바이럴 푸시 전 **@ATANOR_AI 계정 워밍업**. 신규계정 graduated-access 해제가 선행 조건.
- 방식: atanor-x-viral-cadence 크론(09:00/21:00 KST)이 뱅크에서 다양한 텍스트 포스트를 준비→알림. 발행은 원터치 승인(무인 아님). 며칠간 리듬 유지.
- 미디어(시냅스 영상)는 보류: 브라우저 자동화가 :3400 WebGL 앱에서 렌더 실패 → 운영자 화면녹화 첨부 대기, 또는 @ATANOR_AI를 프로그램 브라우저에 로그인해 단일-브라우저 캡처+게시로 전환.
- 다음 준비 포스트: 오늘 ~21:00 슬롯(EN no-LLM angle, rotation next_index=0).
- 워밍 가속 팁(운영자): 관련 AI/dev 계정 팔로우·답글·좋아요가 graduated-access를 더 빨리 해제. 순수 게시만으론 느림.

## 2026-07-09 10:40 — 국면: HN 준비 (운영자 "알아서" → 준비-먼저 채택)
- 결정: HN/레딧 즉시 발사 대신 **준비-먼저**. HN 목표 = 이번 주 화~목 저녁(KST 21–23시) 정타. 레딧은 HN 후속.
- ✅ repo 메타 세팅(둘 다 PUBLIC): description + homepage(랜딩) + topics(knowledge-graph/explainable-ai/no-llm/local-first/artificial-intelligence/privacy).
- [준비 남음] ①README 개선 푸시(초안=approval_queue/2026-07-09_github_readme-audit.md, 정직성 검증됨) — 공개 브랜드 첫인상이라 운영자 확인 후 푸시 권장. ②데모 GIF(:3400 그래프 화면녹화, 운영자만 가능 — 브라우저 자동화 렌더 실패). ③canonical repo 확정.
- [권고] canonical 공개 리포 = **Cozystone/ATANOR**(이름 깔끔 + 스타 2). ATANOR-Demo는 중복 드리프트 → 정리 대상. HN 링크는 ATANOR 권장.
