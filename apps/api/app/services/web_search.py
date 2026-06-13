from __future__ import annotations

import os
import re
import urllib.request
import xml.etree.ElementTree as ET
import json
from html import unescape
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote, quote_plus


@dataclass
class WebSearchResult:
    id: str
    title: str
    url: str
    snippet: str
    provider: str
    source_type: str = "web_search"
    license_status: str = "reference_only"


DEFAULT_QUERY = "GraphRAG neuromorphic continual learning low power AI architecture"

STATIC_RESULTS = [
    WebSearchResult(
        id="web-static-001",
        title="Microsoft GraphRAG",
        url="https://github.com/microsoft/graphrag",
        snippet="Microsoft GraphRAG provides a graph-based retrieval augmented generation system with indexing and query workflows.",
        provider="static",
        source_type="repository_or_docs",
    ),
    WebSearchResult(
        id="web-static-002",
        title="Grounding with Bing Search tools with the agents API",
        url="https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/bing-tools",
        snippet="Microsoft Foundry agents can use Grounding with Bing Search to incorporate real-time public web data and cite sources.",
        provider="static",
        source_type="official_docs",
    ),
    WebSearchResult(
        id="web-static-003",
        title="Bing Search APIs retiring on August 11, 2025",
        url="https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement",
        snippet="Microsoft says Bing Search APIs retire on August 11, 2025 and recommends Grounding with Bing Search as part of Azure AI Agents.",
        provider="static",
        source_type="official_docs",
    ),
    WebSearchResult(
        id="web-static-004",
        title="MiroFish",
        url="https://github.com/666ghj/MiroFish",
        snippet="MiroFish demonstrates a console-style graph growth interface useful as a UI reference for ATANOR BakeBoard.",
        provider="static",
        source_type="repository_or_docs",
    ),
]


def _provider_from_env(provider: str | None = None) -> str:
    return (provider or os.getenv("WEB_SEARCH_PROVIDER") or "static").strip().lower()


FRESH_SEARCH_PATTERN = re.compile(
    "(\uC624\uB298|\uD604\uC7AC|\uCD5C\uC2E0|\uBC29\uAE08|\uC2E4\uC2DC\uAC04|\uC18D\uBCF4|\uB274\uC2A4|\uB0A0\uC528|\uC8FC\uAC00|\uD658\uC728|today|latest|recent|current|breaking|news|weather|stock|price)",
    re.IGNORECASE,
)
KNOWLEDGE_LOOKUP_PATTERN = re.compile(
    "(\uB204\uAD6C|\uB204\uAD6C\uC57C|\uBB50\uC57C|\uBB34\uC5C7|\uC815\uC758|\uC54C\uB824\uC918|\uC124\uBA85|who is|what is|tell me about|define|explain)",
    re.IGNORECASE,
)


def is_fresh_search_query(query: str) -> bool:
    return bool(FRESH_SEARCH_PATTERN.search(query))


def is_knowledge_lookup_query(query: str) -> bool:
    return bool(KNOWLEDGE_LOOKUP_PATTERN.search(query))


def _provider_configured(provider: str) -> bool:
    if provider == "brave":
        return bool(os.getenv("BRAVE_SEARCH_API_KEY"))
    if provider == "serper":
        return bool(os.getenv("SERPER_API_KEY"))
    if provider == "tavily":
        return bool(os.getenv("TAVILY_API_KEY"))
    if provider in {"microsoft-grounding", "grounding-with-bing", "bing-grounding"}:
        return bool(os.getenv("FOUNDRY_PROJECT_ENDPOINT") and os.getenv("BING_PROJECT_CONNECTION_ID"))
    return provider == "static"


