"""Regression: the web-grounded rescue must NOT answer from an off-topic page.

A full-text encyclopedia search can return a page that merely *mentions* the term
(asking "팔란티어가 뭐야?" once surfaced a Miraculous Ladybug character-list page,
which is definition-shaped but not about the entity). The rescue must abstain in
that case and graft nothing — never present an unrelated page as the answer.
"""
from __future__ import annotations

import asyncio

import pytest

from app.routers import dual_brain


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _no_graft(monkeypatch):
    # Never touch the real candidate store during this test.
    monkeypatch.setattr(dual_brain, "_graft_web_nodes_to_cloud_brain", lambda *a, **k: {})


def test_off_topic_page_is_rejected_and_abstains(monkeypatch):
    off_topic = {
        "provider": "wikipedia",
        "results": [
            {
                "title": "미라큘러스: 레이디버그와 블랙캣의 등장인물 목록",
                "url": "https://ko.wikipedia.org/wiki/미라큘러스",
                "snippet": "미라큘러스: 레이디버그와 블랙캣의 등장인물 목록. 다음은 미라큘러스: 레이디버그와 블랙캣의 등장인물 문서이다. 여러 인물이 등장한다.",
                "query_terms_matched": 0,
            }
        ],
    }

    async def fake_search_web(query, count=5, provider=None):
        return off_topic

    monkeypatch.setattr("app.services.web_search.search_web", fake_search_web)

    out = _run(dual_brain._web_grounded_rescue("팔란티어가 뭐야?", "ko"))
    assert out is not None
    # Must abstain, not answer from the unrelated page.
    assert out.get("web_no_relevant_source") is True
    assert "미라큘러스" not in str(out.get("answer") or "")
    assert "레이디버그" not in str(out.get("answer") or "")
    assert out.get("reasoning_certificate", {}).get("guarantees", {}).get("grafted_to_brain") is False


def test_on_topic_page_is_answered(monkeypatch):
    on_topic = {
        "provider": "wikipedia",
        "results": [
            {
                "title": "팔란티어 테크놀로지스",
                "url": "https://ko.wikipedia.org/wiki/팔란티어_테크놀로지스",
                "snippet": "팔란티어 테크놀로지스는 빅 데이터 분석 소프트웨어 플랫폼을 전문으로 하는 미국의 소프트웨어 회사이다. 콜로라도주 덴버에 본사를 두고 있으며 2003년에 설립되었다.",
                "query_terms_matched": 1,
            }
        ],
    }

    async def fake_search_web(query, count=5, provider=None):
        return on_topic

    monkeypatch.setattr("app.services.web_search.search_web", fake_search_web)

    out = _run(dual_brain._web_grounded_rescue("팔란티어가 뭐야?", "ko"))
    assert out is not None
    assert not out.get("web_no_relevant_source")
    assert "팔란티어" in str(out.get("answer") or "")
