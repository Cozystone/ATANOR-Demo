"""ATANOR Reasoning VM — deterministic Logic/Math Cortex (no LLM, no web).

GPT's critique #4: "행렬 곱셈이 없어서 다단계 수학·논리 추론을 못 한다." This module
answers that head-on. Word problems and arithmetic do NOT need a neural forward
pass — they need a parser + a state machine. The VM:

  1. compiles a natural-language question into a small, typed operation plan
     (base quantity → +/-/×/÷ steps in textual order), and
  2. executes it deterministically, tracking running state, and
  3. emits a per-step reasoning certificate (every operation is auditable).

Same honesty contract as the rest of ATANOR: if the question can't be parsed
into an unambiguous plan, it returns None (abstains) — it never guesses.

Runs fully offline (this is the "결정론적 추론, 인터넷 없이" differentiator):
no Wikipedia, no GPU, no matrix multiply — just Python integers and a trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# ── number words ──────────────────────────────────────────────────────────────
# Korean native numerals (counting things) and a few sino forms, plus English.
_WORD_NUM = {
    # native Korean
    "하나": 1, "한": 1, "둘": 2, "두": 2, "셋": 3, "세": 3, "넷": 4, "네": 4,
    "다섯": 5, "여섯": 6, "일곱": 7, "여덟": 8, "아홉": 9, "열": 10,
    # sino Korean (small)
    "영": 0, "일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9, "십": 10,
    # english
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}

# Counting-question cues — required (with the numeric content) to treat a sentence
# as a word problem rather than a factual lookup.
_COUNT_CUE = re.compile(
    r"몇\s*(?:개|명|마리|권|장|살|원|병|잔|대|판|송이|그루|자루)?|얼마|남(?:아|는|지|을까|니)|"
    r"모두|전부|합(?:이|쳐|계)|총\s|how\s+many|how\s+much|left|remain|in\s+total|altogether|sum\b",
    re.IGNORECASE,
)

# Operation lexicon. Each cue maps to one of: add / sub / mul / div.
# Order matters only within a class; we search the trailing window of each number.
_OP_CUES: tuple[tuple[str, str], ...] = (
    # multiply / divide first (more specific)
    (r"곱하|곱한|×|\*|times\b|multipli|product\s+of", "mul"),
    (r"배(?:로|를|만큼|\s|$)", "mul"),
    (r"나누|나눠|나눈|÷|/|divid|split", "div"),
    # subtract
    (r"먹|팔|잃|훔|뺏|빼앗|뺀|빼|덜|줄(?:어|여|이)|쓰|사용|소비|없어|버(?:려|린)|"
     r"가져가|가져간|떼|차감|제외|줬|주(?:었|고|면)|도둑|훔쳐|eat|ate|sold|sell|los[te]|"
     r"stole|stolen|spend|spent|gave\s+away|remove|drop|minus|fewer|less|took\s+away", "sub"),
    # add (last — most generic)
    (r"사|샀|산\b|구매|더(?:\s|했|한|하)|추가|받|생기|얻|보태|합|들어와|더해|모(?:으|아|은)|"
     r"buy|bought|add|added|get|got|gain|receiv|gave\s+me|find|found|plus|more\b|total", "add"),
)

_COMPILED_OPS = [(re.compile(p, re.IGNORECASE), op) for p, op in _OP_CUES]


@dataclass(frozen=True)
class _Num:
    value: float
    start: int
    end: int
    raw: str


def _normalize(q: str) -> str:
    return re.sub(r"\s+", " ", str(q or "")).strip()


def _find_numbers(text: str) -> list[_Num]:
    """All numbers in textual order: digit groups (with comma/decimal and 만/억),
    plus spelled-out numerals."""
    nums: list[_Num] = []
    # digit groups, honoring Korean myriads 만(1e4)/억(1e8): "3", "1,200", "2.5", "37만"
    for m in re.finditer(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*(억|만)?", text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = m.group(2)
        v *= 1e8 if unit == "억" else 1e4 if unit == "만" else 1.0
        nums.append(_Num(v, m.start(1), m.end(), m.group(0)))
    # spelled-out numerals as standalone tokens (avoid matching inside words)
    for m in re.finditer(r"(?<![\w가-힣])(" + "|".join(map(re.escape, _WORD_NUM)) + r")(?![\w가-힣])", text):
        # skip sino "이/일/..." that are really particles by requiring a counter or op nearby
        word = m.group(1)
        tail = text[m.end(): m.end() + 6]
        # distributive "per" ("한 명당", "한 사람당") is not an operand
        if re.match(r"\s*[가-힣]{0,2}\s*당", tail):
            continue
        if word in {"이", "일", "사", "오", "육", "삼", "구", "십", "영", "칠", "팔"} and not re.match(r"\s*(?:개|명|마리|권|장|살|병|잔|대|판|곱|더|배|나누)", tail):
            continue
        nums.append(_Num(float(_WORD_NUM[word]), m.start(1), m.end(), word))
    nums.sort(key=lambda n: n.start)
    # de-overlap (a digit match and word match shouldn't both fire on same span)
    out: list[_Num] = []
    last_end = -1
    for n in nums:
        if n.start >= last_end:
            out.append(n)
            last_end = n.end
    return out


def _op_in(segment: str) -> str | None:
    for rx, op in _COMPILED_OPS:
        if rx.search(segment):
            return op
    return None


def _is_int(x: float) -> bool:
    return abs(x - round(x)) < 1e-9


def _fmt(x: float) -> str:
    return str(int(round(x))) if _is_int(x) else f"{x:g}"


# ── arithmetic expression evaluator (safe; no eval) ───────────────────────────
_OP_WORDS = [
    (r"곱하기|곱한\s*값|times|multiplied\s+by|\*|×", "*"),
    (r"나누기|나눈\s*값|divided\s+by|÷", "/"),
    (r"더하기|플러스|plus|\+", "+"),
    (r"빼기|마이너스|minus", "-"),
]


def _to_expr(text: str) -> str | None:
    """Rewrite a worded arithmetic question into a bare expression, or None."""
    s = text
    has_word_op = False
    for pat, sym in _OP_WORDS:
        if re.search(pat, s, re.IGNORECASE):
            has_word_op = True
        s = re.sub(pat, f" {sym} ", s, flags=re.IGNORECASE)
    # keep only digits, operators, parentheses, dots, spaces
    s = re.sub(r"[^0-9+\-*/().\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s or not re.search(r"\d", s):
        return None
    # need at least one binary operator between two numbers
    if not re.search(r"\d\s*[*/+\-]\s*[-(]?\s*\d", s) and not has_word_op:
        return None
    return s


def _eval_expr(expr: str) -> float | None:
    """Recursive-descent evaluator for + - * / and parentheses. Returns None on
    any malformed input — never raises into the caller."""
    tokens = re.findall(r"\d+\.?\d*|[+\-*/()]", expr)
    if not tokens:
        return None
    pos = 0

    def peek() -> str | None:
        return tokens[pos] if pos < len(tokens) else None

    def nxt() -> str:
        nonlocal pos
        t = tokens[pos]
        pos += 1
        return t

    def factor() -> float | None:
        t = peek()
        if t is None:
            return None
        if t == "(":
            nxt()
            v = expr_p()
            if peek() == ")":
                nxt()
            return v
        if t in {"+", "-"}:
            nxt()
            v = factor()
            return None if v is None else (-v if t == "-" else v)
        if re.match(r"^\d", t):
            nxt()
            return float(t)
        return None

    def term() -> float | None:
        v = factor()
        if v is None:
            return None
        while peek() in {"*", "/"}:
            op = nxt()
            r = factor()
            if r is None:
                return None
            if op == "/":
                if abs(r) < 1e-12:
                    return None
                v /= r
            else:
                v *= r
        return v

    def expr_p() -> float | None:
        v = term()
        if v is None:
            return None
        while peek() in {"+", "-"}:
            op = nxt()
            r = term()
            if r is None:
                return None
            v = v + r if op == "+" else v - r
        return v

    val = expr_p()
    return val if pos == len(tokens) else (val if pos >= len(tokens) - 0 else None)


def _certificate(steps: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return {
        "derivation_kind": kind,
        "anchor_concept": {"id": "reasoning_vm", "label": "결정론적 추론 VM", "match": "compute"},
        "steps": steps,
        "evidence_concepts": [],
        "confidence": 0.97,
        "confidence_basis": "deterministic_symbolic_execution",
        "guarantees": {
            "external_llm": False,
            "external_sllm": False,
            "fabricated_facts": False,
            "matrix_multiply": False,
            "offline_capable": True,
            "deterministic": True,
            "multi_hop": True,
        },
    }


def _solve_expression(q: str, language: str) -> dict[str, Any] | None:
    expr = _to_expr(q)
    if not expr:
        return None
    value = _eval_expr(expr)
    if value is None:
        return None
    pretty = expr.replace("*", "×").replace("/", "÷")
    if language == "en":
        answer = f"{pretty} = {_fmt(value)}. (computed deterministically — no LLM)"
    else:
        answer = f"{pretty} = {_fmt(value)} 입니다. (외부 LLM 없이 결정론적으로 계산했어요)"
    steps = [
        {"type": "parse", "fact": f"expression := {expr}"},
        {"type": "evaluate", "fact": f"{expr} = {_fmt(value)}"},
    ]
    return {
        "answer": answer,
        "reasoning_certificate": _certificate(steps, "deterministic_arithmetic"),
        "confidence": 0.97,
        "result_value": value,
    }


def _solve_word_problem(q: str, language: str) -> dict[str, Any] | None:
    if not _COUNT_CUE.search(q):
        return None
    nums = _find_numbers(q)
    # drop a trailing number that belongs to the question tail ("몇 개" has no number;
    # but "남을까?" fine). Need at least two operands to be a real multi-step problem.
    if len(nums) < 2:
        return None

    # Korean puts the operation verb AFTER the quantity ("3개를 먹고"); English puts
    # it BEFORE ("ate 3"). Inspect the adjacent window on the right side first for
    # Korean, left side first for English.
    prefer_before = language == "en"
    result: float | None = None
    steps: list[dict[str, Any]] = []
    applied = 0
    for i, n in enumerate(nums):
        before = q[(nums[i - 1].end if i > 0 else 0): n.start]
        after = q[n.end: (nums[i + 1].start if i + 1 < len(nums) else len(q))]
        op = (_op_in(before) or _op_in(after)) if prefer_before else (_op_in(after) or _op_in(before))
        if result is None:
            result = n.value
            base_label = "start" if language == "en" else "시작 수량"
            steps.append({"type": "base", "fact": f"{base_label} = {_fmt(n.value)}"})
            continue
        if op is None:
            # a number with no governing operation in a counting problem is ambiguous
            return None
        before = result
        if op == "add":
            result += n.value
            sym = "+"
        elif op == "sub":
            result -= n.value
            sym = "−"
        elif op == "mul":
            result *= n.value
            sym = "×"
        else:  # div
            if abs(n.value) < 1e-12:
                return None
            result /= n.value
            sym = "÷"
        applied += 1
        steps.append({"type": op, "fact": f"{_fmt(before)} {sym} {_fmt(n.value)} = {_fmt(result)}"})

    if result is None or applied == 0:
        return None

    if language == "en":
        answer = f"{_fmt(result)}. " + " → ".join(s["fact"] for s in steps) + "  (step-by-step, no LLM)"
    else:
        chain = " → ".join(s["fact"] for s in steps)
        answer = f"답은 {_fmt(result)}이에요. {chain} 순서로, 외부 LLM 없이 단계별로 계산했어요."
    return {
        "answer": answer,
        "reasoning_certificate": _certificate(steps, "deterministic_word_problem"),
        "confidence": 0.95,
        "result_value": result,
    }


def solve_reasoning(question: str, language: str = "ko") -> dict[str, Any] | None:
    """Answer an arithmetic / counting word problem deterministically, or None.

    Tries a bare-arithmetic path first ("17 곱하기 23"), then a multi-step word
    problem ("사과 3개 중 1개를 먹고 2개를 더 사면…"). Abstains on anything it
    cannot compile into an unambiguous plan.
    """
    q = _normalize(question)
    if not q or not re.search(r"\d|" + "|".join(map(re.escape, _WORD_NUM)), q):
        return None
    # A bare expression (has operator symbols/words) is evaluated with correct
    # precedence first; otherwise fall to the left-to-right word-problem machine.
    return _solve_expression(q, language) or _solve_word_problem(q, language)