def provider_status(provider: str | None = None) -> dict[str, Any]:
    selected = _provider_from_env(provider)
    return {
        "selected_provider": selected,
        "configured": _provider_configured(selected),
        "raw_result_providers": {
            "brave": bool(os.getenv("BRAVE_SEARCH_API_KEY")),
            "serper": bool(os.getenv("SERPER_API_KEY")),
            "tavily": bool(os.getenv("TAVILY_API_KEY")),
            "wikipedia": True,
            "static": True,
        },
        "microsoft_grounding_with_bing": {
            "configured": _provider_configured("microsoft-grounding"),
            "mode": "foundry_agent_tool",
            "native_homage_default": False,
            "reason": "Grounding with Bing is an Azure Foundry Agent tool that returns model responses with citations, not raw searchable chunks for ATANOR native synthesis.",
            "required_env": [
                "FOUNDRY_PROJECT_ENDPOINT",
                "FOUNDRY_MODEL_DEPLOYMENT_NAME",
                "BING_PROJECT_CONNECTION_ID",
                "AGENT_TOKEN or Azure credential",
            ],
        },
    }


def static_search(query: str, count: int = 5) -> list[dict[str, Any]]:
    terms = [term.lower() for term in query.split() if len(term) > 1]
    scored: list[tuple[int, WebSearchResult]] = []
    for result in STATIC_RESULTS:
        haystack = f"{result.title} {result.snippet} {result.url}".lower()
        score = sum(1 for term in terms if term in haystack)
        scored.append((score, result))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [asdict(result) | {"search_score": score} for score, result in scored[: max(1, min(count, 10))]]


