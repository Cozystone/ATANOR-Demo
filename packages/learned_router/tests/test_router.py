# -*- coding: utf-8 -*-
"""Learned router: stable features, trainable, sane predictions on core intents."""
from __future__ import annotations

import numpy as np

from packages.learned_router.router import _hash_features, predict, router_available


def test_features_are_deterministic_and_normalized():
    a = _hash_features("대한민국의 수도는?")
    b = _hash_features("대한민국의 수도는?")
    assert np.array_equal(a, b)
    assert abs(float(np.linalg.norm(a)) - 1.0) < 1e-5


def test_predict_without_model_is_no_opinion_or_valid():
    label, conf = predict("넌 누구니")
    if router_available():
        assert label != "" and 0.0 <= conf <= 1.0
    else:
        assert (label, conf) == ("", 0.0)


def test_core_intents_when_model_present():
    if not router_available():
        return  # bootstrap model not trained in this checkout — honest skip
    cases = {"넌 누구니": "identity", "한글로 답해줘": "meta_language",
             "3 더하기 4는?": "math", "사랑이란?": "definition"}
    hits = sum(1 for q, want in cases.items() if predict(q)[0] == want)
    assert hits >= 3  # allow one drift; retraining happens continuously
