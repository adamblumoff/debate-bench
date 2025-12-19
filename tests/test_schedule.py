from __future__ import annotations

from debatebench.cli.run.schedule import build_pairs, derive_debate_seed


class DummyModel:
    def __init__(self, model_id: str):
        self.id = model_id


def test_build_pairs_balanced():
    models = [DummyModel("a"), DummyModel("b"), DummyModel("c")]
    pairs = build_pairs(models, balanced_sides=True)
    ids = {(a.id, b.id) for a, b in pairs}
    assert len(pairs) == 6
    assert ("a", "b") in ids
    assert ("b", "a") in ids


def test_build_pairs_unbalanced():
    models = [DummyModel("a"), DummyModel("b"), DummyModel("c")]
    pairs = build_pairs(models, balanced_sides=False)
    ids = {(a.id, b.id) for a, b in pairs}
    assert len(pairs) == 3
    assert ("a", "b") in ids
    assert ("b", "a") not in ids


def test_derive_debate_seed_deterministic():
    seed1 = derive_debate_seed("tag", "topic", "pro", "con", 0)
    seed2 = derive_debate_seed("tag", "topic", "pro", "con", 0)
    seed3 = derive_debate_seed("tag", "topic", "pro", "con", 1)
    assert seed1 == seed2
    assert seed1 != seed3
