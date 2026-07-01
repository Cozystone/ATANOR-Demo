"""Holographic associative substrate: generalizes + uses wide context, beating the bigram baseline."""
from __future__ import annotations

from cgsr.holographic_lm import HolographicLM, resonance, tokens

# Shapes are decided by the NOUN, which sits BEFORE the shared token "IS". A last-token bigram
# therefore cannot tell round from square (it only sees "IS"); the holographic window can.
_NOUNS = {"ball": "round", "box": "square", "ring": "round", "cube": "square", "plate": "round", "brick": "square"}


def _train_corpus():
    corpus = []
    for mod in ("red", "blue"):
        for noun, shape in _NOUNS.items():
            corpus.append(f"{mod} {noun} IS {shape}")
    return corpus


def test_wide_context_disambiguates_where_bigram_cannot():
    lm = HolographicLM(window=3, seed=7).fit(_train_corpus())
    for noun, shape in _NOUNS.items():
        holo = lm.predict([noun, "IS"], candidates=["round", "square"])
        assert max(holo, key=holo.get) == shape, (noun, holo)
    # the bigram sees only "IS" → it is at chance (round and square tie)
    bg = lm.predict_bigram(["ball", "IS"])
    assert abs(bg.get("round", 0) - bg.get("square", 0)) < 1e-9


def test_generalizes_to_unseen_modifier_and_beats_bigram():
    lm = HolographicLM(window=3, seed=7).fit(_train_corpus())
    holo_correct = 0
    bigram_correct = 0
    for noun, shape in _NOUNS.items():
        ctx = ["green", noun, "IS"]  # "green" never appears in training
        holo = lm.predict(ctx, candidates=["round", "square"])
        if holo and max(holo, key=holo.get) == shape:
            holo_correct += 1
        bg = lm.predict_bigram(ctx)
        if bg and max(bg, key=bg.get) == shape:
            bigram_correct += 1
    holo_acc = holo_correct / len(_NOUNS)
    bigram_acc = bigram_correct / len(_NOUNS)
    assert holo_acc >= 0.9, holo_acc          # generalizes via the shared sub-context
    assert bigram_acc <= 0.6, bigram_acc      # last-token baseline is at chance
    assert holo_acc > bigram_acc + 0.3


def test_generation_stays_on_topic_coherence():
    # Two disjoint topics; a topic seed must not drift into the other topic's vocabulary.
    corpus = [
        "물고기 는 물 에서 헤엄친다", "물 은 강 에서 흐른다", "강 에서 물고기 가 헤엄친다",
        "로켓 은 우주 로 날아간다", "우주 에서 로켓 이 날아간다", "우주 는 넓다",
    ]
    lm = HolographicLM(window=3, seed=7).fit(corpus)
    out = lm.generate(["물고기", "는"], length=6)
    space_words = {"로켓", "우주"}
    assert not (set(out) & space_words), out  # stayed in the water topic


def test_no_fabrication_only_corpus_tokens():
    corpus = ["alpha beta gamma", "beta gamma delta"]
    lm = HolographicLM(window=2, seed=7).fit(corpus)
    vocab = set(tokens(" ".join(corpus)))
    out = lm.generate("alpha", length=8)
    assert set(out) <= vocab  # never emits a token not grounded in the corpus


def test_deterministic():
    a = HolographicLM(window=3, seed=7).fit(_train_corpus()).predict(["ball", "IS"], candidates=["round", "square"])
    b = HolographicLM(window=3, seed=7).fit(_train_corpus()).predict(["ball", "IS"], candidates=["round", "square"])
    assert a == b


def test_bind_unbind_recovers():
    lm = HolographicLM(dim=2048, seed=7)
    role = lm.space.vec("role")
    filler = lm.space.vec("filler")
    bound = lm.space.bind(role, filler)
    recovered = lm.space.unbind(bound, role)
    assert resonance(recovered, filler) > 0.99  # FHRR bind is invertible
