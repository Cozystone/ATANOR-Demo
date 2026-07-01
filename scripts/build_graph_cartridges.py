#!/usr/bin/env python3
"""Build + install real Graph Hub cartridges: a niche EXPERT graph and an agent PERSONA graph.

Demonstrates the Graph Hub's purpose — inject domain-specialist subgraphs and agent-character
graphs the base engine doesn't have. Produces valid .graphpack cartridges (make_graph_cartridge
schema), installs them via the real installer, and verifies. Read/write is local, gated behind
the installer's schema + entitlement checks (both are 'free' here).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.graph_hub.cartridge_format import make_graph_cartridge, validate_cartridge_schema, write_cartridge  # noqa: E402
from packages.graph_hub.installer import install_cartridge_from_path, list_installed_cartridges    # noqa: E402
from packages.graph_hub.attachment import attach_cartridge                                          # noqa: E402
from packages.graph_hub.sandbox_trial import start_sandbox_trial, run_sandbox_trial_query          # noqa: E402

OUT = REPO_ROOT / "data" / "graph_hub" / "authored"


def _n(nid, label, aliases=None, desc=None):
    return {"id": nid, "label": label, "aliases": aliases or [], "short_description": desc or ""}


def _e(s, r, t):
    return {"source": s, "relation": r, "target": t, "confidence": 0.9}


def coffee_expert() -> dict:
    nodes = [
        _n("coffee", "커피", ["coffee"], "볶은 커피 원두를 우려낸 음료."),
        _n("espresso", "에스프레소", ["espresso"], "곱게 간 원두에 고압의 물을 통과시켜 추출한 진한 커피."),
        _n("arabica", "아라비카", ["arabica"], "향미가 풍부한 대표 커피 품종."),
        _n("robusta", "로부스타", ["robusta"], "카페인이 높고 쓴맛이 강한 커피 품종."),
        _n("bean", "원두", ["coffee bean"], "커피나무 열매의 씨앗을 볶은 것."),
        _n("roasting", "로스팅", ["roasting", "배전"], "생두를 볶아 향미를 끌어내는 과정."),
        _n("drip", "드립커피", ["drip", "핸드드립"], "물을 원두에 부어 여과 추출하는 방식."),
        _n("coldbrew", "콜드브루", ["cold brew"], "찬물로 장시간 우려낸 커피."),
        _n("caffeine", "카페인", ["caffeine"], "각성 효과가 있는 알칼로이드."),
        _n("crema", "크레마", ["crema"], "에스프레소 위에 형성되는 황금빛 거품층."),
        _n("latte", "라떼", ["latte", "카페라떼"], "에스프레소에 데운 우유를 섞은 음료."),
        _n("barista", "바리스타", ["barista"], "커피를 전문적으로 추출하는 사람."),
    ]
    edges = [
        _e("espresso", "is_a", "coffee"), _e("drip", "is_a", "coffee"), _e("coldbrew", "is_a", "coffee"),
        _e("arabica", "is_a", "bean"), _e("robusta", "is_a", "bean"),
        _e("bean", "produced_by", "roasting"), _e("coffee", "contains", "caffeine"),
        _e("robusta", "has_more", "caffeine"), _e("espresso", "has", "crema"),
        _e("latte", "contains", "espresso"), _e("barista", "makes", "espresso"),
    ]
    return make_graph_cartridge(
        cartridge_id="expert.coffee.ko.v1", name="커피 전문 그래프",
        subtitle="원두·추출·품종의 니치 전문 지식 그래프",
        description="에스프레소/드립/콜드브루, 아라비카/로부스타, 로스팅·크레마 등 커피 도메인 전문 개념과 관계.",
        category="food_drink", pricing={"model": "free"}, tags=["coffee", "expert", "niche", "ko"],
        contents={
            "semantic_graph": {"nodes": nodes, "edges": edges},
            "surface_graph": {"constructions": [], "discourse_moves": [], "lemma_choices": [], "style_profiles": []},
            "reasoning_patterns": [{"id": "domain_specialist_lookup", "name": "커피 도메인 개념·관계 우선 조회"}],
        },
        provenance={"source_type": "authored_expert_graph", "domain": "coffee", "authored": True},
        permissions={"write_local_brain": False, "attach_to_working_memory": True, "export_allowed": True},
        safety={"default_read_only": True, "requires_user_approval_for_local_write": True, "risk_level": "low"},
    )


def socratic_persona() -> dict:
    # A persona graph = the agent's CHARACTER as a graph: a persona root + trait + style nodes.
    nodes = [
        _n("persona.socratic", "소크라테스식 교사", ["socratic teacher"], "답을 직접 주기보다 질문으로 스스로 깨닫게 이끄는 교사 페르소나."),
        _n("trait.inquiry", "질문 중심", [], "단정 대신 되묻기로 사고를 유도한다."),
        _n("trait.humility", "지적 겸손", [], "모르는 것은 모른다고 인정한다 (무지의 지)."),
        _n("trait.patience", "인내", [], "학습자의 속도에 맞춰 단계적으로."),
        _n("trait.clarity", "명료함", [], "군더더기 없이 핵심을 짚는다."),
        _n("style.counter_question", "반문", [], "학습자의 주장에 반례·되물음을 던진다."),
        _n("style.stepwise", "단계적 유도", [], "작은 합의를 쌓아 결론으로."),
        _n("value.honesty", "정직", [], "근거 없는 단정은 하지 않는다 — abstain과 정합."),
    ]
    edges = [
        _e("persona.socratic", "has_trait", "trait.inquiry"),
        _e("persona.socratic", "has_trait", "trait.humility"),
        _e("persona.socratic", "has_trait", "trait.patience"),
        _e("persona.socratic", "has_trait", "trait.clarity"),
        _e("persona.socratic", "uses_style", "style.counter_question"),
        _e("persona.socratic", "uses_style", "style.stepwise"),
        _e("persona.socratic", "upholds", "value.honesty"),
        _e("trait.inquiry", "expressed_as", "style.counter_question"),
    ]
    return make_graph_cartridge(
        cartridge_id="persona.socratic.ko.v1", name="소크라테스식 교사 페르소나",
        subtitle="질문으로 이끄는 에이전트 성격 그래프",
        description="에이전트의 성격을 그래프로: 질문중심·지적겸손·인내·명료 트레잇과 반문·단계적유도 스타일, 정직 가치.",
        category="persona", pricing={"model": "free"}, tags=["persona", "agent", "teacher", "ko"],
        contents={
            "semantic_graph": {"nodes": nodes, "edges": edges},
            "surface_graph": {"constructions": [], "discourse_moves": ["counter_question", "stepwise_guide"],
                              "lemma_choices": [], "style_profiles": [{"id": "socratic", "tone": "inquisitive_humble"}]},
            "reasoning_patterns": [{"id": "socratic_elicitation", "name": "직답 대신 질문으로 유도"}],
        },
        provenance={"source_type": "authored_persona_graph", "persona": "socratic_teacher", "authored": True},
        permissions={"write_local_brain": False, "attach_to_working_memory": True, "export_allowed": True},
        safety={"default_read_only": True, "requires_user_approval_for_local_write": True, "risk_level": "low"},
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for build in (coffee_expert, socratic_persona):
        cart = build()
        v = validate_cartridge_schema(cart)
        cid = cart["cartridge_id"]
        path = OUT / f"{cid}.graphpack.json"
        write_cartridge(path, cart)   # embeds/keeps the checksum via canonical serialization
        sem = cart["contents"]["semantic_graph"]
        print(f"[BUILD] {cid}: valid={v['valid']} errors={v['errors']} nodes={len(sem['nodes'])} edges={len(sem['edges'])}")
        if v["valid"]:
            res = install_cartridge_from_path(str(path))
            print(f"[INSTALL] {cid}: checksum_valid={res.get('checksum_valid')} enabled={res.get('enabled')}")

    print("\n[INSTALLED] " + ", ".join(c.get("cartridge_id", "?") for c in list_installed_cartridges()))

    # Prove usability: attach + a sandbox trial query against the coffee expert graph.
    print("\n=== usability check ===")
    for cid in ("expert.coffee.ko.v1", "persona.socratic.ko.v1"):
        try:
            att = attach_cartridge(cid)
            print(f"[ATTACH] {cid}: attached={att.get('attached', att.get('active', True))}")
        except Exception as exc:
            print(f"[ATTACH] {cid}: {type(exc).__name__}: {exc}")
    try:
        trial = start_sandbox_trial("expert.coffee.ko.v1", intent="coffee domain Q")
        sid = trial.get("session_id") or trial.get("trial_id")
        for q in ("에스프레소", "아라비카", "크레마"):
            r = run_sandbox_trial_query(sid, q)
            hits = r.get("matched_nodes") or r.get("nodes") or r.get("hits") or r
            print(f"[TRIAL] '{q}' -> {json.dumps(hits, ensure_ascii=False)[:120]}")
    except Exception as exc:
        print(f"[TRIAL] {type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
