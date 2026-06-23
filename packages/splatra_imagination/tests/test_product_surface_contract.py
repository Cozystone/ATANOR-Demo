from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_product_surface_keeps_orb_input_readable_and_lab_labels_out() -> None:
    status_card = (ROOT / "apps" / "web" / "app" / "AtanorUserStatusCard.tsx").read_text(encoding="utf-8")
    field = (ROOT / "apps" / "web" / "app" / "SplatraImaginationField.tsx").read_text(encoding="utf-8")

    assert 'mode="product"' in status_card
    assert 'interactive={false}' in status_card
    assert 'className="atanor-dashboard-imagination-field"' in status_card
    assert "atanor-hologram-composer" in status_card
    assert "useTypewriterText" in status_card
    assert "data-stage-layout" in status_card
    assert "requestedSceneChoreography" in status_card
    assert "sceneFocus={stageLayout === \"scene_focus\"}" in status_card
    assert "scenePlan={sceneChoreography}" in status_card
    assert "ParticleText" not in status_card
    assert "scenePlan?: ScenePlan | null" in field
    assert "type SceneTransform" in field
    assert "sceneBeatIndex" in field
    assert "sceneArchetype" in field
    assert "activeSceneBeatIndex" in field
    assert "sceneTransform" in field
    assert "data-scene-beat" in field
    assert "splatra-imagination-product-label" in field
    assert "imagination /" in field
    assert "imagination ·" not in field
    assert "flowFieldAngle" in field
    assert "drawParticleStroke" in field
    assert "SPLATRA Imagination Field" in field
    assert 'mode === "lab"' in field


def test_scene_focus_layout_moves_orb_without_hiding_input() -> None:
    css = (ROOT / "apps" / "web" / "app" / "globals.css").read_text(encoding="utf-8")

    assert '[data-stage-layout="scene_focus"] .hologram-voice-orb' in css
    assert '[data-stage-layout="scene_focus"] .atanor-hologram-speech' in css
    assert "atanor-hologram-composer" in css


def test_product_archetype_cycle_excludes_central_orb_body() -> None:
    field = (ROOT / "apps" / "web" / "app" / "SplatraImaginationField.tsx").read_text(encoding="utf-8")
    product_block = field.split("const PRODUCT_ARCHETYPES", 1)[1].split("];", 1)[0]

    assert '"orb"' not in product_block
    assert '"constellation"' in product_block
    assert '"city_block"' in product_block
    assert '"circuit"' in product_block
