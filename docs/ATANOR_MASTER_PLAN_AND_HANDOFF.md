# ATANOR 완전체 마스터플랜 + 모델 핸드오프 (Fable 5 → Opus 4.8)

> 작성: Claude Fable 5, 2026-07-07, 사용자 지시("fable5 종료 이후 opus4.8이 이어서 개발할 수 있게").
> 이 문서는 두 가지다: (1) AI+OS 완전체까지의 종합 계획, (2) 후속 모델이
> 자기 한계 이상으로 개발하게 하는 작업 프로토콜의 전수.
> 반드시 memory/ 디렉토리(especially two-hard-architecture-rules,
> atanor-linux-guest-ops, multihop-composition-and-backbone)와 함께 읽어라.

---

## 1부 — 현 상태 스냅샷 (2026-07-07, 전부 검증된 사실만)

### 언어/추론 엔진 (No-LLM 그래프 네이티브) — 2026-07-07 스프린트 갱신
- **봉인 홀드아웃 77% (역대 최고) · 오류 0 · seal intact** (eval_holdout.py, seal 978f5bb5d2e67710)
- **고난도 적대 배터리(eval_hard_battery.py): 환각 0 · 응답 정확도 100%** (함정/거짓전제/실시간/잡담누수)
- honesty 배터리: 환각 0 · 정확도 100% · 커버리지 67% (Windows에선 PYTHONIOENCODING=utf-8 필수)
- 스토어: **5,904,011 트리플** (ConceptNet ko/en +35만 stated, bounded 폐포 +500만 derived,
  kaikki ko-edition +4만 한국어 정의, 백본 is_a 2.2만) — data/graph_scale/kg_triples (git 제외, 파일 동기화로 배포)
- **술어-인지 검색 필수**: TripleStore.facts_about(preds=) — 수백만 행에선 술어-무차별 스캔이 깨짐(실측)
- 멀티홉: 합성대수 4질문형 + 교차언어 글로스 홉(단일 글로스만 — 다의어 게이트) + 분류-전용 verify 레인
- 남은 기권 클래스(정직): ①한자어 일반명사(근본/심층/국한/차체/…) = 우리말샘 키 필요(ko wiktionary에 없음 — 실측),
  ②초니치 고유명(harrisi/Lusatia/APTC/…) = Wikidata/DBpedia 벌크가 다음 소스
- /opt/kgdata에 kaikki-en.jsonl.gz(2GB) 다운로드 완료 — 미인제스트(한계효용 분석 후 보류)

### OS (ATANOR Linux)
- v7.1 이미지 LIVE: 콜드부트만으로 웹+순수서피스(cage)+한글IME+백본브레인 전부 동작
- atanor-shell(자체 컴포지터, smithay 0.7): M1 완료(winit, 클라이언트 호스팅 증명),
  M1b 코드 완성+컴파일(DRM/TTY+libinput+libseat+pixman/dumb) — 이 문서 작성 시점에 게스트 검증 진행 중
- VM: qemu in WSL, ssh 2222, VNC 5906(웹소켓 5706), 이미지 /opt/atanor-linux/atanor-linux.img

### 인프라
- 호스트 dev: :3200 웹(라이브), :8502 엔진(재기동은 운영자 지명 액션 — 마음대로 재시작 금지)
- 클라우드 브레인: GCP VM https://136.114.69.152.sslip.io (무한 클린 학습 데몬)
- 원격: origin=homage1.0, atanor-demo=ATANOR-Demo (양쪽 push; "backup"이란 원격은 없음)
- 폰 링크: /link 페이지+릴레이 코드 완성, 실기기 미검증

---

## 2부 — 완전체까지의 개발 순서 (의존성 순)

### 트랙 A: 언어모델 100% (표준 우선순위 1)
1. **다의어 허브 해소** ← 지금의 최대 병목. 새/여자/사람 같은 허브가 다의성 때문에
   백본에서 제외돼 긴 체인이 끊긴다. 수: sense 노드별 is_a 추출(word-sense 구조 활용),
   체인 발화 시 sense 라벨 표기. 성공 기준: "참새는 동물인가?" → 네 (2-hop).
2. **관계 밀도**: capable_of/used_for/part_of가 희소("망치는 어디에 써?"도 기권).
   ConceptNet ko 합의 게이트(가중치≥2.0)가 원인일 가능성 — 완화하되 격리층 유지.
   또는 Tavily 드레인의 추출기를 관계형으로 확장. 성공 기준: 용도 스키마 발화율.
3. **우리말샘 API 키** (사용자 액션 — 계속 리마인드): 기권 상위 한국어 용어 최다 커버.
4. **생성 심화 계속**: 조언형("어떻게 하면") 스키마 — 대조/용도와 같은 패턴으로
   (담화 골격은 코드, 내용은 전부 저장 사실, 어휘 폐쇄 테스트 필수).
