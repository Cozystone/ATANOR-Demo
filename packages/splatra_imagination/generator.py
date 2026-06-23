from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

from .archetypes import generate_archetype
from .emotion_bridge import imagination_controls
from .models import ARCHETYPES, Archetype, ImaginationFrame, ImaginationObject, ImaginationSeed, default_safety_flags
from .turbovec_bridge import compress_imagination_object


def deterministic_seed(value: str) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def select_archetype(seed_id: str, curiosity: float) -> Archetype:
    rng = random.Random(deterministic_seed(f"archetype:{seed_id}:{curiosity:.4f}"))
    index = int(rng.random() * len(ARCHETYPES)) % len(ARCHETYPES)
    return ARCHETYPES[index]


@dataclass
class ImaginationGenerator:
    max_particle_budget: int = 100_000
    default_product_budget: int = 1600
    default_lab_budget: int = 6500

    def generate_object(self, seed: ImaginationSeed, *, compress: bool = True) -> ImaginationObject:
        budget = max(1, min(int(seed.particle_budget), self.max_particle_budget))
        controls = imagination_controls(
            valence=seed.valence,
            arousal=seed.arousal,
            curiosity=seed.curiosity,
            speaking_energy=seed.speaking_energy,
            state=seed.state,
        )
        density = float(controls["density_multiplier"])
        count = max(16, min(budget, int(round(budget * density))))
        rng = random.Random(deterministic_seed(f"{seed.seed_id}:{seed.archetype}:{seed.randomness:.5f}"))
        particles = generate_archetype(seed.archetype, count, rng, controls)
        object_id = f"imag_{hashlib.sha1((seed.seed_id + seed.archetype).encode('utf-8')).hexdigest()[:16]}"
        item = ImaginationObject(
            object_id=object_id,
            archetype=seed.archetype,
            particles=particles,
            metadata={
                "seed": seed.to_dict(),
                "controls": controls,
                "label": "imagination",
                "source": "procedural",
                "not_verified_memory": True,
            },
            lod_level=seed.lod_target,
            safety_flags=default_safety_flags(),
            is_verified_knowledge=False,
        )
        if not compress:
            return item
        bridge = compress_imagination_object(item)
        return ImaginationObject(
            object_id=item.object_id,
            archetype=item.archetype,
            particles=item.particles,
            metadata={**item.metadata, "turbovec": bridge.to_dict()},
            compressed_ref=bridge.compressed_ref,
            lod_level=item.lod_level,
            safety_flags=item.safety_flags,
            is_verified_knowledge=False,
        )

    def generate_frame(self, seed: ImaginationSeed, *, compress: bool = True, include_particles: bool = True) -> ImaginationFrame:
        item = self.generate_object(seed, compress=compress)
        frame_hash = hashlib.sha1((seed.seed_id + item.object_id + seed.created_at).encode("utf-8")).hexdigest()[:16]
        return ImaginationFrame(
            frame_id=f"frame_{frame_hash}",
            objects=[item],
            controls=item.metadata.get("controls", {}),
            label="imagination",
            source="procedural",
            proof_only=True,
        )
