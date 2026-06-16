from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DATA_ROOT = Path("data/cloud_brain")
SOURCES_PATH = DATA_ROOT / "web_seed_sources.json"
STATE_PATH = DATA_ROOT / "web_seed_feeder_state.json"
INBOX_DIR = DATA_ROOT / "inbox"

PRIVATE_NETWORKS = (
    ip_network("10.0.0.0/8"),
    ip_network("127.0.0.0/8"),
    ip_network("169.254.0.0/16"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("::1/128"),
    ip_network("fc00::/7"),
    ip_network("fe80::/10"),
)

DEFAULT_SOURCES = [
    {
        "source_id": "atanor_safe_demo_disabled",
        "name": "ATANOR Safe Demo Source",
        "url": "https://example.com/",
        "enabled": False,
        "source_type": "public_web",
        "trust_tier": "low",
        "crawl_interval_minutes": 1440,
        "last_fetched_at": None,
    }
]

DEFAULT_STATE = {
    "enabled": False,
    "last_run_at": None,
    "last_status": "idle",
    "sources_checked": 0,
    "fragments_created": 0,
    "fragments_rejected": 0,
    "last_error": None,
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip = False
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            cleaned = " ".join(data.split())
            if cleaned:
                self._chunks.append(cleaned)

    def text(self) -> str:
        return " ".join(self._chunks)


@dataclass(frozen=True)
class FeederResult:
    enabled: bool
    status: str
    sources_checked: int
    fragments_created: int
    fragments_rejected: int
    last_run_at: str | None
    last_error: str | None = None

    def to_state(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "last_run_at": self.last_run_at,
            "last_status": self.status,
            "sources_checked": self.sources_checked,
            "fragments_created": self.fragments_created,
            "fragments_rejected": self.fragments_rejected,
            "last_error": self.last_error,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_layout(root: Path = DATA_ROOT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "inbox").mkdir(parents=True, exist_ok=True)
    sources_path = root / "web_seed_sources.json"
    state_path = root / "web_seed_feeder_state.json"
    if not sources_path.exists():
        write_json(sources_path, DEFAULT_SOURCES)
    if not state_path.exists():
        write_json(state_path, DEFAULT_STATE)


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_sources(root: Path = DATA_ROOT) -> list[dict[str, Any]]:
    ensure_layout(root)
    sources = read_json(root / "web_seed_sources.json", DEFAULT_SOURCES)
    return sources if isinstance(sources, list) else []


def load_state(root: Path = DATA_ROOT) -> dict[str, Any]:
    ensure_layout(root)
    state = read_json(root / "web_seed_feeder_state.json", DEFAULT_STATE)
    if not isinstance(state, dict):
        return dict(DEFAULT_STATE)
    return {**DEFAULT_STATE, **state}


def save_state(state: dict[str, Any], root: Path = DATA_ROOT) -> None:
    write_json(root / "web_seed_feeder_state.json", {**DEFAULT_STATE, **state})


def is_safe_public_url(url: str) -> tuple[bool, str | None]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False, "URL must use http or https."
    if parsed.username or parsed.password:
        return False, "Authenticated URLs are not allowed."
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False, "URL host is missing."
    if host in {"localhost", "0.0.0.0"} or host.endswith(".local"):
        return False, "Local or internal hosts are not allowed."
    if "\\" in url or re.match(r"^[a-zA-Z]:\\", url):
        return False, "Local file paths are not allowed."
    try:
        address = ip_address(host)
    except ValueError:
        address = None
    if address is not None:
        if address.is_private or address.is_loopback or address.is_link_local or any(address in network for network in PRIVATE_NETWORKS):
            return False, "Private, loopback, and link-local IP ranges are not allowed."
    path_lower = parsed.path.lower()
    if any(marker in path_lower for marker in ("/login", "/signin", "/auth", "/account", "/session")):
        return False, "Pages that appear to require authentication are not allowed."
    return True, None


def normalize_text(raw: str) -> str:
    extractor = TextExtractor()
    try:
        extractor.feed(raw)
        text = extractor.text() or raw
    except Exception:
        text = raw
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:12_000]


def fetch_public_text(url: str, *, timeout_seconds: int = 10) -> str:
    ok, reason = is_safe_public_url(url)
    if not ok:
        raise ValueError(reason or "Unsafe URL")
    request = Request(url, headers={"User-Agent": "ATANOR-WebSeedFeeder/0.1 (+public-fragment-candidate)"})
    with urlopen(request, timeout=timeout_seconds) as response:
        content_type = str(response.headers.get("content-type", ""))
        if "text" not in content_type and "html" not in content_type and "json" not in content_type:
            raise ValueError(f"Unsupported content type: {content_type}")
        body = response.read(512_000)
    return normalize_text(body.decode("utf-8", errors="ignore"))


def should_fetch(source: dict[str, Any], now: datetime | None = None) -> bool:
    if not bool(source.get("enabled")):
        return False
    interval = int(source.get("crawl_interval_minutes") or 1440)
    last = source.get("last_fetched_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(str(last).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (now or datetime.now(timezone.utc)) - last_dt >= timedelta(minutes=max(1, interval))


def candidate_from_text(source: dict[str, Any], text: str, *, extracted_at: str | None = None) -> dict[str, Any]:
    extracted_at = extracted_at or utc_now()
    source_id = str(source.get("source_id") or "unknown_source")
    source_url = str(source.get("url") or "")
    title = str(source.get("name") or source_id)
    canonical = "\n".join([source_id, source_url, title, text])
    content_hash = hashlib.sha256(canonical.encode("utf-8", errors="ignore")).hexdigest()
    return {
        "fragment_id": f"candidate_{content_hash[:24]}",
        "content_hash": content_hash,
        "source_scope": "cloud",
        "privacy_scope": "public",
        "origin": "web_seed_feeder",
        "source_url": source_url,
        "source_id": source_id,
        "title": title,
        "text": text,
        "extracted_at": extracted_at,
        "trust_state": "unverified",
        "verification_state": "web_seed_pending",
        "ingestion_state": "pending",
        "created_by": "cloud_brain_web_seed_feeder",
    }


def write_candidate_fragment(fragment: dict[str, Any], root: Path = DATA_ROOT) -> bool:
    inbox = root / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    content_hash = str(fragment["content_hash"])
    path = inbox / f"candidate_{content_hash}.json"
    if path.exists():
        return False
    write_json(path, fragment)
    return True


def run_once(root: Path = DATA_ROOT, *, fetcher=fetch_public_text, force_enabled: bool = False) -> FeederResult:
    ensure_layout(root)
    state = load_state(root)
    now = utc_now()
    if not (bool(state.get("enabled")) or force_enabled):
        result = FeederResult(False, "disabled", 0, 0, 0, now, None)
        save_state(result.to_state(), root)
        return result

    checked = 0
    created = 0
    rejected = 0
    last_error: str | None = None
    sources = load_sources(root)
    updated_sources: list[dict[str, Any]] = []

    for source in sources:
        source = dict(source)
        if not should_fetch(source):
            updated_sources.append(source)
            continue
        checked += 1
        ok, reason = is_safe_public_url(str(source.get("url") or ""))
        if not ok:
            rejected += 1
            last_error = reason
            updated_sources.append(source)
            continue
        try:
            text = fetcher(str(source.get("url")))
            if len(text) < 80:
                rejected += 1
                last_error = "Fetched text was too short to create a public fragment candidate."
                updated_sources.append(source)
                continue
            fragment = candidate_from_text(source, text, extracted_at=now)
            if write_candidate_fragment(fragment, root):
                created += 1
            source["last_fetched_at"] = now
        except Exception as exc:
            rejected += 1
            last_error = str(exc)
        updated_sources.append(source)

    write_json(root / "web_seed_sources.json", updated_sources)
    status = "created_fragments" if created else ("error" if rejected and last_error else "no_new_payload")
    result = FeederResult(True, status, checked, created, rejected, now, last_error)
    save_state(result.to_state(), root)
    return result


def feeder_status(root: Path = DATA_ROOT) -> dict[str, Any]:
    ensure_layout(root)
    state = load_state(root)
    status = str(state.get("last_status") or "idle")
    if bool(state.get("enabled")) and status == "idle":
        status = "listening"
    return {
        "enabled": bool(state.get("enabled")),
        "status": status,
        "sources_checked": int(state.get("sources_checked") or 0),
        "fragments_created": int(state.get("fragments_created") or 0),
        "fragments_rejected": int(state.get("fragments_rejected") or 0),
        "last_run_at": state.get("last_run_at"),
        "last_error": state.get("last_error"),
        "inbox_path": str((root / "inbox").as_posix()),
        "writes_local_brain": False,
        "privacy_scope": "public_cloud_candidates_only",
    }


def watch(root: Path = DATA_ROOT, *, interval_seconds: int = 60) -> None:
    while True:
        run_once(root)
        time.sleep(max(5, interval_seconds))


def main() -> None:
    parser = argparse.ArgumentParser(description="ATANOR Cloud Brain Web Seed Feeder")
    parser.add_argument("--once", action="store_true", help="Run one feeder pass and exit.")
    parser.add_argument("--watch", action="store_true", help="Run feeder loop. Disabled by default.")
    parser.add_argument("--root", default=str(DATA_ROOT), help="Cloud Brain data root.")
    parser.add_argument("--force-enabled", action="store_true", help="Run once even if feeder state is disabled.")
    args = parser.parse_args()
    root = Path(args.root)
    if args.watch:
        watch(root)
        return
    result = run_once(root, force_enabled=args.force_enabled)
    print(json.dumps(result.to_state(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

