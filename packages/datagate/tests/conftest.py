"""Shared fixtures: temp data dirs and a deterministic fixture corpus."""

from __future__ import annotations

from pathlib import Path

import pytest

from datagate import DataGateConfig

# A long clean prose document (well over min_chars, low special/link ratios).
CLEAN_LONG = (
    "Homage1.0 is a transparent neuro-symbolic AI factory. "
    "It collects knowledge from documents, filters out low quality data, "
    "structures the survivors into an ontology and a knowledge graph, and "
    "trains a small language model from scratch. The whole process is shown "
    "on a web dashboard called BakeBoard so that every stage of the pipeline "
    "is visible and inspectable. DataGate is the quality gate that protects "
    "the small model from noisy and low quality training material. "
) * 4

SHORT_DOC = "Too short to keep."

# Two byte-for-byte identical long documents (different filenames), distinct
# from CLEAN_LONG so the dedup scenario is independent of the accepted doc.
DUP_TEXT = (
    "Deduplication keeps the training corpus clean. When the same passage "
    "appears twice it teaches the small model nothing new and skews token "
    "statistics, so DataGate keeps only the first occurrence in a run. "
) * 4
DUP_A = DUP_TEXT
DUP_B = DUP_TEXT

# Symbol soup: long enough to pass min_length, but mostly non-text glyphs.
SYMBOL_SOUP = "█▓▒░@#$%^&*<>{}[]|\\~`█▓▒░@#$%^&*<>{}=+/" * 12

# A document that is almost entirely links.
LINK_LIST = "\n".join(f"https://example.com/page/{i}" for i in range(40))

# Korean prose (Unicode alnum) — should pass the special-char filter.
KOREAN_DOC = (
    "호마지는 투명한 뉴로 심볼릭 인공지능 공장이다. "
    "이 시스템은 문서에서 지식을 모으고 저품질 데이터를 걸러낸다. "
    "작은 언어 모델을 처음부터 학습시키며 그 과정을 웹에서 보여준다. "
) * 3

EMPTY_DOC = ""


@pytest.fixture
def config(tmp_path: Path) -> DataGateConfig:
    """A DataGateConfig wired to isolated temp directories."""
    return DataGateConfig(
        input_dir=str(tmp_path / "raw"),
        cleaned_dir=str(tmp_path / "cleaned"),
        rejected_dir=str(tmp_path / "rejected"),
        metadata_dir=str(tmp_path / "metadata"),
    )


def _write(base: Path, rel: str, text: str) -> None:
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def corpus(config: DataGateConfig) -> DataGateConfig:
    """Populate data/raw with one document per scenario and return the config."""
    raw = Path(config.input_dir)
    _write(raw, "clean_long.md", CLEAN_LONG)
    _write(raw, "short.txt", SHORT_DOC)
    _write(raw, "dup_a.txt", DUP_A)
    _write(raw, "dup_b.txt", DUP_B)
    _write(raw, "symbols.txt", SYMBOL_SOUP)
    _write(raw, "links.md", LINK_LIST)
    _write(raw, "korean.txt", KOREAN_DOC)
    _write(raw, "empty.txt", EMPTY_DOC)
    return config