def _strip_html(value: str) -> str:
    text = unescape(unescape(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z#0-9]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_lookup_query(query: str) -> str:
    cleaned = re.sub(r"[?!.,]", " ", query)
    cleaned = re.sub(
        "(\uB204\uAD6C\uC57C|\uB204\uAD6C\uB2C8|\uB204\uAD6C|\uBB50\uC57C|\uBB34\uC5C7\uC774\uC57C|\uBB34\uC5C7|\uC54C\uB824\uC918|\uC124\uBA85\uD574\uC918|\uC18C\uAC1C\uD574\uC918|\uC815\uC758|who is|what is|tell me about|define|explain)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    tokens = [token for token in re.split(r"\s+", cleaned.strip()) if token]
    trimmed = [re.sub("[\uC740\uB294\uC774\uAC00\uC744\uB97C]$", "", token) for token in tokens]
    return " ".join(token for token in trimmed if token).strip() or query.strip()


def wikipedia_search(query: str, count: int = 5) -> list[dict[str, Any]]:
    lookup = _normalize_lookup_query(query)
    bounded_count = max(1, min(count, 10))
    api_url = (
        "https://ko.wikipedia.org/w/api.php?action=query&list=search&format=json&utf8=1"
        f"&srlimit={bounded_count}&srsearch={quote_plus(lookup)}"
    )
    request = urllib.request.Request(api_url, headers={"User-Agent": "ATANORAlpha/0.1 web-search"})
    with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310 - bounded public API endpoint
        body = json.loads(response.read().decode("utf-8"))
    results: list[dict[str, Any]] = []
    for index, item in enumerate((body.get("query", {}).get("search", []) or [])[:bounded_count], start=1):
        title = _strip_html(item.get("title") or lookup)
        page_slug = quote(title.replace(" ", "_"), safe="")
        page_url = f"https://ko.wikipedia.org/wiki/{page_slug}"
        snippet = _strip_html(item.get("snippet") or "")
        if index <= 2:
            try:
                summary_url = f"https://ko.wikipedia.org/api/rest_v1/page/summary/{page_slug}"
                summary_request = urllib.request.Request(summary_url, headers={"User-Agent": "ATANORAlpha/0.1 web-search"})
                with urllib.request.urlopen(summary_request, timeout=5) as summary_response:  # nosec B310
                    summary = json.loads(summary_response.read().decode("utf-8"))
                snippet = _strip_html(summary.get("extract") or snippet)
                page_url = summary.get("content_urls", {}).get("desktop", {}).get("page") or page_url
            except Exception:
                pass
        if title and snippet:
            results.append(
                {
                    "id": f"wikipedia-{index}",
                    "title": title,
                    "url": page_url,
                    "snippet": snippet,
                    "provider": "wikipedia",
                    "source_type": "encyclopedia_search",
                    "license_status": "reference_only",
                    "search_score": bounded_count - index + 1,
                }
            )
    return results


def news_rss_search(query: str, count: int = 5) -> list[dict[str, Any]]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    request = urllib.request.Request(url, headers={"User-Agent": "ATANORAlpha/0.1 web-search"})
    with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310 - bounded public RSS endpoint
        xml = response.read()
    root = ET.fromstring(xml)
    results: list[dict[str, Any]] = []
    for index, item in enumerate(root.findall(".//item")[: max(1, min(count, 10))], start=1):
        title = (item.findtext("title") or "News result").strip()
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        description = _strip_html(item.findtext("description") or "")
        if not link:
            continue
        results.append(
            {
                "id": f"news-rss-{index}",
                "title": title,
                "url": link,
                "snippet": f"{pub_date} - {description}" if pub_date else description,
                "provider": "news-rss",
                "source_type": "news_search",
                "license_status": "reference_only",
                "search_score": count - index + 1,
            }
        )
    return results


async def search_web(query: str | None = None, count: int = 5, provider: str | None = None) -> dict[str, Any]:
    selected = _provider_from_env(provider)
    clean_query = (query or DEFAULT_QUERY).strip() or DEFAULT_QUERY
    bounded_count = max(1, min(int(count or 5), 10))
    if selected in {"microsoft-grounding", "grounding-with-bing", "bing-grounding"}:
        return {
            "provider": "microsoft-grounding",
            "query": clean_query,
            "results": [],
            "configured": _provider_configured("microsoft-grounding"),
            "bing_query_url": f"https://www.bing.com/search?q={quote_plus(clean_query)}",
            "status": "metadata_only",
            "message": "Grounding with Bing is configured through Azure Foundry Agents and does not expose raw result chunks to this native ATANOR harvest path.",
            "provider_status": provider_status(selected),
        }

    # The Python local companion keeps network calls conservative. Raw-result
    # providers are wired in the deployable Next route; local FastAPI exposes
    # the same contract and falls back to deterministic reference results.
    if is_fresh_search_query(clean_query) and selected == "static":
        try:
            results = news_rss_search(clean_query, bounded_count)
            if results:
                return {
                    "provider": "news-rss",
                    "query": clean_query,
                    "results": results,
                    "configured": True,
                    "bing_query_url": f"https://www.bing.com/search?q={quote_plus(clean_query)}",
                    "status": "ok",
                    "provider_status": provider_status(selected),
                }
        except Exception:
            pass
    if is_knowledge_lookup_query(clean_query) and selected == "static":
        try:
            results = wikipedia_search(clean_query, bounded_count)
            if results:
                return {
                    "provider": "wikipedia",
                    "query": clean_query,
                    "results": results,
                    "configured": True,
                    "bing_query_url": f"https://www.bing.com/search?q={quote_plus(clean_query)}",
                    "status": "ok",
                    "provider_status": provider_status(selected),
                }
        except Exception:
            pass
    return {
        "provider": selected if _provider_configured(selected) else "static",
        "query": clean_query,
        "results": static_search(clean_query, bounded_count),
        "configured": _provider_configured(selected),
        "bing_query_url": f"https://www.bing.com/search?q={quote_plus(clean_query)}",
        "status": "ok" if selected == "static" else "fallback_static",
        "provider_status": provider_status(selected),
    }


def web_results_to_evidence(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence = []
    for index, result in enumerate(results, start=1):
        evidence.append(
            {
                "doc_id": result.get("id") or f"web-{index:03d}",
                "chunk_id": f"{result.get('id') or f'web-{index:03d}'}#search",
                "path": result.get("url", ""),
                "url": result.get("url", ""),
                "score": round(0.72 + min(index, 5) * 0.03, 3),
                "snippet": result.get("snippet", ""),
                "title": result.get("title", "Web result"),
                "retrieval_signals": {"web_search": 1, "provider": result.get("provider", "static")},
            }
        )
    return evidence
