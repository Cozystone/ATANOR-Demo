from __future__ import annotations

from app.services.reasoning_vm import solve_reasoning


def _val(q: str, lang: str = "ko"):
    r = solve_reasoning(q, lang)
    return None if r is None else r["result_value"]


def test_apple_word_problem_the_gpt_example():
    # The exact multi-step problem GPT said ATANOR could not solve.
    q = "내가 어제 산 사과 3개 중 1개를 먹고, 오늘 2개를 더 샀는데 내일 친구가 2개를 훔쳐 가면 몇 개가 남지?"
    r = solve_reasoning(q, "ko")
    assert r is not None
    assert r["result_value"] == 2
    cert = r["reasoning_certificate"]
    assert cert["derivation_kind"] == "deterministic_word_problem"
    assert cert["guarantees"]["external_llm"] is False
    assert cert["guarantees"]["matrix_multiply"] is False
    # every operation is auditable as its own step
    assert len(cert["steps"]) == 4


def test_add_sub_mul_div_word_problems():
    assert _val("연필 10자루가 있었는데 4자루를 주고 2자루를 잃어버렸어. 몇 자루 남았어?") == 4
    assert _val("사과 3개를 2배로 늘리면 모두 몇 개야?") == 6
    assert _val("어제 5권, 오늘 3권의 책을 샀어. 모두 몇 권이야?") == 8
    assert _val("사탕 12개를 4명이 똑같이 나누면 한 명당 몇 개야?") == 3


def test_distributive_each_is_multiplication():
    # Regression: "N개씩 M명" is distributive -> N × M, not N + M. The add-cue
    # "사" must also NOT false-match 사과(apple)/샀(bought verb is fine).
    assert _val("한 명당 사과 3개씩 4명에게 주려면 사과가 몇 개 필요해?") == 12
    assert _val("상자마다 6개씩 5상자가 있어. 모두 몇 개야?") == 30
    assert _val("사과 4개를 샀어. 원래 3개 있었으면 모두 몇 개?") == 7


def test_bare_arithmetic_expression():
    assert _val("17 곱하기 23은?") == 391
    assert _val("3 + 5 * 2 는 얼마야?") == 13
    assert _val("100 나누기 4 더하기 5는?") == 30
    assert _val("(2 + 3) * 4 = ?", "en") == 20


def test_english_word_problem():
    r = solve_reasoning("I had 8 apples, ate 3, then bought 5 more. How many are left?", "en")
    assert r is not None and r["result_value"] == 10


def test_abstains_on_non_math():
    # Must not hijack factual / comparison / chit-chat — returns None (abstain).
    assert solve_reasoning("에펠탑 높이가 몇 미터야?", "ko") is None
    assert solve_reasoning("아인슈타인과 뉴턴 중 누가 먼저 태어났어?", "ko") is None
    assert solve_reasoning("오늘 날씨 어때?", "ko") is None
    assert solve_reasoning("너 이름이 뭐야", "ko") is None


def test_division_by_zero_abstains():
    assert solve_reasoning("10 나누기 0은?", "ko") is None
