from __future__ import annotations

from packages.splatra_imagination.generator import ImaginationGenerator
from packages.splatra_imagination.models import ImaginationSeed


def _seed() -> ImaginationSeed:
    return ImaginationSeed(
        seed_id="deterministic",
        archetype="orb",
        randomness=0.42,
        valence=0.2,
        arousal=0.6,
        curiosity=0.5,
        particle_budget=500,
        created_at="2026-01-01T00:00:00Z",
    )


def test_deterministic_seed_output() -> None:
    generator = ImaginationGenerator(max_particle_budget=1000)

    a = generator.generate_frame(_seed())
    b = generator.generate_frame(_seed())

    assert a.frame_id == b.frame_id
    assert a.objects[0].particle_count == b.objects[0].particle_count
    assert a.objects[0].particles[0].to_dict() == b.objects[0].particles[0].to_dict()


def test_particle_budget_respected_and_not_verified_knowledge() -> None:
    frame = ImaginationGenerator(max_particle_budget=1000).generate_frame(_seed())
    item = frame.objects[0]

    assert 0 < item.particle_count <= 500
    assert item.is_verified_knowledge is False
    assert frame.label == "imagination"
    assert frame.source == "procedural"
    assert item.safety_flags["local_brain_write"] is False
