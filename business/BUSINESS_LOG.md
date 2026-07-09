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