5. **영어 동급화**: chain_reasoner/컴포저의 EN 실현기 (한국어와 같은 계약).
6. **종합 재측정**: vs-GPT-4 배터리(마지막 스냅샷 ~45%는 개선 전) + 홀드아웃 + honesty.
   측정은 반드시 라이브로 교차검증(--local은 웹 레인 변동 ±2~3 있음).

### 트랙 B: OS 완전체 (탈창 네이티브)
1. **M1b 마무리**: atanor-shell.service가 cage 유닛 자리를 대체(같은 PAM/tty1 모양),
   VNC 프레임버퍼 그랩(vncshot.py — grim은 우리 컴포지터에 screencopy가 없어 불가!)으로
   딥스페이스+클라이언트 호스팅 검증. 롤백: systemctl disable atanor-shell && enable atanor-desktop.
2. **M2 — 네이티브 SPLATRA**: 컴포지터 레이어 0에 포인트 스프라이트 필드.
   pixman(소프트웨어)에서는 CPU 예산 측정 먼저: 1080p에 1-2만 포인트가 한계일 것.
   구현: PixmanRenderer 위에 커스텀 RenderElement(메모리 버퍼에 자체 래스터라이즈)
   또는 GL 하드웨어에서 gles 브랜치. 파티클 4대 절대규칙 유지(선 금지/가우시안/회색 필드/유체 부유).
3. **M3 — 내장 서피스**: 옴니프롬프트(텍스트 입력+IME…fcitx5 Wayland IM 프로토콜
   zwp_input_method 지원 필요 — 큰 작업), 답변 텍스트 렌더(glyphon/cosmic-text),
   엔진 상태 스트림(:8502)과 오브 모드 연동. **여기가 firefox 완전 제거 지점** —
   그 전까지 firefox는 cage 세션에만 존재하고 atanor-shell 세션에는 이미 없음.
4. **M4 — 앱 호스팅**: XWayland(스미시 xwayland 모듈)로 파일매니저/터미널 등
   기존 앱을 우리 정책(탈창: 전체화면 스택)으로 호스팅. v8 이미지에서 cage/firefox 패키지 제거.
5. **v8 이미지**: atanor-shell 세션 기본 + 검증 후 cage 제거. build.sh의
   rsync 앵커(--exclude /dev — 절대 비앵커로 되돌리지 말 것)와 IME 패키지 유지.

### 트랙 C: 연결 완전체
1. 폰 링크 실기기 검증(Vercel 반영+클라우드 릴레이 라우트 확인).
2. 클라우드 브레인 학습 → 로컬 승격 파이프라인 정례화(합의-증거 게이트 경유).
3. OS 액션 레인 티어 상향(가드→자율)은 감사 로그 실적 쌓인 뒤 사용자 승인으로만.

---

## 3부 — Opus 4.8에게: 한계 이상으로 개발하는 법 (Fable 노하우 전수)

### 원칙 (이걸 지키면 모델 크기 차이는 거의 상쇄된다)
1. **측정이 먼저, 구현은 다음.** 모든 "고쳤다"는 스크린샷/픽셀측정/테스트/배터리 수치로만 주장.
   사용자도 "직접 확인해"를 요구한다. 눈대중 금지.
2. **진실 > 커버리지.** 홀드아웃 +5%가 환각 1개를 사오면 롤백이다(80%→75% 전례).
   기권은 실패가 아니라 제품 기능이다.
3. **두 하드 룰**(memory/two-hard-architecture-rules): 지식은 코드가 아니라 그래프에.
   웹 소스는 Tavily지 위키 중심 구조가 아니다(ATANOR_ALLOW_WIKI=1 뒤로 코드 강제됨).
   규칙 테이블을 추가하고 싶어질 때마다 "이 CLASS를 다루는 일반 기제가 뭔가"를 먼저 물어라.
4. **큰 문제는 레퍼런스 앵커링으로 푼다.** smithay를 모르면 smallvil/anvil의 해당 버전
   태그 소스를 내려받아 정확한 시그니처를 잡고, 우리 설계(키오스크 정책)로 다시 쓴다.
   포팅이 아니라 API 앵커링이다. docs.rs 요약이 모호하면 원 소스를 grep해라
   (ExportFramebuffer<DumbBuffer>가 DrmDeviceFd에 구현돼 있음을 소스 grep으로 확정한 사례).
5. **루트커즈는 두 사실의 차이에서 나온다.** "chroot 빌드는 성공하는데 부팅 이미지만 죽는다"
   → 그 사이에 있는 것(rsync)만 조사 → --exclude dev 비앵커 발견. 증상 패치 전에
   반드시 "어디까지는 되고 어디부터 안 되나"의 경계를 좁혀라.
