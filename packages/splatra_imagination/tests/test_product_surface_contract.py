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
    assert "sceneNarrationBeats" in status_card
    assert "beat.speech_cue !== false" in status_card
    assert "firstSceneNarration" in status_card
    assert "sceneSpeechBeatIndex" in status_card
    assert "setSceneSpeechBeatIndex(nextSpeechBeat.beatIndex)" in status_card
    assert "data-scene-speech-beat" in status_card
    assert "activeSpeechBeatIndex={sceneSpeechBeatIndex}" in status_card
    assert "speech_cue: bool = True" in (ROOT / "packages" / "splatra_imagination" / "scene_choreography.py").read_text(encoding="utf-8")
    assert "scene_group_id: str = \"\"" in (ROOT / "packages" / "splatra_imagination" / "scene_choreography.py").read_text(encoding="utf-8")
    assert "splatraStateForInnerVoice" in status_card
    assert '"/api/inner-voice/generate-frame"' in status_card
    assert '"/api/inner-voice/emit"' not in status_card
    assert "append_to_log: true" in status_card
    assert "splatra_state: splatraStateForInnerVoice" in status_card
    assert "sceneSpeechStartedAt" in status_card
    assert "data-speech-placement" in status_card
    assert "data-self-narration-placement" in status_card
    assert "selfNarrationPlacement" in status_card
    assert "selfNarrationRef" in status_card
    assert "requestedTextAnchor" in status_card
    assert "requestedLayoutIntent" in status_card
    assert "scenePlanBlockers" in status_card
    assert "rectsOverlap" in status_card
    assert "data-layout-decision" in status_card
    assert "requestedLayoutDecision" in status_card
    assert "requestedLayoutBasis" in status_card
    assert "DashboardLayoutMetrics" in status_card
    assert "dashboardLayoutMetrics" in status_card
    assert "speechUpperLeftTopVh" in status_card
    assert "selfNarrationMaxVw" in status_card
    assert "client_scene_geometry_fallback" in status_card
    assert "ParticleText" not in status_card
    assert "scenePlan?: ScenePlan | null" in field
    assert "type SceneTransform" in field
    assert "sceneBeatIndex" in field
    assert "narration?: string" in field
    assert "sceneArchetype" in field
    assert "activeSceneBeatIndex" in field
    assert "activeSpeechBeatIndex?: number" in field
    assert "const syncedBeatIndex = activeSpeechBeatIndex" in field
    assert "data-active-speech-beat" in field
    assert "sceneTransform" in field
    assert "sceneCameraView" in field
    assert "type SceneCameraView" in field
    assert "SceneRenderObject" in field
    assert "buildSceneRenderObjects" in field
    assert "sceneParticlesForBeat" in field
    assert "scenePoseForBeat" in field
    assert "figureParticles" in field
    assert "organicStructureParticles" in field
    assert "smallObjectParticles" in field
    assert '"seated"' in field
    assert "hasFruit" in field
    assert "sceneRoleStyle" in field
    assert "semantic_role" in field
    assert "visual_affordance" in field
    assert "spatial_relation" in field
    assert "scene_group_id" in field
    assert "sameSceneGroup" in field
    assert "sceneBeatModelPoints" in field
    assert "sceneGroupCameraView" in field
    assert "small_moving_object" in field
    assert "motion_path" in field
    assert "sceneMotionPathPoint" in field
    assert "drawSceneMotionPathFlow" in field
    assert "cameraView" in field
    assert "scenePlanCentralScale" in field
    assert "centralSceneScale" in field
    assert "dashboard_layout" in field
    assert "central_scale" in field
    assert "drawSceneFocusParticles" in field
    assert "data-scene-objects" in field
    assert "data-active-scene-group" in field
    assert "data-scene-beat" in field
    assert "splatra-imagination-product-label" in field
    assert "imagination /" in field
    assert "imagination ·" not in field
    assert "flowFieldAngle" in field
    assert "drawParticleStroke" in field
    assert "drawParticleSegment" in field
    assert "streamCount = 2" in field
    assert "laneOffset" in field
    assert "curl" in field
    assert "drawParticleEllipse" in field
    assert "ctx.stroke" not in field
    assert "ctx.lineTo" not in field
    assert "centers.forEach" not in field
    assert "SPLATRA Imagination Field" in field
    assert 'mode === "lab"' in field


def test_scene_focus_layout_moves_orb_without_hiding_input() -> None:
    css = (ROOT / "apps" / "web" / "app" / "globals.css").read_text(encoding="utf-8")

    assert '[data-stage-layout="scene_focus"] .hologram-voice-orb' in css
    assert '[data-stage-layout="scene_focus"] .atanor-hologram-speech' in css
    assert '[data-speech-placement="lower_left"] .atanor-hologram-speech' in css
    assert '[data-speech-placement="upper_left"] .atanor-hologram-speech' in css
    assert '[data-speech-placement="upper_right"] .atanor-hologram-speech' in css
    assert '[data-self-narration-placement="upper_left"] .atanor-hologram-self-narration' in css
    assert '[data-self-narration-placement="lower_left"] .atanor-hologram-self-narration' in css
    assert '[data-self-narration-placement="upper_right"] .atanor-hologram-self-narration' in css
    assert '[data-scene-intent="wide_particle_stage"] .hologram-voice-orb' in css
    assert "--atanor-scene-orb-size" in css
    assert "--atanor-scene-field-opacity" in css
    assert "--atanor-scene-speech-upper-left-top" in css
    assert "--atanor-scene-speech-upper-right-top" in css
    assert "--atanor-scene-speech-lower-center-bottom" in css
    assert "--atanor-scene-self-max" in css
    assert "atanor-hologram-composer" in css


def test_product_archetype_cycle_excludes_central_orb_body() -> None:
    field = (ROOT / "apps" / "web" / "app" / "SplatraImaginationField.tsx").read_text(encoding="utf-8")
    product_block = field.split("const PRODUCT_ARCHETYPES", 1)[1].split("];", 1)[0]

    assert '"orb"' not in product_block
    assert '"constellation"' in product_block
    assert '"city_block"' in product_block
    assert '"circuit"' in product_block
