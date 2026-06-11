# Homage1.0 Long-Run Stability Plan

## 기준 사양

- CPU: AMD Ryzen 9 9950X3D
- GPU: ZOTAC GAMING GeForce RTX 5080 AMP EXTREME INFINITY 16GB GDDR7
- Memory: Micron DDR5 32GB (16GB x 2)
- Storage: GIGABYTE AORUS Gen4 7300 V2 1TB

## 결론

이 사양은 Alpha 규모의 수백~수천 노드 시각화와 GraphRAG 데모에는 충분하지만,
장시간 학습에서 위험한 병목은 연산량보다 그래프 저장/렌더링/체크포인트 폭증이다.
따라서 Homage는 전체 그래프를 매번 JSON으로 다시 쓰거나 브라우저에 모두 렌더링하지 않는다.

안정 운전의 기준 구조는 다음과 같다.

1. Ontology 원장은 append-only graph event log로 저장한다.
2. 현재 작업 중인 hot graph만 SQLite WAL 인덱스에 둔다.
3. `nodes.json` / `edges.json`은 실시간 원장이 아니라 export snapshot으로만 쓴다.
4. UI는 전체 노드가 아니라 active frontier, anchor, community summary만 LOD로 보여준다.
5. RAM/VRAM/storage watermark가 오면 Harvest와 학습을 즉시 늦추고, RAG는 read-only로 유지한다.

## Runtime Envelope

| 항목 | 운전 기준 |
| --- | --- |
| RAM soft watermark | 23.0GB |
| RAM hard watermark | 27.5GB |
| VRAM soft watermark | 11.8GB |
| VRAM hard watermark | 14.4GB |
| SSD free reserve | 최소 200GB |
| Graph store budget | 약 680GB |
| Checkpoint ring | 80GB, 최근 8개 유지 |

Soft watermark는 자동 backpressure가 시작되는 지점이다. Hard watermark는 작업을 멈추고
flush/compact/checkpoint rotation을 먼저 해야 하는 지점으로 본다.

## Queue Policy

| 큐 | 제한 |
| --- | --- |
| Harvest pending | 512~4096개 사이에서 target node 수에 따라 제한 |
| DataGate batch | 64 docs |
| Ontology delta chunk | 256 chunks |
| Node write batch | 500 nodes |
| Edge write batch | 2000 edges |
| RAG query concurrency | 2 |
| Training | bf16/8-bit, gradient accumulation, activation checkpointing, full corpus VRAM 적재 금지 |

Harvest가 빠르게 자료를 모아도 Ontology Forge writer가 밀리면 새 관계 생성을 멈추고,
이미 존재하는 노드 병합만 수행한다. 이렇게 해야 그래프 생성 속도가 저장 계층을 압도하지 않는다.

## Graph Storage Model

장시간 운전에서 Ontology Forge는 다음 계층으로 나뉜다.

- Event log: `node_seen`, `edge_seen`, `evidence_attached`, `node_merged`, `edge_reweighted`
  같은 append-only 이벤트.
- Hot index: SQLite WAL. 최근 활성 노드, edge key, evidence count, confidence, last_seen_at.
- Snapshot: 주기적으로 compact한 `nodes.json`, `edges.json`, graph summary export.
- Cold evidence: 원문 chunk와 provenance는 별도 chunk store에 보관하고, graph edge는 reference만 가진다.

Edge는 중복 row를 계속 늘리지 않고 `(source_id, target_id, relation_type)`를 key로 사용한다.
새 근거가 들어오면 `evidence_count`, `confidence`, `last_seen_at`을 갱신한다.

## UI LOD Policy

수천 노드가 생겨도 브라우저는 전체 그래프를 렌더링하지 않는다.

- Hot window: 기본 2,048 nodes / 12,000 edges, max 24,000 nodes / 240,000 edges
- UI render budget: 240~2,000 nodes
- 렌더링 대상: 질문/학습 frontier, 고신뢰 anchor, 커뮤니티 summary, 사용자가 선택한 주변 이웃
- 이동/확대/축소는 카메라 상태를 유지하고, 새 노드가 들어와도 scene reset을 하지 않는다.
- 전체 탐색은 search-first로 처리하고, 상세 확장은 선택한 subgraph만 가져온다.

## Checkpoint And Resume

- Run state: 5분마다 저장
- Ontology snapshot: 20분마다 저장
- Training checkpoint: 15분마다 저장
- Keep last: 8개
- Resume key: `run_id`, `document_id`, `chunk_id`, `node_id`, `edge_key`

모든 단계는 idempotent해야 한다. 같은 chunk를 다시 처리해도 같은 node/edge key로 합쳐져야 하며,
중단 후 재개해도 관계가 두 배로 불어나면 안 된다.

## Backpressure Rules

| 조건 | 조치 |
| --- | --- |
| RAM >= soft watermark | Harvest 일시정지, ontology batch flush, hot graph compact, RAG read-only |
| VRAM >= soft watermark | Homage Oven batch 일시정지, microbatch 축소, DataGate/Ontology는 CPU 유지 |
| Graph writer lag > 2 batches | 새 relation 생성 중지, known node merge만 수행 |
| Storage free <= reserve | Harvest 중지, checkpoint rotation, graph compaction, operator review 필요 |

## Current Alpha 적용 상태

- `/api/neuro/stability`가 위 정책을 계산한다.
- BakeBoard 학습 과정에 `지속 운전 안전장치` 단계가 추가된다.
- UI에서 학습량 preset에 따라 target nodes/edges/duration을 다시 계산한다.
- Alpha의 `nodes.json` / `edges.json` 경로는 아직 snapshot 중심이다. 다음 단계에서 live source를
  SQLite WAL + event log로 승격해야 한다.

## 다음 구현 단계

1. `ontology_events` append-only log와 SQLite WAL hot index 추가.
2. Ontology Forge writer를 batch writer로 분리하고 writer lag metric 추가.
3. Build Start graph frames를 event replay 기반으로 변경.
4. RAG retriever가 전체 graph JSON 대신 hot index + sampled context bundle을 읽도록 변경.
5. UI graph API를 pagination/subgraph endpoint로 분리.
6. checkpoint rotation과 resume contract를 실제 run directory에 저장.