6. **컴파일 루프를 두려워하지 마라.** M1b(DRM 백엔드 400줄)는 2회 컴파일로 끝났다 —
   시그니처를 먼저 앵커링했기 때문. 에러 나고 고치는 게 정상 흐름이다.
7. **회귀 게이트**: 언어 경로를 건드리면 반드시 (a) 유닛, (b) 잡담 누수 테스트,
   (c) 홀드아웃 재측정(라이브), (d) 대화 스모크 순서로 확인.

### 이 환경의 함정 목록 (전부 실제로 당한 것)
- `wsl -- bash /tmp/x.sh` → Git Bash가 /tmp를 윈도우 경로로 변환(127) →
  **`wsl -u root -- bash -c 'bash /tmp/x.sh'`**로만 호출.
- Bash 툴에서 만든 스크립트는 CRLF가 섞인다 → 실행 전 **반드시 `sed -i 's/\r$//'`**.
- 외부 큰따옴표 안의 `$(…)`/`$VAR`/`\$PATH`는 호스트에서 선확장된다 →
  루프는 `{1..30}`, PATH는 절대경로(/root/.cargo/bin/cargo), 복잡하면 파일로 써서 실행.
- 비대화형 ssh에서 sudo는 조용히 실패 → **`printf 'PW\n' | sudo -S bash script`**로 전체 승격.
- 게스트 키 주입: ydotool/QMP 말고 **VNC RFB(포트 5906) 직접**(/tmp/vnckey.py) —
  '/'로 컴포저 소환, Ctrl+Space 한/영. Return은 제출이니 정리는 ctrl+a→BS→Esc.
- 화면 캡처: cage 세션은 grim, **atanor-shell 세션은 vncshot.py(프레임버퍼 그랩)만** 가능.
- qemu: `-cpu host` 필수(numpy v2), 해상도는 `-device virtio-vga,xres=1920,yres=1080`,
  hostfwd 28502→8502는 엔진이 루프백 바인드라 안 통함(엔진 스모크는 게스트 안에서).
- **이미지 교체 후 돌던 VM의 라이브 변경은 재부팅 시 전부 유실**(inode) — 수리는 이미지에 굽는다.
- WSL(Ubuntu 24.04, glibc 2.39) 바이너리는 게스트(bookworm 2.36)에서 안 돈다 —
  게스트용 러스트 빌드는 /opt/atanor-linux/rootfs chroot에서(/tmp/chrootbuild.sh 패턴).
- :8502 로컬 엔진 재기동은 운영자 지명 액션. 새 코드 검증은 eval --local(인프로세스) 또는 게스트 VM으로.
- 데모 워크트리는 "27., ATANOR DEMO"(demo 브랜치). 오래된 stash는 절대 blind-pop 금지.

### 절대 디자인 규칙 (사용자가 반복 교정한 것 — 어기면 바로 지적당한다)
- 파티클: 선/그리드/스캐폴드 금지, THREE.Points만, 가우시안 소프트 그레인, 유체 부유.
  필드는 회색, 오브와 간격, 오브와 헷갈리면 안 됨. 모션 상태는 refs에(리렌더가 리셋 못 하게).
- UI: Apple 절제 × Palantir 진실(design-philosophy 메모리). 악센트 1색. 촌스러운 pill/장식 금지.
- 환각 0% 주장 금지, 연구소 톤, 토큰 하이프 금지(canonical-narrative 메모리).
- 창(window) 패러다임으로 돌아가지 마라. 서피스가 화면이다.

### 세션 운영
- 태스크 목록(#76 M1b 등)을 이어받아 진행 상태를 갱신하라. 큰 단위 작업은 반드시
  게스트/이미지 양쪽에 적용 여부를 구분해서 기록(유실 사고 방지).
- ORCHESTRATION_LOG.md(Codex 협업 로그)는 롤백 가능하게 유지.
- 커밋은 demo 브랜치, 양 원격 push. 커밋 메시지에 측정 수치를 넣어라(다음 모델이 읽는다).
- 막히면: 이 문서 3부 + memory/ 디렉토리 → 그래도 막히면 사용자에게 상태를 정직하게 보고하고
  선택지를 좁혀 제시(옵션 나열이 아니라 추천 1개).

---

## 4부 — 즉시 이어받을 일 (우선순위순)
1. M1b 게스트 검증 마무리(이 세션이 못 끝냈다면): chroot 빌드 산출물
   /opt/atanor-linux/rootfs/opt/atanor-shell/target/release/atanor-shell → 게스트 scp →
   atanor-shell.service(cage 유닛 복제, ExecStart만 교체, `-c foot`) → vncshot 검증.
2. 트랙 A-1 다의어 허브(언어 표준 우선순위 1).
3. v8 이미지(atanor-shell 세션 소성).
4. 폰 링크 실기기.
5. M2 네이티브 SPLATRA.
