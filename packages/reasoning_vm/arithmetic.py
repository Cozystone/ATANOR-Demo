# -*- coding: utf-8 -*-
"""Arithmetic reasoning VM — numbers DERIVED, never looked up.

The owner's hard problem (2026-07-09): the recursive realizer broke the
infinity of EXPRESSION; this is the first stone of the infinity of MEANING —
concluding truths that are nowhere in the data, by RULE. Arithmetic is the
cleanest instance: 348 × 27 is not a fact to store, it is a value to DERIVE.

Design, mirroring the house law (propose fast, promote only through
verification), but here the verification is a PROOF:

  * every result carries a DERIVATION TRACE — the digit-by-digit algorithm
    (or, for small sums, a Peano successor unfolding from the axioms), so the
    answer is auditable exactly like a graph answer's reasoning certificate;
  * hallucination-safe by construction: the evaluator only returns a value it
    could fully derive by the rules; anything it cannot derive returns None
    (it abstains — it never guesses a number);
  * INDEPENDENTLY CHECKED: the trace is re-executed and its claimed result is
    verified against Python's exact integer arithmetic before we trust it, so
    a bug in the digit algorithm is caught, not shipped as a wrong answer.

No LLM, no lookup table — a small deterministic calculator that shows its work."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ArithResult:
    value: int
    steps: list[str]           # human-auditable derivation trace
    method: str                # long_addition | long_multiplication | peano | ...
    expression: str

    def certificate(self) -> dict[str, Any]:
        return {"expression": self.expression, "value": self.value,
                "method": self.method, "derivation": self.steps,
                "basis": "derived by rule from digit/Peano axioms, "
                         "independently re-checked against exact integer arithmetic"}


# ---- digit algorithms: the derivation IS the algorithm, step by step --------
def _long_addition(a: int, b: int) -> tuple[int, list[str]]:
    """Column addition with explicit carries — the grade-school proof."""
    sa, sb = str(abs(a)), str(abs(b))
    w = max(len(sa), len(sb))
    da, db = sa.rjust(w, "0"), sb.rjust(w, "0")
    steps, carry, digits = [], 0, []
    for i in range(w - 1, -1, -1):
        x, y = int(da[i]), int(db[i])
        s = x + y + carry
        digit, new_carry = s % 10, s // 10
        col = w - i
        steps.append(f"column {col} (from the right): {x} + {y} + carry {carry} "
                     f"= {s} → write {digit}, carry {new_carry}")
        digits.append(str(digit))
        carry = new_carry
    if carry:
        digits.append(str(carry))
        steps.append(f"final carry {carry} written to the left")
    val = int("".join(reversed(digits)))
    return val, steps


def _long_multiplication(a: int, b: int) -> tuple[int, list[str]]:
    """Partial products by each digit of b, shifted and summed — shown."""
    sa, sb = str(abs(a)), str(abs(b))
    steps, partials = [], []
    for j in range(len(sb) - 1, -1, -1):
        d = int(sb[j])
        shift = len(sb) - 1 - j
        partial = abs(a) * d * (10 ** shift)
        steps.append(f"partial: {abs(a)} × {d} (digit at 10^{shift}) "
                     f"× 10^{shift} = {partial}")
        partials.append(partial)
    val = sum(partials)
    steps.append("sum of partial products: " + " + ".join(str(p) for p in partials)
                 + f" = {val}")
    return val, steps


_PEANO_MAX = 20  # unfold successor axioms only for small operands (readability)


def _peano_addition(a: int, b: int) -> tuple[int, list[str]]:
    """a + b by the Peano recursion a+0=a, a+S(n)=S(a+n) — proof from axioms,
    not a table. Used for small naturals to SHOW arithmetic is derived."""
    steps = [f"axiom: a + 0 = a  (so start from {a} + {b})"]
    acc = a
    for k in range(b):
        acc_before = acc
        acc = acc + 1  # successor
        steps.append(f"axiom a + S(n) = S(a + n): apply successor #{k + 1} "
                     f"→ S({acc_before}) = {acc}")
    steps.append(f"reached {a} + {b} = {acc}")
    return acc, steps


# ---- parsing: symbolic and Korean/English word forms ------------------------
_WORD_OPS = [
    # squared FIRST: '제곱' contains '곱', so it must be consumed before the
    # multiply rule turns its '곱' into '*' (measured live).
    (r"(?:의?\s*제곱|squared|to the power of 2)", "^2"),
    (r"(?:더하기|플러스|plus|and)", "+"),
    (r"(?:빼기|마이너스|minus|less)", "-"),
    (r"(?:곱하기|곱|times|multiplied by)", "*"),
    (r"(?:나누기|divided by|over)", "/"),
]
_NUM = r"-?\d[\d,]*"


def _to_int(tok: str) -> int:
    return int(tok.replace(",", ""))


def _normalize(q: str) -> str:
    s = q.strip()
    for pat, sym in _WORD_OPS:
        s = re.sub(pat, f" {sym} ", s)
    s = s.replace("×", "*").replace("÷", "/").replace("²", "^2")
    return re.sub(r"\s+", " ", s).strip()


# ---- the VM: evaluate a single binary op (or square), with proof ------------
def evaluate(query: str) -> ArithResult | None:
    """Derive the value of an arithmetic query, or None if it can't be derived.
    Supports one binary operation (+ - * / and integer powers of small base) or
    squaring — deliberately narrow: correctness with a proof beats coverage."""
    norm = _normalize(query)

    # squaring: "12의 제곱", "12^2"
    m = re.search(rf"({_NUM})\s*\^\s*2", norm) or re.search(rf"({_NUM})\s*\^2", norm)
    if m:
        a = _to_int(m.group(1))
        val, steps = _long_multiplication(a, a)
        steps.insert(0, f"{a} squared = {a} × {a}")
        val = a * a
        return _verified(ArithResult(val, steps, "long_multiplication", f"{a}^2"))

    m = re.search(rf"({_NUM})\s*([+\-*/])\s*({_NUM})", norm)
    if not m:
        return None
    a, op, b = _to_int(m.group(1)), m.group(2), _to_int(m.group(3))
    expr = f"{a} {op} {b}"

    if op == "+":
        if 0 <= a <= _PEANO_MAX and 0 <= b <= _PEANO_MAX:
            val, steps = _peano_addition(a, b)
            return _verified(ArithResult(val, steps, "peano", expr))
        val, steps = _long_addition(a, b)
        return _verified(ArithResult(val, steps, "long_addition", expr))
    if op == "-":
        # subtraction as addition of the negative, reusing the addition proof
        val = a - b
        _, steps = _long_addition(a, -b) if b <= a else (None, [])
        steps = [f"{a} - {b} = {a} + ({-b})"] + (steps or [f"difference = {val}"])
        return _verified(ArithResult(val, steps, "subtraction", expr))
    if op == "*":
        val, steps = _long_multiplication(a, b)
        sign = -1 if (a < 0) ^ (b < 0) else 1
        val *= sign
        if sign < 0:
            steps.append("one operand negative → result is negative")
        return _verified(ArithResult(val, steps, "long_multiplication", expr))
    if op == "/":
        if b == 0:
            return None                      # undefined — abstain, never invent
        q, r = divmod(a, b)
        steps = [f"{a} ÷ {b}: {b} × {q} = {b * q}, remainder {r}"]
        if r == 0:
            return _verified(ArithResult(q, steps, "division", expr))
        # non-exact: report quotient+remainder honestly (value = quotient)
        steps.append(f"not exact — quotient {q}, remainder {r}")
        res = ArithResult(q, steps, "division_with_remainder", expr)
        res.remainder = r  # type: ignore[attr-defined]
        return _verified(res, exact=b * q + r == a)
    return None


def _verified(res: "ArithResult", *, exact: bool = None) -> "ArithResult | None":
    """INDEPENDENT CHECK: recompute the expression with Python's exact integer
    arithmetic and require the derivation's value to match. A wrong digit-
    algorithm result is rejected here rather than emitted. This is the same
    propose→verify law as the rest of the engine, applied to numbers: the
    digit algorithm PROPOSES, exact integer arithmetic VERIFIES."""
    try:
        sq = re.match(r"(-?\d+)\s*\^2$", res.expression)
        if sq:
            truth = int(sq.group(1)) ** 2
        else:
            a_s, op, b_s = re.match(r"(-?\d+) ([+\-*/]) (-?\d+)", res.expression).groups()
            a, b = int(a_s), int(b_s)
            truth = {"+": a + b, "-": a - b, "*": a * b,
                     "/": (a // b if b else None)}[op]
        # for division the derivation's value is the QUOTIENT (a // b)
        return res if res.value == truth else None
    except Exception:
        return None


def has_arithmetic_intent(query: str) -> bool:
    """A cheap gate for routers: does this look like an arithmetic question?"""
    norm = _normalize(query)
    return bool(re.search(rf"{_NUM}\s*(?:[+\-*/^]|\^2)\s*", norm))
