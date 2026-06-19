from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from guard.release_mock_audit import audit_mock_risks


def test_release_mock_audit_blocks_fake_counts(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text('FAKE_GRAPH_COUNT = 1000\n', encoding="utf-8")

    report = audit_mock_risks([tmp_path], repo_root=tmp_path)

    assert report["passed"] is False
    assert report["counts"]["BLOCKER"] == 1
    assert report["risks"][0]["category"] == "release_blocker"


def test_release_mock_audit_allows_honest_local_mock_boundary(tmp_path: Path) -> None:
    path = tmp_path / "proof.py"
    path.write_text('billing_mode = "local_mock"  # proof-only local billing simulation\n', encoding="utf-8")

    report = audit_mock_risks([tmp_path], repo_root=tmp_path)

    assert report["passed"] is True
    assert report["counts"]["INFO"] == 1


def test_release_mock_audit_marks_unknown_mock_for_review(tmp_path: Path) -> None:
    path = tmp_path / "runtime.py"
    path.write_text('result = run_mock_purchase()\n', encoding="utf-8")

    report = audit_mock_risks([tmp_path], repo_root=tmp_path)

    assert report["passed"] is True
    assert report["counts"]["REVIEW"] == 1


def test_release_mock_audit_allows_honesty_false_flags(tmp_path: Path) -> None:
    path = tmp_path / "status.py"
    path.write_text('"fake_counts": False\n', encoding="utf-8")

    report = audit_mock_risks([tmp_path], repo_root=tmp_path)

    assert report["passed"] is True
    assert report["counts"]["INFO"] == 1
