from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
DATAGATE_ROOT = REPO_ROOT / "packages" / "datagate"
ONTOLOGY_ROOT = REPO_ROOT / "packages" / "ontology_forge"
RAG_ROOT = REPO_ROOT / "packages" / "rag_engine"
GUARD_ROOT = REPO_ROOT / "packages" / "guard"
MODEL_ROOT = REPO_ROOT / "packages" / "model"
TRAINER_ROOT = REPO_ROOT / "packages" / "trainer"
NEURO_ROOT = REPO_ROOT / "packages" / "neuro_efficiency"

for path in (API_ROOT, DATAGATE_ROOT, ONTOLOGY_ROOT, RAG_ROOT, GUARD_ROOT, MODEL_ROOT, TRAINER_ROOT, NEURO_ROOT):
    path_string = str(path)
    if path_string not in sys.path:
        sys.path.insert(0, path_string)
