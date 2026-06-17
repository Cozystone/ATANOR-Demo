from __future__ import annotations

import sys
import os
from pathlib import Path


os.environ.setdefault("ATANOR_DISABLE_DAEMON_SELF_HEAL", "1")
os.environ.setdefault("ATANOR_WEB_SEED_FEEDER_ON_TICK", "0")

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
DATAGATE_ROOT = REPO_ROOT / "packages" / "datagate"
ONTOLOGY_ROOT = REPO_ROOT / "packages" / "ontology_forge"
RAG_ROOT = REPO_ROOT / "packages" / "rag_engine"
GUARD_ROOT = REPO_ROOT / "packages" / "guard"
MODEL_ROOT = REPO_ROOT / "packages" / "model"
TRAINER_ROOT = REPO_ROOT / "packages" / "trainer"
NEURO_ROOT = REPO_ROOT / "packages" / "neuro_efficiency"
KNOWLEDGE_ROOT = REPO_ROOT / "packages" / "knowledge_bakery"
COST_ROOT = REPO_ROOT / "packages" / "cost_model"
SEED_ROOT = REPO_ROOT / "packages" / "seed_research"

for path in (API_ROOT, DATAGATE_ROOT, ONTOLOGY_ROOT, RAG_ROOT, GUARD_ROOT, MODEL_ROOT, TRAINER_ROOT, NEURO_ROOT, KNOWLEDGE_ROOT, COST_ROOT, SEED_ROOT):
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)
