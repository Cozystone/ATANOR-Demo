#!/usr/bin/env python3
"""Promotion: Cloud Brain candidate graph -> base_brain answer pack.

This is the missing link. The continuous learner writes into the cloud candidate store
(clean_seed_v2, ~7500 concepts), but answer_with_base_brain() reads a SEPARATE curated
pack (58 concepts) — so learning never reaches general answers. This batch promotion
builds an enriched pack = curated concepts (kept, high quality) + cloud-graph concepts,
each with a FAITHFUL short_description = a verbatim source sentence (linked by source_hash,
No-LLM, never paraphrased) and its IS_A/typed relations.

Re-runnable (periodic refresh). Backs nothing up itself (caller backed up the pack);
writes PACK_PATH with base_pack_code_version aligned to the loader so it is authoritative
(not rebuilt to curated-only on next load).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.base_brain.benchmark import build_zero_user_benchmark_v0          # noqa: E402
from packages.base_brain.models import PACK_PATH                                # noqa: E402
from packages.base_brain.pack_loader import BASE_PACK_CODE_VERSION              # noqa: E402
from packages.base_brain.seed_extension import build_seed_graph_v2             # noqa: E402
from packages.base_brain.semantic_pack import build_general_semantic_pack_v0   # noqa: E402
from packages.base_brain.surface_pack import build_general_surface_pack_v0     # noqa: E402
from packages.base_brain.pack_builder import _lemma_links                       # noqa: E402
from packages.base_brain.models import utc_now_iso                             # noqa: E402

STORE = REPO_ROOT / "data" / "cloud_brain" / "candidate_runs" / "clean_seed_v2"
MOJIBAKE = ("荑", "吏", "媛", "占")  # _needs_rebuild trips on these; skip such descriptions


def _read(fn: str) -> list[dict]:
    p = STORE / fn
    out = []
    if p.exists():
        for line in p.open(encoding="utf-8"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def _clean_desc(text: str) -> str | None:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not (20 <= len(t) <= 220):
        return None
    if any(m in t for m in MOJIBAKE):
        return None
    return t


def promote() -> dict:
    # curated stays authoritative
    curated = build_general_semantic_pack_v0()
    curated_concepts = curated.get("concepts", [])
    taken_ids = {str(c["concept_id"]) for c in curated_concepts}
    taken_names = {str(c.get("canonical_name", "")).lower() for c in curated_concepts}

    # cloud graph
    evidence = _read("evidence.jsonl")
    text_by_hash = {}
    for e in evidence:
        h = e.get("source_hash")
        if h and h not in text_by_hash:
            d = _clean_desc(e.get("text"))
            if d:
                text_by_hash[h] = d

    # ABOUTNESS gate: a sentence may only describe a concept that is its TOPIC
    # (subject). Build source_hash -> set(topic heads) from case_frames, so we never
    # attach a sentence about Nvidia to the concept "델라웨어" just because it is
    # mentioned. Only definitional/subject sentences become descriptions.
    def _norm(s: str) -> str:
        return re.sub(r"\s+", " ", str(s or "")).strip().lower()

    topics_by_hash: dict[str, set] = {}
    for fr in _read("case_frames.jsonl"):
        h = fr.get("source_hash")
        if not h:
            continue
        for role in fr.get("case_roles") or []:
            if str(role.get("role")) in ("TOPIC", "SUBJ", "SUBJECT"):
                topics_by_hash.setdefault(h, set()).add(_norm(role.get("head")))

    concepts = _read("concepts.jsonl")
    id_to_name = {c["concept_id"]: c.get("canonical_name", "") for c in concepts}
    rels_by_src: dict[str, list] = {}
    all_rels: list[dict] = []
    for r in _read("relations.jsonl"):
        rels_by_src.setdefault(r.get("source_concept_id"), []).append(r)
        all_rels.append(r)

    # Data-derived quality signals (NO rule list):
    #  - in_degree: how many facts REFERENCE a concept — a referenced concept is a real
    #    entity; an adverbial/filler subject (원래/오늘/지금) is never referenced (in=0).
    #  - predicate informativeness: selective verbs (결합하다) outrank light verbs (하다).
    from packages.cloud_brain.neuroplasticity import predicate_informativeness
    in_degree: dict[str, int] = {}
    for r in all_rels:
        t = r.get("target_concept_id")
        if t:
            in_degree[t] = in_degree.get(t, 0) + 1
    pred_info = predicate_informativeness(all_rels)

    promoted = []
    for c in concepts:
        name = str(c.get("canonical_name") or "").strip()
        if not name or name.lower() in taken_names:
            continue
        # faithful AND about-this-concept: the sentence's TOPIC must be this concept
        # AND the sentence must LEAD with the concept name (it is the primary
        # subject, not a mid-sentence topic). This filters run-ons ("프레디 머큐리는
        # 〈곡〉는 ...") and mentions where the real subject is something else.
        desc = None
        nn = _norm(name)
        for h in (c.get("source_hashes") or []):
            txt = text_by_hash.get(h)
            if txt and nn in topics_by_hash.get(h, set()) and _norm(txt).startswith(nn):
                desc = txt
                break
        if not desc:
            continue  # no sentence leads with / is about this concept -> do not promote
        # desc leads with the concept name; strip that leading subject + particle so
        # the answer engine's own "{name}는" prefix does not double it
        # ("종족은 종족은 테란이며" -> "종족은 테란이며").
        m = re.match(re.escape(name) + r"\s*(?:은|는|이|가|란|이란|도|을|를|와|과)?\s*", desc)
        if m and (len(desc) - m.end()) >= 12:
            desc = desc[m.end():].strip()
        cid = str(c["concept_id"])
        if cid in taken_ids:
            continue
        # Quality gate: keep IS_A always; surface predicate (association) relations ONLY
        # for referenced entities (in_degree>=1), then only the most informative ones
        # with a substantive target. Parse-error/adverbial subjects (in_degree 0) fall
        # back to definition + IS_A only, instead of emitting noise
        # ("원래는 디자이너를 취직합니다").
        raw = rels_by_src.get(cid, [])
        chosen: list[dict] = []
        # Only REFERENCED entities (in_degree>=1) get relations at all; adverbial/filler
        # parse-error subjects (원래/오늘, in=0) fall back to description-only, so we never
        # assert a false "X의 한 종류" or a junk association for them.
        if in_degree.get(cid, 0) >= 1:
            chosen = [r for r in raw if str(r.get("relation")) == "IS_A"][:2]
            cand = [r for r in raw if str(r.get("relation")) != "IS_A"
                    and pred_info.get(str(r.get("relation")), 0.0) >= 0.3
                    and len(str(id_to_name.get(r.get("target_concept_id")) or "").strip()) >= 2]
            cand.sort(key=lambda r: pred_info.get(str(r.get("relation")), 0.0), reverse=True)
            chosen += cand[:3]
        rels = []
        for r in chosen:
            tgt = id_to_name.get(r.get("target_concept_id")) or r.get("target_concept_id")
            if tgt:
                rels.append({
                    "source": cid, "relation": str(r.get("relation", "is_a")).lower(),
                    "target": str(tgt), "confidence": round(float(c.get("confidence", 0.6)), 3),
                    "source_type": "cloud_graph_promoted",
                })
        promoted.append({
            "concept_id": cid,
            "canonical_name": name,
            "aliases": [],
            "labels": {c.get("language", "ko"): name},
            "short_description": desc,
            "relations": rels,
            "confidence": round(float(c.get("trust", 0.5)), 3),
            "source_type": "cloud_graph_promoted",
        })
        taken_ids.add(cid)
        taken_names.add(name.lower())

    merged = list(curated_concepts) + promoted
    semantic_graph = dict(curated)
    semantic_graph["concepts"] = merged
    semantic_graph["relation_count"] = sum(len(c.get("relations", [])) for c in merged)
    semantic_graph["source_type"] = "curated_plus_cloud_promoted"

    seed_graph = build_seed_graph_v2()
    surface_graph = build_general_surface_pack_v0()
    benchmark = build_zero_user_benchmark_v0()
    payload = {
        "pack_id": "atanor_base_brain_v0",
        "version": "0.1.5",
        "metadata": {
            "created_at": utc_now_iso(),
            "base_pack_code_version": BASE_PACK_CODE_VERSION,  # align => authoritative, no rebuild
            "claims": ["zero-user-data graph-native answers", "curated base + cloud-graph promoted concepts",
                       "no external LLM/sLLM", "faithful descriptions = verbatim sourced sentences"],
            "does_not_claim": ["GPT-level quality", "complete world knowledge", "trained neural decoder"],
            "promotion": {"source_store": STORE.name, "curated": len(curated_concepts),
                          "promoted_from_cloud": len(promoted), "total": len(merged)},
            "semantic_surface_links": _lemma_links(semantic_graph, surface_graph),
            "honesty": {"user_data_used": False, "external_llm_used": False,
                        "external_sllm_used": False, "external_web_used": False},
        },
        "seed_graph": seed_graph,
        "semantic_graph": semantic_graph,
        "surface_graph": surface_graph,
        "benchmark": benchmark,
    }
    PACK_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"curated": len(curated_concepts), "promoted": len(promoted), "total": len(merged),
            "pack": str(PACK_PATH)}


if __name__ == "__main__":
    r = promote()
    print(f"[PROMOTE] curated={r['curated']} + cloud_promoted={r['promoted']} = total={r['total']} concepts")
    print(f"[PROMOTE] wrote {r['pack']} (base_pack_code_version aligned -> authoritative)")
