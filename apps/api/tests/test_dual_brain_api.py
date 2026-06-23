from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from app.routers import dual_brain
from packages.voice_loop.local_tts import LocalTTSResult, local_voice_audio_dir


def _fake_voice_synthesis(text: str, *, language: str = "ko") -> LocalTTSResult:
    root = local_voice_audio_dir()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "atanor_voice_22222222222222222222222222222222.wav"
    path.write_bytes(b"RIFF$\x00\x00\x00WAVEfmt ")
    return LocalTTSResult(engine="windows_sapi", audio_path=path, audio_url=f"/api/voice-loop/audio/{path.name}")


def test_dual_brain_ingest_links_semantic_and_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    response = client.post(
        "/api/dual-brain/ingest",
        json={"text": "쉽게 말하면, 쿠버네티스는 많은 컨테이너를 자동으로 배치하고 관리하는 운영 관리자에 가깝습니다."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["semantic_projection"]["source_hash"] == payload["surface_projection"]["source_hash"]
    assert payload["stored_raw_text"] is False
    assert payload["external_llm_used"] is False


def test_chat_uses_base_brain_when_rag_has_concepts_without_grounding(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fake_query_graphrag(*args, **kwargs):
        return {
            "result": {
                "active_concepts": ["Kubernetes"],
                "matched_nodes": [{"label": "Kubernetes"}],
                "matched_edges": [],
                "evidence_docs": [],
                "confidence": 0.1,
                "retrieval_trace": {},
            }
        }

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fake_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "쿠버네티스가 뭐야?", "language": "ko", "brain_mode": "local", "include_trace": True},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert "쿠버네티스" in payload["answer"]
    assert "컨테이너" in payload["answer"]
    assert "Cloud Brain" not in payload["answer"]
    assert "source_hash" not in payload["answer"]
    assert payload["compact_trace"]["local_coverage"] == "base_brain"
    assert payload["external_llm_used"] is False
    assert payload["external_sllm_used"] is False
    assert payload["local_brain_write"] is False


def test_chat_accepts_query_alias_and_blocks_internal_leakage(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fake_query_graphrag(*args, **kwargs):
        return {
            "result": {
                "active_concepts": ["GraphRAG"],
                "matched_nodes": [{"label": "GraphRAG"}],
                "matched_edges": [
                    {
                        "source_hash": "87eba76e7f3164534045ba922e7770fb58bbd14ad732bbf5ba6f11cc56989e6e",
                        "relation": "relates_to",
                        "target_hash": "084943ae838283848e9e4b5e0c66b0743414d7198b2bfa8f47a5f88db823f969",
                    }
                ],
                "evidence_docs": [{"source_hash": "abcdef1234567890abcdef1234567890", "snippet": ""}],
                "confidence": 0.2,
                "retrieval_trace": {},
            }
        }

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fake_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"query": "GraphRAG가 근거 문서를 어떻게 사용해서 답변을 검증하나요?", "language": "ko"},
    )

    assert response.status_code == 200
    answer = response.json()["result"]["answer"]
    assert "GraphRAG" in answer
    assert "근거" in answer
    assert "source_hash" not in answer


def test_chat_default_path_attaches_hidden_three_core_trace(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fake_query_graphrag(*args, **kwargs):
        return {
            "result": {
                "active_concepts": ["Kubernetes", "containers"],
                "matched_nodes": [{"label": "Kubernetes"}, {"label": "containers"}],
                "matched_edges": [{"source": "Kubernetes", "relation": "manages", "target": "containers", "confidence": 0.8}],
                "evidence_docs": [{"title": "seed", "snippet": "Kubernetes manages containers."}],
                "confidence": 0.7,
                "retrieval_trace": {},
            }
        }

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fake_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "Explain Kubernetes in simple English.", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    answer = payload["answer"]
    assert payload["trace"] is None
    assert payload["default_trace_visible"] is False
    assert payload["compact_trace"]["three_core"]["used"] is True
    assert payload["compact_trace"]["three_core"]["sqc"]["used"] is True
    assert payload["compact_trace"]["three_core"]["fractal_seed_rail"]["used"] is True
    assert payload["compact_trace"]["three_core"]["holographic_wave"]["used"] is True
    assert payload["answer_engine"]["three_core_trace_attached"] is True
    assert payload["answer_engine"]["three_core_answer_source"] == "hidden_trace_only"
    assert "SQC" not in answer
    assert "Fractal" not in answer
    assert "Wave" not in answer
    assert "Q-Cortex" not in answer
    assert "Local Brain" not in answer
    assert "Cloud Brain" not in answer
    assert "source_hash" not in answer
    assert payload["external_llm_used"] is False
    assert payload["external_sllm_used"] is False
    assert payload["local_brain_write"] is False


def test_chat_conversation_uses_readonly_verified_store_for_grounded_visual_scene(tmp_path, monkeypatch) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": "Gravity is a force of attraction between masses. Isaac Newton formulated the law of universal gravitation.",
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "Gravity"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ATANOR_VERIFIED_STORE_PATH", str(tmp_path))
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={
            "question": "What is the law of gravity?",
            "language": "en",
            "mode": "conversation",
            "brain_mode": "conversation",
            "include_trace": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    scene = payload["scene_choreography"]
    assert payload["route_type"] == "general_knowledge_question"
    assert payload["compact_trace"]["semantic_grounding"]["grounding_source"] == "verified_store_v0_readonly"
    assert "Isaac Newton" in payload["answer"]
    assert scene["stage_layout"] == "scene_focus"
    assert scene["topic_scene_templates"] is False
    assert any("Isaac Newton" in beat["prompt"] for beat in scene["beats"])
    assert all("apple" not in beat["prompt"].casefold() for beat in scene["beats"])
    assert all("apple" not in item["text"].casefold() for item in scene["speech_timeline"])
    assert all(item.get("particle_behavior") != "gravity_arc" for item in scene["speech_timeline"])
    assert payload["external_llm_used"] is False
    assert payload["external_sllm_used"] is False
    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False


def test_dashboard_conversation_returns_verified_speech_timeline_for_motion_scene(tmp_path, monkeypatch) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": (
                    "Gravity is associated with Isaac Newton. "
                    "Isaac Newton sat under an apple tree. "
                    "An apple fell from the tree toward Newton, and the event helped explain gravitational attraction."
                ),
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "Newton apple tree"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ATANOR_VERIFIED_STORE_PATH", str(tmp_path))

    async def fail_query_graphrag(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("dashboard conversation mode must not enter graph retrieval")

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fail_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={
            "question": "What is gravity?",
            "language": "en",
            "mode": "conversation",
            "brain_mode": "conversation",
            "include_trace": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    scene = payload["splatra_scene_plan"]
    assert scene == payload["scene_choreography"] == payload["visual_scene_plan"]
    assert scene["stage_layout"] == "scene_focus"
    assert scene["layout_intent"] == "wide_particle_stage"
    assert scene["dashboard_layout"]["agent_layout_decision"]["decision_basis"] == "verified_scene_geometry"
    assert scene["dashboard_layout"]["agent_layout_decision"]["text_rendering"] == "dom_text_not_particles"
    assert scene["dashboard_layout"]["orb"]["anchor"] == "lower_right"
    assert scene["topic_scene_templates"] is False
    assert scene["speech_timeline"]
    assert all(item["text_source"] == "verified_beat_narration" for item in scene["speech_timeline"])
    assert all(item["speech_cue_basis"] == "verified_evidence_unit" for item in scene["speech_timeline"])
    assert any(item["particle_behavior"] == "gravity_arc" for item in scene["speech_timeline"])
    gravity_item = next(item for item in scene["speech_timeline"] if item["particle_behavior"] == "gravity_arc")
    assert gravity_item["physics_hint"]["field"] == "downward_attraction"
    assert gravity_item["motion_path"]["basis"] == "verified_motion_phrase"
    assert "apple" in gravity_item["text"].casefold()
    assert payload["answer_engine"]["external_llm"] is False
    assert payload["answer_engine"]["external_sllm"] is False
    assert payload["answer_engine"]["rule_based_answer_used"] is False
    assert payload["local_brain_write"] is False
    assert payload["production_store_mutated"] is False


def test_verified_store_runtime_discovers_sibling_primary_store(tmp_path, monkeypatch) -> None:
    isolated = tmp_path / "ATANOR-live-selfhood-scheduler"
    sibling = tmp_path / "24.Homage1.0" / "data" / "cloud_brain" / "verified_store_v0"
    isolated.mkdir()
    sibling.mkdir(parents=True)
    (sibling / "evidence.jsonl").write_text("", encoding="utf-8")

    monkeypatch.delenv("ATANOR_VERIFIED_STORE_PATH", raising=False)
    monkeypatch.setattr(dual_brain, "PROJECT_ROOT", isolated)

    runtime = dual_brain._verified_store_runtime()

    assert runtime == {"verified_store_path": str(sibling)}


def test_chat_trace_mode_exposes_compact_three_core_summary(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fake_query_graphrag(*args, **kwargs):
        return {
            "result": {
                "active_concepts": ["ATANOR", "symbolic reasoning"],
                "matched_nodes": [{"label": "ATANOR"}, {"label": "symbolic reasoning"}],
                "matched_edges": [{"source": "ATANOR", "relation": "uses", "target": "symbolic reasoning", "confidence": 0.75}],
                "evidence_docs": [{"title": "seed", "snippet": "ATANOR uses symbolic reasoning."}],
                "confidence": 0.7,
                "retrieval_trace": {},
            }
        }

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fake_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "Explain ATANOR as one sentence.", "language": "en", "mode": "trace"},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert isinstance(payload["trace"], dict)
    assert payload["trace"]["three_core"]["used"] is True
    assert payload["trace"]["three_core"]["honesty"]["external_llm_used"] is False
    assert payload["trace"]["three_core"]["honesty"]["external_sllm_used"] is False
    assert payload["trace"]["three_core"]["honesty"]["local_brain_write"] is False
    assert "source_hash" not in payload["answer"]


def test_local_graph_status_questions_do_not_fall_through_to_base_brain(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_base_brain(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("status questions must not call Base Brain fallback")

    monkeypatch.setattr(dual_brain, "answer_with_base_brain", fail_base_brain)
    client = TestClient(app)

    for question in (
        "내 로컬 메모리 총 노드 수",
        "내 로컬 메모리 총 연결선 수",
        "내 로컬 메모리 총 엣지 수",
        "내 개인 메모리 관계 수 알려줘",
        "화면에 표시 중인 로컬 그래프 노드 수",
        "렌더링된 연결선 수",
        "기본 시드 앵커까지 포함하면 몇 개야?",
    ):
        response = client.post(
            "/api/chat/atanor",
            json={"question": question, "language": "ko", "brain_mode": "local", "include_trace": True},
        )
        assert response.status_code == 200
        payload = response.json()["result"]
        assert "RAM" not in payload["answer"]
        assert "SSD" not in payload["answer"]
        assert "연결선" in payload["answer"] or "논리 노드" in payload["answer"]
        assert payload["compact_trace"]["local_coverage"] == "status_question"
        assert payload["compact_trace"]["graph_status"]["selected_scope"] == "local"
        assert "personal_local_memory_count" in payload["compact_trace"]["graph_status"]
        assert "local_viewport_materialized_count" in payload["compact_trace"]["graph_status"]
        assert "seed_anchor_count" in payload["compact_trace"]["graph_status"]
        assert payload["external_llm_used"] is False
        assert payload["external_sllm_used"] is False
        assert payload["local_brain_write"] is False


def test_cloud_graph_status_question_uses_status_router(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_base_brain(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("status questions must not call Base Brain fallback")

    monkeypatch.setattr(dual_brain, "answer_with_base_brain", fail_base_brain)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "cloud graph relation count", "language": "en", "brain_mode": "cloud", "include_trace": True},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert "relations" in payload["answer"]
    assert payload["compact_trace"]["local_coverage"] == "status_question"
    assert payload["compact_trace"]["graph_status"]["selected_scope"] == "cloud"
    assert payload["external_llm_used"] is False
    assert payload["external_sllm_used"] is False


def test_cloud_status_read_failure_does_not_use_general_knowledge(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_status(self):
        raise RuntimeError("status unavailable")

    def fail_base_brain(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("status read failure must not call Base Brain fallback")

    monkeypatch.setattr(dual_brain.SemanticCloudStore, "status", fail_status)
    monkeypatch.setattr(dual_brain, "answer_with_base_brain", fail_base_brain)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "클라우드 브레인 관계 수", "language": "ko", "brain_mode": "cloud", "include_trace": True},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert "상태를 읽을 수 없습니다" in payload["answer"]
    assert "RAM" not in payload["answer"]
    assert payload["compact_trace"]["graph_status"]["status_unavailable"] is True
    assert payload["external_llm_used"] is False
    assert payload["external_sllm_used"] is False


def test_computer_memory_questions_still_use_base_brain(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)

    ram_response = client.post(
        "/api/chat/atanor",
        json={"question": "RAM은 뭐야?", "language": "ko", "brain_mode": "local", "include_trace": True},
    )
    assert ram_response.status_code == 200
    ram_payload = ram_response.json()["result"]
    assert "RAM" in ram_payload["answer"]
    assert ram_payload["compact_trace"]["local_coverage"] == "base_brain"
    assert ram_payload["external_llm_used"] is False
    assert ram_payload["external_sllm_used"] is False
    assert ram_payload["local_brain_write"] is False

    comparison_response = client.post(
        "/api/chat/atanor",
        json={"question": "컴퓨터 메모리와 SSD 차이", "language": "ko", "brain_mode": "local", "include_trace": True},
    )
    assert comparison_response.status_code == 200
    comparison_payload = comparison_response.json()["result"]
    assert "RAM" in comparison_payload["answer"]
    assert "SSD" in comparison_payload["answer"]
    assert comparison_payload["compact_trace"]["local_coverage"] == "base_brain"


def test_live_selfhood_greeting_uses_native_conversation_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fail_query_graphrag(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("short live conversation must not enter graph retrieval")

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fail_query_graphrag)
    monkeypatch.setattr(dual_brain, "synthesize_windows_sapi", _fake_voice_synthesis)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "안녕", "language": "ko", "brain_mode": "unified", "include_trace": True},
    )

    assert response.status_code == 200
    body = response.json()
    payload = body["result"]
    assert body["state"] == "completed"
    assert payload["answer"]
    assert "먼저 의도와 경계" not in payload["answer"]
    assert "내부적으로 점검" not in payload["answer"]
    assert payload["answer_kind"] == "asm_v0_conversation_surface"
    assert payload["speech_act"] == "greeting"
    assert payload["can_speak"] is True
    assert payload["final_answer_generation_claimed"] is True
    assert payload["compact_trace"]["local_coverage"] == "live_selfhood_conversation"
    assert payload["compact_trace"]["selfhood_loop"]["internal_scratchpad_visible"] is False
    assert payload["compact_trace"]["selfhood_loop"]["rule_based_answer_blocked"] is True
    assert payload["compact_trace"]["selfhood_loop"]["requires_learned_generator"] is False
    assert payload["compact_trace"]["surface_graph"]["conversation_surface"]["generation_basis"] == "local_corpus_construction_transition_model"
    assert payload["answer_engine"]["rule_based_answer_used"] is False
    assert payload["answer_engine"]["template_free_surface"] is True
    assert payload["answer_engine"]["external_llm"] is False
    assert payload["answer_engine"]["external_sllm"] is False
    assert payload["answer_engine"]["production_store_mutated"] is False
    assert payload["answer_engine"]["candidate_promotion"] is False
    assert payload["answer_engine"]["internal_trace_exposed"] is False
    assert payload["voice_output"]["requested"] is True
    assert payload["voice_output"]["enabled"] is True
    assert payload["voice_output"]["selected_engine"] in {"fallback", "fish_2", "fish_1_5"}
    assert payload["voice_output"]["tts_engine"] == "windows_sapi"
    assert payload["voice_output"]["audio_available"] is True
    assert payload["voice_output"]["audio_url"] == "/api/voice-loop/audio/atanor_voice_22222222222222222222222222222222.wav"
    assert payload["voice_output"]["error_reason"] is None
    assert payload["voice_output"]["text_fallback"] is True
    assert payload["voice_output"]["microphone_enabled"] is False
    assert payload["voice_output"]["always_listening_enabled"] is False
    assert payload["voice_output"]["raw_voice_saved"] is False
    assert payload["voice_output"]["external_service"] is False
    assert payload["voice_output"]["generated_audio_persisted"] is False
    assert payload["local_brain_write"] is False
    audio_response = client.get(payload["voice_output"]["audio_url"])
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/wav")


def test_dashboard_conversation_mode_forces_asm_v0_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fail_query_graphrag(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("dashboard conversation mode must not enter graph retrieval")

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fail_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={
            "question": "뭐 하고 있어?",
            "language": "ko",
            "brain_mode": "conversation",
            "mode": "conversation",
            "include_trace": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["answer"]
    assert payload["answer_kind"] == "asm_v0_conversation_surface"
    assert payload["answer_engine"]["generation_basis"] == "local_corpus_construction_transition_model"
    assert payload["answer_engine"]["external_llm"] is False
    assert payload["answer_engine"]["external_sllm"] is False
    assert payload["answer_engine"]["rule_based_answer_used"] is False
    assert payload["answer_engine"]["template_free_surface"] is True
    assert payload["answer_engine"]["internal_trace_exposed"] is False
    assert payload["local_brain_write"] is False


def test_dashboard_conversation_can_return_splatra_scene_choreography_without_templates(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fail_query_graphrag(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("dashboard conversation mode must not enter graph retrieval")

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fail_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={
            "question": "Use SPLATRA to visualize this",
            "language": "en",
            "brain_mode": "conversation",
            "mode": "conversation",
            "include_trace": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["answer_kind"] == "asm_v0_conversation_surface"
    assert payload["scene_choreography"]["stage_layout"] == "scene_focus"
    assert payload["scene_choreography"]["orb_anchor"] == "lower_right"
    assert payload["scene_choreography"]["topic_scene_templates"] is False
    assert payload["visual_scene_plan"] == payload["scene_choreography"]
    assert payload["compact_trace"]["visual_imagination"]["topic_scene_templates"] is False
    assert payload["answer_engine"]["external_llm"] is False
    assert payload["answer_engine"]["external_sllm"] is False
    assert payload["answer_engine"]["rule_based_answer_used"] is False
    assert payload["local_brain_write"] is False


def test_korean_dashboard_conversation_returns_splatra_scene_plan_from_verified_store(tmp_path, monkeypatch) -> None:
    (tmp_path / "evidence.jsonl").write_text(
        json.dumps(
            {
                "text": "아이작 뉴턴은 중력 법칙과 관련해 사과가 나무에서 떨어지는 장면을 관찰했다. 그 사건은 물체가 지구 쪽으로 끌리는 현상을 설명하는 단서가 되었다.",
                "verification": {"status": "verified"},
                "provenance": {"source_name": "licensed_fixture", "title": "뉴턴과 중력"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ATANOR_VERIFIED_STORE_PATH", str(tmp_path))

    async def fail_query_graphrag(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("dashboard conversation mode must not enter graph retrieval")

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fail_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={
            "question": "중력의 법칙에 대해 설명해줘",
            "language": "ko",
            "brain_mode": "conversation",
            "mode": "conversation",
            "include_trace": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    scene = payload["splatra_scene_plan"]
    assert payload["route_type"] == "general_knowledge_question"
    assert payload["compact_trace"]["semantic_grounding"]["grounding_source"] == "verified_store_v0_readonly"
    assert payload["answer"]
    assert "아이작 뉴턴" in payload["answer"]
    assert scene == payload["scene_choreography"] == payload["visual_scene_plan"]
    assert scene["stage_layout"] == "scene_focus"
    assert scene["orb_anchor"] == "lower_right"
    assert scene["layout_intent"] == "wide_particle_stage"
    assert scene["dashboard_layout"]["planning_basis"] == "scene_geometry_extent"
    assert scene["dashboard_layout"]["orb"]["anchor"] == "lower_right"
    assert scene["topic_scene_templates"] is False
    assert scene["scene_extent"]["motion_count"] >= 1
    assert any("사과" in beat["narration"] for beat in scene["beats"])
    assert any(beat.get("motion_path") for beat in scene["beats"])
    assert payload["answer_engine"]["external_llm"] is False
    assert payload["answer_engine"]["external_sllm"] is False
    assert payload["answer_engine"]["rule_based_answer_used"] is False
    assert payload["local_brain_write"] is False


def test_live_selfhood_self_model_generates_without_scratchpad_or_rule_answer(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    async def fail_query_graphrag(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("short self-model conversation must not enter graph retrieval")

    monkeypatch.setattr(dual_brain.alpha_service, "query_graphrag", fail_query_graphrag)
    client = TestClient(app)

    response = client.post(
        "/api/chat/atanor",
        json={"question": "지금 자기 모델을 설명해줘", "language": "ko", "brain_mode": "unified", "include_trace": False},
    )

    assert response.status_code == 200
    payload = response.json()["result"]
    assert payload["answer"]
    assert "자기 모델" in payload["answer"]
    assert "먼저 의도와 경계" not in payload["answer"]
    assert "내부적으로 점검" not in payload["answer"]
    assert payload["answer_kind"] == "asm_v0_conversation_surface"
    assert payload["speech_act"] == "self_model"
    assert payload["can_speak"] is True
    assert payload["trace"] is None
    assert payload["compact_trace"]["selfhood_loop"]["internal_scratchpad_visible"] is False
    assert payload["compact_trace"]["selfhood_loop"]["rule_based_answer_blocked"] is True
    assert payload["answer_engine"]["rule_based_answer_used"] is False
    assert payload["answer_engine"]["generation_basis"] == "semantic_grounded_conversation_router_v0"
    assert payload["answer_engine"]["semantic_grounding_used"] is True
    assert payload["route_type"] == "limitation_question"
    assert payload["external_llm_used"] is False
    assert payload["external_sllm_used"] is False
