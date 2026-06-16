from pathlib import Path

from packages.cloud_brain.semantic_growth import ingest_semantic_source
from packages.cloud_brain.semantic_store import SemanticCloudStore


SAMPLE_KO = "쿠버네티스는 컨테이너화된 애플리케이션을 자동으로 배포하고 관리하는 오픈소스 플랫폼입니다."
SAMPLE_EN = "Kubernetes is an open-source platform that manages containerized applications and automates deployment."


def test_semantic_ingest_creates_store_records(tmp_path: Path):
    root = tmp_path / "cloud"
    result = ingest_semantic_source(SAMPLE_KO, "sample-ko", "ko", cloud_root=root)
    status = SemanticCloudStore(root).status()
    assert result["concepts_created"] > 0
    assert result["relations_created"] > 0
    assert status["concepts"] > 0
    assert result["honesty"]["local_brain_write"] is False


def test_duplicate_ingest_strengthens_not_explodes(tmp_path: Path):
    root = tmp_path / "cloud"
    first = ingest_semantic_source(SAMPLE_KO, "sample-ko", "ko", cloud_root=root)
    second = ingest_semantic_source(SAMPLE_KO, "sample-ko", "ko", cloud_root=root)
    status = SemanticCloudStore(root).status()
    assert second["concepts_merged"] > 0
    assert second["relations_strengthened"] > 0
    assert status["concepts"] == first["status"]["concepts"]


def test_cross_language_alias_strengthens_existing_concept(tmp_path: Path):
    root = tmp_path / "cloud"
    ingest_semantic_source(SAMPLE_KO, "sample-ko", "ko", cloud_root=root)
    result = ingest_semantic_source(SAMPLE_EN, "sample-en", "en", cloud_root=root)
    assert result["concepts_merged"] > 0
