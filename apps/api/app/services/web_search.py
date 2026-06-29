from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import json
from html import unescape
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import quote, quote_plus


# Wikimedia's User-Agent policy REQUIRES a descriptive agent with a real contact
# (URL or email). A generic / "contact: local" agent gets aggressively 429'd — that
# was the real cause of the recurring "web_unreachable": with a proper UA the same
# REST calls return 200 immediately. Override per-deployment via ATANOR_WEB_UA.
WEB_USER_AGENT = os.getenv("ATANOR_WEB_UA") or (
    "ATANOR-KnowledgeBot/0.2 (+https://github.com/ATANOR-Demo; ATANOR knowledge grounding)"
)

# Small TTL cache so repeated questions don't re-hit Wikipedia (cuts latency and
# avoids 429 rate-limiting). Keyed by request URL.
_WIKI_CACHE: dict[str, tuple[float, Any]] = {}
_WIKI_CACHE_TTL = 900.0  # 15 min


def _wiki_get_json(url: str, *, timeout: float = 2.5, retries: int = 1) -> Any:
    """GET + parse JSON from a bounded public Wikipedia endpoint, with a tiny TTL
    cache and one backoff retry on 429/5xx. Returns {} on failure (never raises).

    Timeout/retries are kept tight on purpose: a failing lookup must give up in a
    few seconds, not ~15s (3 attempts × 5s), which is what made the answer feel
    'too slow' / return web_unreachable after a long wait."""
    now = time.monotonic()
    cached = _WIKI_CACHE.get(url)
    if cached and now - cached[0] < _WIKI_CACHE_TTL:
        return cached[1]
    request = urllib.request.Request(url, headers={"User-Agent": WEB_USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - bounded public API
                payload = json.loads(response.read().decode("utf-8"))
            _WIKI_CACHE[url] = (now, payload)
            return payload
        except urllib.error.HTTPError as exc:
            # 429 = rate-limited; an immediate retry just gets another 429, so give up
            # at once (fast fail) instead of sleeping. Only retry genuinely transient
            # 5xx server errors, and with a short backoff.
            if exc.code in (500, 502, 503) and attempt < retries:
                time.sleep(0.4 * (attempt + 1))
                continue
            return {}
        except Exception:
            return {}
    return {}


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
    "(\uB204\uAD6C|\uB204\uAD6C\uC57C|\uBB50\uC57C|\uBB34\uC5C7|\uC815\uC758|\uC54C\uB824\uC918|\uC124\uBA85|\uC65C|\uC774\uC720|\uC6D0\uB9AC|\uC5B4\uB5BB\uAC8C"
    "|\uC5B8\uC81C|\uC5B4\uB514|\uC5B4\uB290|\uBC1C\uBA85|\uBC1C\uACAC|\uB9CC\uB4E0|\uC9C0\uC740|\uC4F4"  # \uC5B8\uC81C \uC5B4\uB514 \uC5B4\uB290 \uBC1C\uBA85 \uBC1C\uACAC \uB9CC\uB4E0 \uC9C0\uC740 \uC4F4
    r"|\bwho\b|\bwhat\b|\bwhen\b|\bwhere\b|\bwhich\b|\bwhom\b"
    r"|tell me about|define|explain|why|how"
    r"|invented|discovered|founded|created|located|capital of|author of)",
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
        "(\uC5D0\\s*\uB300\uD574|\uC5D0\\s*\uB300\uD55C|\uC5D0\\s*\uAD00\uD574|\uC5D0\\s*\uAD00\uD55C|\uAD00\uB828\uD574|\uB204\uAD6C\uC57C|\uB204\uAD6C\uB2C8|\uB204\uAD6C|\uBB50\uC57C|\uBB34\uC5C7\uC774\uC57C|\uBB34\uC5C7|\uC54C\uB824\uC918|\uC124\uBA85\uD574\uC918|\uC124\uBA85|\uC18C\uAC1C\uD574\uC918|\uC815\uC758|who is|what is|tell me about|define|explain)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    # Strip question scaffolding around a fact so the ENTITY remains and the
    # encyclopedia search hits the right page ("who invented the telephone" ->
    # "the telephone"). English verbs + Korean equivalents.
    cleaned = re.sub(
        r"\b(who|when|where|which)\b\s*(was|were|is|are|did)?\s*"
        r"(invented|discovered|made|created|founded|wrote|built|designed|painted|born|located|the\s+author\s+of|the\s+capital\s+of)?",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        "(누가\\s*(발명|발견|만든|지은|쓴|세운|그린)(한|했어|했나|했지)?|언제\\s*(발명|발견|만들|생겼)|"
        "발명한|발견한|만든|지은|쓴|언제|어디(에|서|야)?|어느|수도(가|는)?)",
        " ",
        cleaned,
    )
    # Strip attribution nouns so an attribution question ("엔비디아 창립자가 누구야")
    # searches the ENTITY ("엔비디아"), landing on the main article — not a tangential
    # page like "엔비디아 GTC" that merely shares the term.
    cleaned = re.sub(
        r"(창립자|설립자|창업자|공동\s*창업자|발명자|발견자|저자|작곡가|작가|감독|창시자|설계자|개발자)\s*(은|는|이|가|를|을)?",
        " ",
        cleaned,
    )
    # attribution verbs + the generic head noun ("그린 사람", "설립한 사람", "이름")
    cleaned = re.sub(
        r"(그린|세운|설립한|창립한|창업한|작곡한|감독한|건설한|개발한|창시한|설계한)\b",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"\s(사람|인물|이름)\b", " ", cleaned)
    cleaned = re.sub(
        r"(그건|그게|그거|그것|이건|이게|이거|이것|왜\s*그런가요|왜\s*그래|왜|이유|원리|어떻게|how|why)",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    tokens = [token for token in re.split(r"\s+", cleaned.strip()) if token]
    trimmed = [_strip_korean_lookup_particle(token) for token in tokens]
    return " ".join(token for token in trimmed if token).strip() or query.strip()


def _strip_korean_lookup_particle(token: str) -> str:
    token = token.strip()
    if len(token) <= 1:
        return token
    # Strip only common lookup particles from Korean noun tokens. This turns
    # "중력의 법칙에 대해" into "중력 법칙" without using a generative model.
    return re.sub(r"(\uC740|\uB294|\uC774|\uAC00|\uC744|\uB97C|\uC758|\uC5D0|\uC5D0\uC11C|\uC73C\uB85C|\uB85C|\uACFC|\uC640|\uB3C4|\uB9CC)$", "", token)


def _lookup_terms(lookup: str) -> list[str]:
    terms: list[str] = []
    for token in re.split(r"\s+", lookup.lower()):
        token = re.sub(r"[^0-9a-zA-Z\uAC00-\uD7A3]+", "", token)
        if len(token) >= 2:
            terms.append(token)
    return terms


VISUAL_EVENT_CUE_RE = re.compile(
    r"(떨어|낙하|앉|나무|사과|머리|발견|관찰|움직|이동|회전|충돌|흐르|"
    r"fall|fell|falling|drop|dropped|tree|apple|sat|sitting|head|discover|observ|move|motion|orbit)",
    re.IGNORECASE,
)


def _split_source_sentences(text: str, *, max_len: int = 420) -> list[str]:
    cleaned = _strip_html(text)
    if not cleaned:
        return []
    # Keep sentence boundaries simple and deterministic; this is evidence
    # extraction for visual affordances, not generative summarization.
    rough = re.split(r"(?<=[.!?。])\s+|(?<=다\.)\s+|[\n\r]+", cleaned)
    sentences: list[str] = []
    for item in rough:
        sentence = re.sub(r"\s+", " ", item).strip()
        if len(sentence) < 18:
            continue
        if len(sentence) > max_len:
            sentence = sentence[:max_len].rstrip(" ,;:") + "..."
        sentences.append(sentence)
    return sentences


def extract_visual_event_sentences(text: str, *, limit: int = 3) -> list[str]:
    """Return source-local visual/motion sentences without topic templates."""

    results: list[str] = []
    seen: set[str] = set()
    for sentence in _split_source_sentences(text):
        if not VISUAL_EVENT_CUE_RE.search(sentence):
            continue
        key = sentence.casefold()
        if key in seen:
            continue
        seen.add(key)
        results.append(sentence)
        if len(results) >= max(1, limit):
            break
    return results


def _wikipedia_extract_for_page(title: str) -> str:
    page_slug = quote(title.replace(" ", "_"), safe="")
    page_url = (
        "https://ko.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&exintro=0"
        f"&format=json&titles={page_slug}"
    )
    request = urllib.request.Request(page_url, headers={"User-Agent": WEB_USER_AGENT})
    with urllib.request.urlopen(request, timeout=5) as response:  # nosec B310 - bounded public API endpoint
        body = json.loads(response.read().decode("utf-8"))
    pages = (body.get("query", {}) or {}).get("pages", {}) or {}
    for page in pages.values():
        extract = str(page.get("extract") or "").strip()
        if extract:
            return extract
    return ""


_INFOBOX_FIELDS = {
    "founded": ("설립자", "창립자", "창업자", "공동 창립자", "공동창립자", "founder", "founders", "founded by"),
    "invented": ("발명자", "발명가", "inventor", "inventors"),
    "directed": ("감독", "director"),
    "composed": ("작곡", "작곡가", "composer"),
}


def wikipedia_infobox_people(title: str, *, host: str, relation_key: str) -> str | None:
    """Read the named people from an article's infobox (e.g. a company's 설립자
    field) via the parse API. The extracts API strips infoboxes, so founders that
    live only in the infobox are invisible to prose scraping — this recovers them.
    Returns a comma-joined name string, or None. Deterministic, no LLM."""
    fields = _INFOBOX_FIELDS.get(relation_key)
    if not fields:
        return None
    api = f"https://{host}/w/api.php?action=parse&format=json&prop=wikitext&redirects=1&page={quote(title, safe='')}"
    body = _wiki_get_json(api)
    parse = (body or {}).get("parse", {}) or {}
    wikitext = parse.get("wikitext", {})
    wt = wikitext.get("*", "") if isinstance(wikitext, dict) else str(wikitext or "")
    if not wt:
        return None
    for field in fields:
        m = re.search(rf"\|\s*{re.escape(field)}\s*=\s*(.+)", wt)
        if not m:
            continue
        value = m.group(1)
        # Prefer [[wikilink]] display names; reject ref/citation noise.
        names = [n.split("|")[0].strip() for n in re.findall(r"\[\[([^\]]+)\]\]", value)]
        names = [n for n in names if n and "=" not in n and "{" not in n and 2 <= len(n) <= 24 and not re.search(r"\d", n)]
        if names:
            return ", ".join(dict.fromkeys(names[:5]))  # de-dup, cap at 5
    return None


def _wikipedia_visual_event_results(base_results: list[dict[str, Any]], *, limit: int = 2) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for result in base_results[:2]:
        title = str(result.get("title") or "").strip()
        if not title:
            continue
        try:
            extract = _wikipedia_extract_for_page(title)
        except Exception:
            continue
        for sentence_index, sentence in enumerate(extract_visual_event_sentences(extract, limit=2), start=1):
            enriched.append(
                {
                    "id": f"{result.get('id') or 'wikipedia'}-visual-{sentence_index}",
                    "title": f"{title} visual event evidence",
                    "url": result.get("url", ""),
                    "snippet": sentence,
                    "provider": "wikipedia",
                    "source_type": "encyclopedia_visual_event_extract",
                    "license_status": "reference_only",
                    "search_score": int(result.get("search_score") or 0) - sentence_index,
                    "query_terms_matched": int(result.get("query_terms_matched") or 0),
                    "normalized_query": result.get("normalized_query"),
                    "visual_evidence_enrichment": True,
                    "enrichment_basis": "source_page_sentence_visual_motion_cues",
                    "topic_scene_templates": False,
                    "renderer_may_infer_topic": False,
                    "particle_text": False,
                }
            )
            if len(enriched) >= max(0, limit):
                return enriched
    return enriched


def _wiki_host_for_query(query: str) -> str:
    # Use the Wikipedia edition that matches the query language. A Korean query
    # hits ko.wikipedia; an otherwise-Latin query hits en.wikipedia (searching
    # ko.wikipedia for "Eiffel Tower" returns irrelevant pages).
    return "ko.wikipedia.org" if re.search(r"[가-힣]", query or "") else "en.wikipedia.org"


def _norm_title(title: str) -> str:
    return re.sub(r"[\s_]+", "", str(title or "").lower())


def _wiki_rest_summary(term: str, host: str) -> dict[str, Any] | None:
    """Direct REST summary for an exact page title. Catches entities the action
    search misses (e.g. '빌게이츠' resolves to the '빌 게이츠' page) and is the most
    rate-limit-friendly Wikipedia endpoint. Returns a result row or None."""
    term = (term or "").strip()
    if not term:
        return None
    slug = quote(term.replace(" ", "_"), safe="")
    summary = _wiki_get_json(f"https://{host}/api/rest_v1/page/summary/{slug}", timeout=3.0)
    if not isinstance(summary, dict) or not summary:
        return None
    if str(summary.get("type") or "") == "disambiguation":
        return None
    extract = _strip_html(str(summary.get("extract") or ""))
    if not extract:
        return None
    title = _strip_html(str(summary.get("title") or term))
    page_url = (summary.get("content_urls", {}) or {}).get("desktop", {}).get("page") or f"https://{host}/wiki/{slug}"
    return {
        "id": "wikipedia-direct",
        "title": title,
        "url": page_url,
        "snippet": extract,
        "provider": "wikipedia",
        "source_type": "encyclopedia_summary",
        "license_status": "reference_only",
        "search_score": 250,
        "query_terms_matched": 2,
        "normalized_query": term,
    }


def _wiktionary_definition(term: str, *, korean: bool) -> dict[str, Any] | None:
    """A free DICTIONARY source (different content type from the encyclopedia) for
    plain definitional 'X가 뭐야' queries — real source diversity beyond Wikipedia
    while staying on a keyless, language-aware endpoint."""
    term = (term or "").strip()
    if not term:
        return None
    host = "ko.wiktionary.org" if korean else "en.wiktionary.org"
    slug = quote(term.replace(" ", "_"), safe="")
    body = _wiki_get_json(f"https://{host}/api/rest_v1/page/definition/{slug}", timeout=3.0)
    if not isinstance(body, dict) or not body:
        return None
    lang_key = "ko" if korean else "en"
    entries = body.get(lang_key) or next((v for v in body.values() if isinstance(v, list)), [])
    for entry in entries or []:
        for definition in entry.get("definitions", []) or []:
            text = _strip_html(str(definition.get("definition") or "")).strip()
            if len(text) >= 6:
                return {
                    "id": "wiktionary-1",
                    "title": term,
                    "url": f"https://{host}/wiki/{slug}",
                    "snippet": text,
                    "provider": "wiktionary",
                    "source_type": "dictionary_definition",
                    "license_status": "reference_only",
                    "search_score": 180,
                    "query_terms_matched": 1,
                    "normalized_query": term,
                }
    return None


_BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def brave_search(query: str, count: int = 6) -> list[dict[str, Any]]:
    """Real multi-source web search via the Brave Search API (a full web index, the way
    ChatGPT/Perplexity retrieve). Keyed by BRAVE_SEARCH_API_KEY (free tier ~2000/mo).
    Returns title/url/snippet rows; the referent-resonance gate downstream picks the
    best. Empty list when unconfigured or on error (caller falls back to Wikipedia)."""
    key = os.getenv("BRAVE_SEARCH_API_KEY")
    query = (query or "").strip()
    if not key or not query:
        return []
    url = (
        "https://api.search.brave.com/res/v1/web/search?"
        f"q={quote_plus(query)}&count={max(1, min(count, 10))}&search_lang=ko&country=KR"
    )
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "X-Subscription-Token": key, "User-Agent": WEB_USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=6) as response:  # nosec B310 - configured API
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # pragma: no cover - network/optional
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate((payload.get("web", {}) or {}).get("results", []) or [], start=1):
        snippet = _strip_html(str(item.get("description") or ""))
        if not snippet:
            continue
        url_ = str(item.get("url") or "")
        domain = re.sub(r"^https?://(www\.)?", "", url_).split("/")[0]
        rows.append(
            {
                "id": f"brave-{index}",
                "title": _strip_html(str(item.get("title") or "")),
                "url": url_,
                "snippet": snippet,
                "provider": f"brave:{domain}",
                "source_type": "web_search_api",
                "license_status": "reference_only",
                "search_score": (count - index + 1),
                "normalized_query": query,
            }
        )
    return rows


def tavily_search(query: str, count: int = 6) -> list[dict[str, Any]]:
    """Real web search via the Tavily API (LLM-optimized: returns clean page content).
    Keyed by TAVILY_API_KEY (free tier). Empty when unconfigured/on error."""
    key = os.getenv("TAVILY_API_KEY")
    query = (query or "").strip()
    if not key or not query:
        return []
    body = json.dumps(
        {"api_key": key, "query": query, "max_results": max(1, min(count, 10)), "search_depth": "basic"}
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.tavily.com/search", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:  # nosec B310 - configured API
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:  # pragma: no cover - network/optional
        return []
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(payload.get("results", []) or [], start=1):
        snippet = _strip_html(str(item.get("content") or ""))
        if not snippet:
            continue
        url_ = str(item.get("url") or "")
        domain = re.sub(r"^https?://(www\.)?", "", url_).split("/")[0]
        rows.append(
            {
                "id": f"tavily-{index}",
                "title": _strip_html(str(item.get("title") or "")),
                "url": url_,
                "snippet": snippet,
                "provider": f"tavily:{domain}",
                "source_type": "web_search_api",
                "license_status": "reference_only",
                "search_score": (count - index + 1),
                "normalized_query": query,
            }
        )
    return rows


def provider_api_search(query: str, count: int = 6) -> list[dict[str, Any]]:
    """Use whichever real search API is configured (Tavily → Brave). Empty if none."""
    if os.getenv("TAVILY_API_KEY"):
        rows = tavily_search(query, count)
        if rows:
            return rows
    if os.getenv("BRAVE_SEARCH_API_KEY"):
        return brave_search(query, count)
    return []


def has_search_api() -> bool:
    return bool(os.getenv("TAVILY_API_KEY") or os.getenv("BRAVE_SEARCH_API_KEY"))

# DuckDuckGo Lite rate-limits aggressive use, so cache results and back off after a
# block. The chat path is low-volume; sustained crawler-scale collection needs a real
# search API key (Brave/Serper) — env WEB_SEARCH_PROVIDER + key — not this endpoint.
_GENWEB_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_GENWEB_CACHE_TTL = 1800.0  # 30 min
_GENWEB_BACKOFF_UNTIL = 0.0


def general_web_search(query: str, count: int = 6) -> list[dict[str, Any]]:
    """Roam the OPEN web (not just Wikipedia) via DuckDuckGo Lite — a keyless, no-JS
    endpoint that returns diverse Korean+global sources (Naver blogs, Tistory, Namuwiki,
    news, Wikipedia). Returns title/url/snippet rows; the caller selects the best one by
    referent resonance + relevance, so a messy source is filtered out on our end."""
    global _GENWEB_BACKOFF_UNTIL
    query = (query or "").strip()
    if not query:
        return []
    now = time.monotonic()
    cached = _GENWEB_CACHE.get(query)
    if cached and now - cached[0] < _GENWEB_CACHE_TTL:
        return cached[1]
    if now < _GENWEB_BACKOFF_UNTIL:
        return []  # recently blocked → don't hammer; the caller falls back to Wikipedia
    try:
        body = urllib.parse.urlencode({"q": query}).encode("utf-8")
        request = urllib.request.Request(
            "https://lite.duckduckgo.com/lite/",
            data=body,
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "ko,en;q=0.8"},
        )
        with urllib.request.urlopen(request, timeout=6) as response:  # nosec B310 - public lite search
            html = response.read().decode("utf-8", "ignore")
    except Exception:  # pragma: no cover - network/optional
        _GENWEB_BACKOFF_UNTIL = now + 120.0
        return []
    links = re.findall(r"href=\"(https?://[^\"]+)\"\s+class='result-link'>(.*?)</a>", html, re.S)
    if not links:
        _GENWEB_BACKOFF_UNTIL = now + 120.0  # blocked / unexpected page → back off
    snippets = re.findall(r"class='result-snippet'>(.*?)</td>", html, re.S)
    rows: list[dict[str, Any]] = []
    for index, (url, title_html) in enumerate(links[: max(1, min(count, 10))]):
        if "duckduckgo.com" in url:
            continue
        title = _strip_html(title_html)
        snippet = _strip_html(snippets[index]) if index < len(snippets) else ""
        if not snippet:
            continue
        domain = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
        rows.append(
            {
                "id": f"web-{index + 1}",
                "title": title,
                "url": url,
                "snippet": snippet,
                "provider": f"web:{domain}",
                "source_type": "open_web_search",
                "license_status": "reference_only",
                "search_score": (count - index),
                "normalized_query": query,
            }
        )
    if rows:
        _GENWEB_CACHE[query] = (now, rows)
    return rows


_TRUSTED_DOMAINS = ("wikipedia.org", "namu.wiki", "namuwiki", "terms.naver.com", "doopedia", "britannica", "dbpedia")


def _rank_web_rows(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pick the best answer from a set of web rows by referent resonance + relevance,
    so 'our side filters the best out' no matter how noisy the sources are: the answer
    must be ABOUT the queried entity, share its terms, and prefer trusted/definitional
    sources. This is the quality filter that the raw DuckDuckGo merge lacked."""
    try:
        from packages.cgsr.cgsr.referent_resonance import query_subject_entity, answer_is_about_entity
        entity = query_subject_entity(query)
    except Exception:  # pragma: no cover
        entity, answer_is_about_entity = "", None  # type: ignore
    # Use the ENTITY's terms ('사랑'), not the raw query's ('사랑이란'), so a title
    # collision (the song '사랑이란') doesn't outscore the concept for '사랑이란 무엇인가'.
    lookup_terms = (_lookup_terms(entity) if len(entity) >= 2 else []) or _lookup_terms(_normalize_lookup_query(query))
    try:
        from packages.cgsr.cgsr.referent_resonance import infer_evidence_type
    except Exception:  # pragma: no cover
        infer_evidence_type = None  # type: ignore

    def score(row: dict[str, Any]) -> tuple:
        snippet = str(row.get("snippet", ""))
        text = f"{row.get('title','')} {snippet}".lower()
        about = 1
        if answer_is_about_entity is not None and len(entity) >= 2:
            about = 1 if answer_is_about_entity(entity, snippet) else 0
        # Exact-title match to the entity (사랑 == 사랑) beats a longer collided title
        # (사랑이란 the song) — the concept page is what a definitional query wants.
        title_norm = _norm_title(str(row.get("title") or ""))
        exact = 1 if title_norm == _norm_title(entity) else 0
        term_hits = sum(1 for t in lookup_terms if t and t.lower() in text)
        url = str(row.get("url", "")).lower()
        trust = 1 if any(d in url for d in _TRUSTED_DOMAINS) else 0
        looks_def = 1 if re.search(r"(이다|입니다|란\s|라고도|를 말한다|를 뜻한다|를 의미|is a|are )", snippet) else 0
        length_ok = 1 if 40 <= len(snippet) <= 600 else 0
        return (about, exact, term_hits, trust, looks_def, length_ok)

    return sorted(rows, key=score, reverse=True)


def _merge_web_candidates(query: str, count: int) -> list[dict[str, Any]]:
    """Best-of across sources: gather DIVERSE open-web rows (DDG → Naver/Tistory/Namu/
    news/Wikipedia) AND the precise Wikipedia entity page, then SELECT the best by
    on-topic terms, definition shape, source trust, and entity-anchoring — so a messy
    or off-topic source (the song '사랑이란' for '사랑이란 무엇인가', a random movie list) is
    filtered out on our end. Searches the SUBJECT ENTITY ('사랑'), not the raw question,
    so an exact title-collision ('사랑이란' the song) doesn't win. Falls back to
    Wikipedia-only when the open web is rate-limited."""
    try:
        from packages.cgsr.cgsr.referent_resonance import query_subject_entity, answer_is_about_entity
        entity = query_subject_entity(query) or query
    except Exception:  # pragma: no cover
        entity = query
        answer_is_about_entity = None  # type: ignore
    search_term = entity if 2 <= len(entity) <= 20 else query
    general = general_web_search(search_term, count + 2)
    wiki = wikipedia_search(query, count)  # keeps entity resolution / direct summary
    lookup_terms = _lookup_terms(_normalize_lookup_query(query)) or _lookup_terms(entity)

    def score(row: dict[str, Any]) -> tuple:
        snippet = str(row.get("snippet", ""))
        text = f"{row.get('title','')} {snippet}".lower()
        term_hits = sum(1 for t in lookup_terms if t and t.lower() in text)
        about = 1
        if answer_is_about_entity is not None and len(entity) >= 2:
            about = 1 if answer_is_about_entity(entity, snippet) else 0
        url = str(row.get("url", "")).lower()
        trust = 2 if any(d in url for d in _TRUSTED_DOMAINS) else (1 if row.get("provider") == "wikipedia" else 0)
        looks_def = 1 if re.search(r"(이다|입니다|란\s|라고도|를 말한다|를 뜻한다|를 의미)", snippet) else 0
        length_ok = 1 if len(snippet) >= 40 else 0
        return (about, term_hits, trust, looks_def, length_ok)

    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(general + wiki, key=score, reverse=True):
        key = _norm_title(str(row.get("title") or ""))[:30] + str(row.get("snippet") or "")[:30]
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
        if len(merged) >= count:
            break
    return merged


def _resolve_entity_by_type(entity: str, expected_type: str, host: str) -> dict[str, Any] | None:
    """Disambiguate an ambiguous name by surfing diversely: gather several candidate
    pages (action search) and pick the one whose TYPE matches what the question implies
    — '테슬라' + a founder question (→ ORG) resolves to '테슬라 (기업)', not '니콜라 테슬라'.
    This is the crawler-like breadth the user asked for, used for selection, not paste."""
    try:
        from packages.cgsr.cgsr.referent_resonance import infer_evidence_type
    except Exception:  # pragma: no cover - optional
        return None
    entity = (entity or "").strip()
    if not entity or expected_type in ("", "unknown"):
        return None
    api = (
        f"https://{host}/w/api.php?action=query&list=search&format=json&utf8=1"
        f"&srlimit=6&srsearch={quote_plus(entity)}"
    )
    body = _wiki_get_json(api)
    titles = [_strip_html(it.get("title") or "") for it in (body.get("query", {}).get("search", []) or [])][:6]
    if entity not in titles:
        titles.insert(0, entity)
    first_valid: dict[str, Any] | None = None
    for title in titles[:6]:
        row = _wiki_rest_summary(title, host)
        if not row:
            continue
        if first_valid is None:
            first_valid = row
        if infer_evidence_type(row["snippet"]) == expected_type:
            return row  # first type-matching candidate wins
    return first_valid


def _diverse_fallback_rows(query: str, lookup: str, lookup_terms: list[str], primary_host: str) -> list[dict[str, Any]]:
    """When the action search finds nothing, harvest from several keyless sources
    (direct Wikipedia summary in both language editions + Wiktionary) so a query
    isn't dead just because the strict title search missed."""
    korean = primary_host.startswith("ko")
    other_host = "en.wikipedia.org" if korean else "ko.wikipedia.org"
    # Candidate page titles: the cleaned lookup, plus each multi-char term.
    candidates: list[str] = []
    for cand in [lookup, *lookup_terms, query.strip()]:
        cand = (cand or "").strip()
        if cand and cand not in candidates:
            candidates.append(cand)
    rows: list[dict[str, Any]] = []
    for host in (primary_host, other_host):
        for cand in candidates[:4]:
            row = _wiki_rest_summary(cand, host)
            if row:
                rows.append(row)
                break
        if rows:
            break
    if not rows:
        for cand in candidates[:2]:
            wk = _wiktionary_definition(cand, korean=korean)
            if wk:
                rows.append(wk)
                break
    return rows


def wikipedia_search(query: str, count: int = 5) -> list[dict[str, Any]]:
    lookup = _normalize_lookup_query(query)
    lookup_terms = _lookup_terms(lookup)
    bounded_count = max(1, min(count, 10))
    wiki_host = _wiki_host_for_query(query)
    api_url = (
        f"https://{wiki_host}/w/api.php?action=query&list=search&format=json&utf8=1"
        f"&srlimit={max(bounded_count, 8)}&srsearch={quote_plus(lookup)}"
    )
    body = _wiki_get_json(api_url)
    results: list[dict[str, Any]] = []
    for index, item in enumerate((body.get("query", {}).get("search", []) or [])[: max(bounded_count, 8)], start=1):
        title = _strip_html(item.get("title") or lookup)
        page_slug = quote(title.replace(" ", "_"), safe="")
        page_url = f"https://{wiki_host}/wiki/{page_slug}"
        snippet = _strip_html(item.get("snippet") or "")
        if index <= 2:
            summary_url = f"https://{wiki_host}/api/rest_v1/page/summary/{page_slug}"
            summary = _wiki_get_json(summary_url)
            if isinstance(summary, dict) and summary:
                snippet = _strip_html(summary.get("extract") or snippet)
                page_url = summary.get("content_urls", {}).get("desktop", {}).get("page") or page_url
        if title and snippet:
            haystack = f"{title} {snippet}".lower()
            term_hits = sum(1 for term in lookup_terms if term in haystack)
            results.append(
                {
                    "id": f"wikipedia-{index}",
                    "title": title,
                    "url": page_url,
                    "snippet": snippet,
                    "provider": "wikipedia",
                    "source_type": "encyclopedia_search",
                    "license_status": "reference_only",
                    "search_score": (term_hits * 100) + (bounded_count - min(index, bounded_count) + 1),
                    "query_terms_matched": term_hits,
                    "normalized_query": lookup,
                }
            )
    results.sort(key=lambda result: (-int(result.get("query_terms_matched") or 0), -int(result.get("search_score") or 0), str(result.get("title") or "")))
    primary_limit = bounded_count - 1 if bounded_count >= 3 else bounded_count
    bounded_results = results[:primary_limit]
    enrichment_budget = 1 if bounded_count >= 3 else 0
    if enrichment_budget:
        for enriched in _wikipedia_visual_event_results(bounded_results, limit=enrichment_budget):
            if len(bounded_results) >= bounded_count:
                break
            bounded_results.append(enriched)
    if len(bounded_results) < bounded_count:
        for result in results[primary_limit:bounded_count]:
            if len(bounded_results) >= bounded_count:
                break
            bounded_results.append(result)
    # Precision + disambiguation: the action search ranks by term frequency, so a
    # person/entity query ("빌게이츠") can surface a tangential page ("빌게이츠꽃등에", a
    # fly). The exact-title REST summary is the authoritative page; and when the
    # question implies an entity TYPE (창업자 → ORG, 누구 → PERSON), resolve an ambiguous
    # name to the type-matching candidate (테슬라 + 창업자 → 테슬라(기업), not 니콜라 테슬라)
    # by surfing several candidates. Prepend the result so it wins, deduped.
    try:
        from packages.cgsr.cgsr.referent_resonance import query_entity_type as _qet
        _entity_type = _qet(query)
    except Exception:  # pragma: no cover - optional
        _entity_type = "unknown"
    direct = None
    if _entity_type not in ("", "unknown"):
        direct = _resolve_entity_by_type(lookup, _entity_type, wiki_host)
    if not direct:
        direct = _wiki_rest_summary(lookup, wiki_host) or (
            _wiki_rest_summary(lookup_terms[0], wiki_host) if lookup_terms else None
        )
    if direct:
        seen_titles = {_norm_title(direct["title"])}
        merged = [direct]
        for row in bounded_results:
            if _norm_title(str(row.get("title") or "")) not in seen_titles:
                merged.append(row)
                seen_titles.add(_norm_title(str(row.get("title") or "")))
        bounded_results = merged[:bounded_count]
    # Diversity + robustness: if the strict action search found nothing (title
    # mismatch, or it was 429'd), harvest from direct summaries (both language
    # editions) and Wiktionary so the query still gets a real, cited source.
    if not bounded_results:
        bounded_results = _diverse_fallback_rows(query, lookup, lookup_terms, wiki_host)
    return bounded_results


def news_rss_search(query: str, count: int = 5) -> list[dict[str, Any]]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=ko&gl=KR&ceid=KR:ko"
    request = urllib.request.Request(url, headers={"User-Agent": WEB_USER_AGENT})
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
    if not is_fresh_search_query(clean_query) and is_knowledge_lookup_query(clean_query):
        # Multi-source via a real search API (Tavily/Brave) — a full web index, the way
        # ChatGPT/Perplexity retrieve — ranked by referent resonance so the best answer
        # is filtered out on our end. Falls back to the precise, type-resolved Wikipedia
        # path when no API key is configured (a single-endpoint DDG scrape was tried and
        # reverted — too noisy without a strong ranker).
        try:
            api_rows = provider_api_search(clean_query, bounded_count + 2)
            if api_rows:
                ranked = _rank_web_rows(clean_query, api_rows)[:bounded_count]
                return {
                    "provider": "search-api",
                    "query": clean_query,
                    "results": ranked,
                    "configured": True,
                    "bing_query_url": f"https://www.bing.com/search?q={quote_plus(clean_query)}",
                    "status": "ok",
                    "provider_status": provider_status(selected),
                }
        except Exception:
            pass
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
                "source_type": result.get("source_type", "web_search"),
                "visual_evidence_enrichment": bool(result.get("visual_evidence_enrichment")),
                "enrichment_basis": result.get("enrichment_basis"),
                "topic_scene_templates": bool(result.get("topic_scene_templates", False)),
                "renderer_may_infer_topic": bool(result.get("renderer_may_infer_topic", False)),
                "particle_text": bool(result.get("particle_text", False)),
            }
        )
    return evidence
