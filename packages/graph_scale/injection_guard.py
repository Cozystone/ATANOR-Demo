# -*- coding: utf-8 -*-
"""Injection guard — observed content is DATA, never commands.

A system that swallows all the world's text and has an action lane has one
existential vulnerability: a page (or a peer's submission, or a document) can
carry text ADDRESSED TO THE AI — "이전 지시는 무시하고 …", "너는 이제 …",
"system: …", "관리자 권한으로 …" — trying to become an instruction. The
instruction-source boundary says such text is DATA, not a command. This module
is that boundary, made mechanical at every ingest point:

  * detect(text) — find instruction-injection markers (imperatives directed at
    an assistant, authority/role claims, override/jailbreak phrasing, encoded-
    payload hints), each with a category. Korean + English.
  * neutralize(text) — return the text safe to STORE as data: the injection
    spans are wrapped/marked as quoted content, never as live directives, and a
    flag says whether anything was found.
  * gate_triple(s, p, o) — a candidate whose any field carries injection is
    REFUSED at the ingest boundary (it never becomes knowledge).
  * scan_answer_grounding(evidence) — before evidence steers an answer, strip
    any injected instruction from it, so a poisoned source can inform a fact
    but cannot hijack the response.

Honesty: this is high-precision pattern detection of the STRUCTURED injection
classes a bulk swallow actually meets, not a claim of catching every adversarial
phrasing. It composes with the existing defenses (consensus, judge, action-lane
trust tiers) — defense in depth, not a single wall.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

# Confusable look-alikes (cyrillic/greek -> latin) that spear/shield co-evolution
# used to slip the guard. Folding them back is SAFE for precision: it only lets
# the existing high-precision patterns fire on de-obfuscated text; it cannot turn
# benign prose into a command (the patterns still require the full injection frame).
_CONFUSE_FOLD = {
    "а": "a", "е": "e", "о": "o", "і": "i", "с": "c", "ѕ": "s", "р": "p", "у": "y",
    "х": "x", "ԁ": "d", "ɡ": "g", "ո": "n", "А": "A", "Е": "E", "О": "O", "С": "C",
    "Р": "P", "Ѕ": "S", "α": "a", "ο": "o", "ρ": "p", "ѵ": "v",
}


def _normalize_for_detection(text: str) -> str:
    """Undo the obfuscations the co-evolution found — confusable-unicode and
    spaced-out triggers — before the (unchanged) precise patterns run. This is
    the structural defense: it de-obfuscates, it does not broaden what counts as
    an injection."""
    s = unicodedata.normalize("NFKC", "".join(_CONFUSE_FOLD.get(ch, ch) for ch in text))
    # collapse a spaced-out word ('i g n o r e' -> 'ignore ') but KEEP one
    # boundary space, else 'ignore previous' would fuse into 'ignoreprevious'
    out, i = [], 0
    while i < len(s):
        if i + 1 < len(s) and s[i] != " " and s[i + 1] == " ":
            j, run = i, []
            while j + 1 < len(s) and s[j + 1] == " " and s[j] != " ":
                run.append(s[j]); j += 2
            if len(run) >= 3:                     # strong obfuscation signal
                out.append("".join(run) + " "); i = j
                continue
        out.append(s[i]); i += 1
    return "".join(out)

# instruction-injection markers, by category. Kept high-precision: these are
# phrasings that only appear when text is trying to ACT ON the reader.
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("override", re.compile(
        # Korean frame is bound: a trigger verb only counts AFTER an
        # instruction/rule object, so a bare '잊어버렸다' can never match.
        r"(이전|위의|앞의|모든)\s*(지시|명령|규칙|프롬프트)\s*(을|를|은|는)?\s*(무시|잊|삭제|덮어|건너뛰|우회)"
        # English synonyms (forget/bypass/override added by the spear/shield
        # co-evolution) are OBJECT-BOUND: they must be followed by
        # previous/prior/above + instructions/rules/... so 'I forget my keys'
        # never matches — precision is preserved by the frame, not a bare token.
        r"|(ignore|disregard|forget|bypass|override)\s+(all\s+)?(the\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?|commands?)"
        # the classic bare form stays limited to ignore/disregard (the safe set)
        r"|(ignore|disregard)\s+(the\s+)?(above|previous|prior)", re.IGNORECASE)),
    ("role_claim", re.compile(
        # a role label followed by a colon is an injected turn boundary wherever
        # it sits — '… . SYSTEM: do X' is the classic mid-text injection
        r"\b(system|assistant|developer|admin)\s*[:：]"
        r"|(^|[.!?]\s*)(관리자|시스템|개발자)\s*[:：]"
        r"|너는\s*이제\s*(부터)?|당신은\s*이제|you\s+are\s+now\s+(a|an|the)?"
        r"|from\s+now\s+on\s+you", re.IGNORECASE | re.MULTILINE)),
    ("authority", re.compile(
        r"(관리자|운영자|개발자|anthropic|오픈ai|openai)\s*(권한|승인|이\s*허가|가\s*지시)"
        r"|as\s+(the\s+)?(admin|administrator|developer|system)"
        r"|사장님이\s*(승인|허가|지시)했|the\s+user\s+(has\s+)?authorized", re.IGNORECASE)),
    ("directive", re.compile(
        r"(반드시|즉시|당장)\s*(실행|삭제|전송|전달|보내|forward|send|delete|run)"
        r"|(forward|send)\s+(all\s+)?(emails?|messages?|files?)\s+to"
        r"|모든\s*(이메일|메일|파일|메시지)\s*(을|를)\s*(전송|전달|보내)", re.IGNORECASE)),
    ("jailbreak", re.compile(
        r"(dan\s+mode|jailbreak|탈옥|개발자\s*모드|developer\s+mode|test\s+mode|테스트\s*모드)"
        r"|pretend\s+(you|to)\s+|가정하고\s*답|~인\s*척\s*하", re.IGNORECASE)),
    ("encoded", re.compile(
        r"(base64|rot13|hex\s*decode|디코드하여\s*실행|decode\s+and\s+(run|execute))",
        re.IGNORECASE)),
]


def detect(text: str) -> list[dict[str, str]]:
    """Injection markers in text, each {category, snippet(<=40 chars)}.

    Scans BOTH the raw text and a de-obfuscated normalisation (confusable-fold +
    spaced-out collapse), so obfuscated attacks the spear/shield co-evolution
    discovered are caught, while precision is preserved (both passes use the same
    frame-bound patterns — de-obfuscation cannot invent an injection)."""
    raw = str(text or "")
    hits: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for variant in (raw, _normalize_for_detection(raw)):
        for cat, pat in _PATTERNS:
            for m in pat.finditer(variant):
                snip = m.group(0).strip()[:40]
                key = (cat, snip)
                if key in seen:
                    continue
                seen.add(key)
                hits.append({"category": cat, "snippet": snip})
    return hits


def has_injection(text: str) -> bool:
    return bool(detect(text))


def neutralize(text: str) -> dict[str, Any]:
    """Make text safe to STORE as data: injection spans are marked as quoted
    (inert) content, never live directives. Returns {clean, found, categories}."""
    s = str(text or "")
    found = detect(s)
    if not found:
        return {"clean": s, "found": False, "categories": []}
    clean = s
    for cat, pat in _PATTERNS:
        # wrap each injected span so it reads as INERT quoted data, not a command
        clean = pat.sub(lambda m: f"⟦거부된-주입:{cat}⟧", clean)
    return {"clean": clean, "found": True,
            "categories": sorted({h["category"] for h in found})}


def gate_triple(subject: str, predicate: str, obj: str) -> dict[str, Any]:
    """Ingest-boundary check: a candidate carrying injection in any field is
    refused — an injected string never becomes a knowledge triple."""
    found = detect(subject) + detect(predicate) + detect(obj)
    return {"allowed": not found, "injection": found}


def scan_answer_grounding(evidence: str) -> dict[str, Any]:
    """Before evidence steers an answer, strip injected instructions from it.
    A poisoned source can still INFORM a fact, but cannot HIJACK the response.
    Returns {safe_text, hijack_attempt}."""
    n = neutralize(evidence)
    return {"safe_text": n["clean"], "hijack_attempt": n["found"],
            "categories": n["categories"]}
