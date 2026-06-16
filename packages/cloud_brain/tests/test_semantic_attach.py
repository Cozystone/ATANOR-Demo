from pathlib import Path

from packages.cloud_brain.semantic_attach import attach_semantic_cloud_for_query
from packages.cloud_brain.semantic_growth import ingest_semantic_source


def test_attach_semantic_cloud_is_temporary_and_local_write_false(tmp_path: Path):
    cloud_root = tmp_path / "cloud"
    attachment_root = tmp_path / "attachments"
    ingest_semantic_source("쿠버네티스는 컨테이너화된 애플리케이션을 자동으로 배포하고 관리하는 오픈소스 플랫폼입니다.", "sample", "ko", cloud_root=cloud_root)
    result = attach_semantic_cloud_for_query("쿠버네티스가 뭐야?", cloud_root=cloud_root, attachment_root=attachment_root)
    assert result["attached_nodes"]
    assert result["temporary"] is True
    assert result["local_brain_write"] is False
    assert result["cloud_attached_counts_as_local"] is False
