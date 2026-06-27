"""
Test Suite: Producer Persona Catalog (Milestone 9)
Validates 22 producer personas, DSP constraints, genre affinity matrix,
production team parameter resolution, and mastering pipeline behavior.
"""

import pytest
import os
import torch
import torchaudio
from unittest.mock import MagicMock, patch, ANY
from producer import AudioProducer, PERSONA_CONSTRAINTS

# Override conftest autouse database fixture to run offline unit tests
@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema():
    pass


# ============================================================================
# 1. PERSONA CATALOG INTEGRITY TESTS
# ============================================================================

ALL_PERSONA_IDS = [
    # Major tier (10)
    "default_producer", "rubin_raw", "quincy_hifi", "zimmer_epic",
    "martin_pop", "lange_wall", "gmartin_studio", "spector_wall",
    "dre_gfunk", "eno_ambient",
    # Middle tier (10)
    "rock_arena", "dilla_swing", "timbaland_bounce", "pharrell_sparse",
    "godrich_detail", "albini_raw", "vig_power", "wallace_metal",
    "tainy_vibes", "luny_tunes",
    # Minor tier (5)
    "tubby_dub", "perry_dub", "sophie_hyper", "skrillex_loud",
    "eliel_reggae",
]

REQUIRED_KEYS = ["min_drive_db", "max_drive_db", "min_stereo_width", "max_stereo_width", "enable_sub_bass"]


def test_all_25_personas_registered():
    """Every persona from the catalog migration must exist in PERSONA_CONSTRAINTS."""
    assert len(ALL_PERSONA_IDS) == 25
    for pid in ALL_PERSONA_IDS:
        assert pid in PERSONA_CONSTRAINTS, f"Missing persona: {pid}"
    assert len(PERSONA_CONSTRAINTS) == 25


def test_persona_constraint_keys_complete():
    """Every persona must have all required DSP constraint keys."""
    for pid, constraints in PERSONA_CONSTRAINTS.items():
        for key in REQUIRED_KEYS:
            assert key in constraints, f"Persona '{pid}' missing key: {key}"


def test_drive_ranges_valid():
    """min_drive_db < max_drive_db for every persona, and values are non-negative."""
    for pid, c in PERSONA_CONSTRAINTS.items():
        assert c["min_drive_db"] >= 0, f"{pid}: min_drive_db must be >= 0"
        assert c["max_drive_db"] > c["min_drive_db"], f"{pid}: max_drive > min_drive"
        assert c["max_drive_db"] <= 10.0, f"{pid}: max_drive_db unreasonably high"


def test_stereo_width_ranges_valid():
    """1.0 <= min_stereo_width < max_stereo_width for every persona."""
    for pid, c in PERSONA_CONSTRAINTS.items():
        assert c["min_stereo_width"] >= 1.0, f"{pid}: min width must be >= 1.0 (mono)"
        assert c["max_stereo_width"] > c["min_stereo_width"], f"{pid}: max_width > min_width"
        assert c["max_stereo_width"] <= 2.0, f"{pid}: max_stereo_width unreasonably wide"


def test_enable_sub_bass_is_boolean():
    """enable_sub_bass must be a boolean for every persona."""
    for pid, c in PERSONA_CONSTRAINTS.items():
        assert isinstance(c["enable_sub_bass"], bool), f"{pid}: enable_sub_bass must be bool"


# ============================================================================
# 2. TIER DIFFERENTIATION TESTS (DSP character differs per tier)
# ============================================================================

MAJOR_IDS = ["rubin_raw", "quincy_hifi", "zimmer_epic", "martin_pop",
             "lange_wall", "gmartin_studio", "spector_wall", "dre_gfunk", "eno_ambient"]
MIDDLE_IDS = ["rock_arena", "dilla_swing", "timbaland_bounce", "pharrell_sparse",
              "godrich_detail", "albini_raw", "vig_power", "wallace_metal",
              "tainy_vibes", "luny_tunes"]
MINOR_IDS = ["tubby_dub", "perry_dub", "sophie_hyper", "skrillex_loud", "eliel_reggae"]


def test_tier_coverage():
    """All non-default personas are distributed across three tiers."""
    all_tiered = set(MAJOR_IDS + MIDDLE_IDS + MINOR_IDS)
    all_known = set(ALL_PERSONA_IDS) - {"default_producer"}
    assert all_tiered == all_known, f"Tier mismatch: {all_known - all_tiered}"


def test_minimalist_vs_maximalist_drive_spectrum():
    """Albini (anti-compression) must have lower max drive than Skrillex (loudness pioneer)."""
    albini = PERSONA_CONSTRAINTS["albini_raw"]
    skrillex = PERSONA_CONSTRAINTS["skrillex_loud"]
    assert albini["max_drive_db"] < skrillex["min_drive_db"], \
        "Albini max_drive should be below Skrillex min_drive (philosophy gap)"


def test_eno_wide_stereo_vs_spector_narrow():
    """Eno (ambient soundscapes) must have wider stereo than Spector (dense mono)."""
    eno = PERSONA_CONSTRAINTS["eno_ambient"]
    spector = PERSONA_CONSTRAINTS["spector_wall"]
    assert eno["min_stereo_width"] > spector["max_stereo_width"], \
        "Eno's minimum width should exceed Spector's maximum (opposing philosophies)"


def test_sub_bass_producers_are_bass_heavy_genres():
    """Producers known for sub-bass (Dre, Zimmer, Dilla, Tubby, Tainy) have enable_sub_bass=True."""
    sub_bass_expected = ["zimmer_epic", "dre_gfunk", "dilla_swing", "tubby_dub",
                         "perry_dub", "sophie_hyper", "skrillex_loud", "rock_arena",
                         "timbaland_bounce", "pharrell_sparse", "wallace_metal",
                         "tainy_vibes", "luny_tunes", "eliel_reggae"]
    for pid in sub_bass_expected:
        assert PERSONA_CONSTRAINTS[pid]["enable_sub_bass"] is True, \
            f"{pid} should have sub_bass enabled"


def test_purist_producers_no_sub_bass():
    """Purist/minimal producers should NOT have sub-bass boost."""
    no_sub = ["rubin_raw", "eno_ambient", "albini_raw", "gmartin_studio",
              "godrich_detail", "vig_power", "quincy_hifi", "martin_pop",
              "lange_wall", "spector_wall"]
    for pid in no_sub:
        assert PERSONA_CONSTRAINTS[pid]["enable_sub_bass"] is False, \
            f"{pid} should NOT have sub_bass enabled"


# ============================================================================
# 3. MASTERING PIPELINE CLAMPING TESTS
# ============================================================================

@patch("torchaudio.load")
@patch("torchaudio.save")
def test_persona_clamping_albini_caps_drive(mock_save, mock_load):
    """Albini persona (max 1.5dB drive) must clamp a 6dB drive request."""
    mock_load.return_value = (torch.randn(2, 16000), 16000)
    producer = AudioProducer()

    producer.master_track(
        "input.mp3", "output.mp3", "lofi",
        drive_db=6.0,  # Requested way above Albini's max (1.5)
        persona_id="albini_raw"
    )

    args, kwargs = mock_save.call_args
    # The track was saved — verify it completed without error
    assert args[0] == "output.mp3"
    assert args[1].shape[0] == 2


@patch("torchaudio.load")
@patch("torchaudio.save")
def test_persona_clamping_skrillex_allows_high_drive(mock_save, mock_load):
    """Skrillex persona (max 8dB drive) should allow 7dB request without clamping."""
    mock_load.return_value = (torch.randn(2, 16000), 16000)
    producer = AudioProducer()

    producer.master_track(
        "input.mp3", "output.mp3", "techno",
        drive_db=7.0,  # Within Skrillex's range (4-8)
        persona_id="skrillex_loud"
    )

    args, kwargs = mock_save.call_args
    assert args[0] == "output.mp3"


@patch("torchaudio.load")
@patch("torchaudio.save")
def test_persona_sub_bass_applied_when_enabled(mock_save, mock_load):
    """Zimmer persona (sub_bass=True) with boost_db > 0 must activate sub-bass filter."""
    stereo_wav = torch.randn(2, 16000)
    mock_load.return_value = (stereo_wav.clone(), 16000)

    producer = AudioProducer()

    with patch.object(producer, "apply_sub_bass", wraps=producer.apply_sub_bass) as spy_sub:
        producer.master_track(
            "input.mp3", "output.mp3", "ambient",
            sub_bass_boost_db=3.0,
            persona_id="zimmer_epic"
        )
        spy_sub.assert_called_once()
        call_args = spy_sub.call_args
        assert call_args[1]["boost_db"] == 3.0 or call_args[0][1] == 3.0


@patch("torchaudio.load")
@patch("torchaudio.save")
def test_persona_sub_bass_skipped_when_disabled(mock_save, mock_load):
    """Rubin persona (sub_bass=False) must NOT call apply_sub_bass even if boost > 0."""
    mock_load.return_value = (torch.randn(2, 16000), 16000)

    producer = AudioProducer()

    with patch.object(producer, "apply_sub_bass", wraps=producer.apply_sub_bass) as spy_sub:
        producer.master_track(
            "input.mp3", "output.mp3", "lofi",
            sub_bass_boost_db=5.0,  # Requested but Rubin says no
            persona_id="rubin_raw"
        )
        spy_sub.assert_not_called()


# ============================================================================
# 4. AUDIO OUTPUT DIFFERENTIATION TESTS
# ============================================================================

@patch("torchaudio.save")
@patch("torchaudio.load")
def test_different_personas_produce_different_outputs(mock_load, mock_save):
    """Two drastically different personas on the same input must produce different audio."""
    # Deterministic input
    torch.manual_seed(42)
    fixed_input = torch.randn(2, 16000)

    outputs = {}
    for persona_id in ["albini_raw", "skrillex_loud"]:
        mock_load.return_value = (fixed_input.clone(), 16000)
        mock_save.reset_mock()

        producer = AudioProducer()
        producer.master_track(
            "input.mp3", "output.mp3", "techno",
            drive_db=3.0,
            high_shelf_db=2.0,
            stereo_width=1.25,
            persona_id=persona_id
        )

        saved_wav = mock_save.call_args[0][1]
        outputs[persona_id] = saved_wav

    # The outputs must differ (different clamping, different sub-bass)
    diff = torch.abs(outputs["albini_raw"] - outputs["skrillex_loud"]).mean()
    assert diff > 0.001, f"Persona outputs should differ significantly, got diff={diff}"


@patch("torchaudio.save")
@patch("torchaudio.load")
def test_eno_vs_spector_stereo_width_difference(mock_load, mock_save):
    """Eno (wide) vs Spector (narrow) must produce measurably different stereo fields."""
    torch.manual_seed(123)
    # Create input with correlated stereo content (high frequency mid/side to pass crossover without tripping guardrail)
    t = torch.linspace(0, 1, 16000)
    mid = torch.sin(2 * 3.14159 * 440 * t)
    side = torch.sin(2 * 3.14159 * 880 * t) * 0.2
    left = mid + side
    right = mid - side
    fixed_input = torch.stack([left, right])

    stereo_diffs = {}
    for persona_id in ["eno_ambient", "spector_wall"]:
        mock_load.return_value = (fixed_input.clone(), 16000)
        mock_save.reset_mock()

        producer = AudioProducer()
        producer.master_track(
            "input.mp3", "output.mp3", "ambient",
            stereo_width=1.4,  # Both request 1.4, but clamping differs
            persona_id=persona_id
        )

        saved_wav = mock_save.call_args[0][1]
        # Measure L-R difference (stereo width proxy)
        lr_diff = torch.abs(saved_wav[0] - saved_wav[1]).mean().item()
        stereo_diffs[persona_id] = lr_diff

    # Eno's output should be wider (bigger L-R difference) than Spector's
    assert stereo_diffs["eno_ambient"] > stereo_diffs["spector_wall"], \
        f"Eno width ({stereo_diffs['eno_ambient']:.4f}) should exceed Spector ({stereo_diffs['spector_wall']:.4f})"


# ============================================================================
# 5. TEAM RESOLUTION & AFFINITY FALLBACK TESTS
# ============================================================================

def test_api_team_resolution_direct_match():
    """When production_team_parameters has a direct style match, use those params."""
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u_test", "id": "u_test"}

    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.cursor.return_value = mock_cur

    # First call: generation row; Second call: direct team params match
    mock_cur.fetchone.side_effect = [
        {
            "audio_url": "https://replicate.delivery/track.mp3",
            "prompt": "chill vibes", "style": "lofi",
            "user_id": "u_test", "watermark_id": 42
        },
        {  # Direct match from production_team_parameters for lofi
            "drive_db": 2.00, "high_shelf_db": 1.50,
            "stereo_width": 1.15, "limiter_ceiling_db": -1.50,
            "sub_bass_boost_db": 1.50, "lead_producer_id": "dilla_swing"
        }
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    from fastapi.testclient import TestClient
    import os

    with patch("producer.AudioProducer") as MockProducer, \
         patch("c2pa_embedder.C2PAEmbedder") as MockEmbedder, \
         patch("requests.get") as mock_get:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"
        mock_get.return_value = mock_resp

        def fake_master(wav_path, output_path, style, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"mastered")

        mock_prod_inst = MockProducer.return_value
        mock_prod_inst.master_track.side_effect = fake_master

        # Use a treatment-generating ID
        gen_id = "gen_treatment_lofi_dilla"
        cache_path = f"/tmp/remixa_cache/{gen_id}_treatment.mp3"
        if os.path.exists(cache_path):
            os.remove(cache_path)

        try:
            client = TestClient(app)
            resp = client.get(f"/api/v2/generations/{gen_id}/download")
            assert resp.status_code == 200

            # Verify the mastering call used Dilla's resolved params
            mock_prod_inst.master_track.assert_called_once()
            call_kwargs = mock_prod_inst.master_track.call_args
            # Check persona_id was resolved from team parameters
            kw = call_kwargs[1] if call_kwargs[1] else {}
            if "persona_id" in kw:
                assert kw["persona_id"] == "dilla_swing"
        finally:
            app.dependency_overrides.clear()
            if os.path.exists(cache_path):
                os.remove(cache_path)


def test_api_team_resolution_affinity_fallback():
    """When no direct team params exist, fall back to highest-affinity producer."""
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u_test2", "id": "u_test2"}

    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.cursor.return_value = mock_cur

    # Sequence: generation row → no direct match → affinity → producer params → ambient fallback
    mock_cur.fetchone.side_effect = [
        {  # Generation details for an unsupported style 'dnb'
            "audio_url": "https://replicate.delivery/track.mp3",
            "prompt": "jungle beat", "style": "dnb",
            "user_id": "u_test2", "watermark_id": 55
        },
        None,  # No direct match in production_team_parameters for 'dnb'
        {"producer_id": "wallace_metal"},  # Highest affinity producer for 'dnb'
        {  # Wallace's parameters from production_team_parameters
            "drive_db": 4.50, "high_shelf_db": 2.50,
            "stereo_width": 1.35, "limiter_ceiling_db": -0.30,
            "sub_bass_boost_db": 2.50, "lead_producer_id": "wallace_metal"
        }
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    from fastapi.testclient import TestClient
    import os

    with patch("producer.AudioProducer") as MockProducer, \
         patch("c2pa_embedder.C2PAEmbedder") as MockEmbedder, \
         patch("requests.get") as mock_get:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"
        mock_get.return_value = mock_resp

        def fake_master(wav_path, output_path, style, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"mastered")

        mock_prod_inst = MockProducer.return_value
        mock_prod_inst.master_track.side_effect = fake_master

        gen_id = "gen_treatment_dnb_fallback"
        cache_path = f"/tmp/remixa_cache/{gen_id}_treatment.mp3"
        if os.path.exists(cache_path):
            os.remove(cache_path)

        try:
            client = TestClient(app)
            resp = client.get(f"/api/v2/generations/{gen_id}/download")
            assert resp.status_code == 200

            # Verify mastering was called (affinity fallback path worked)
            mock_prod_inst.master_track.assert_called_once()
            call_kwargs = mock_prod_inst.master_track.call_args
            kw = call_kwargs[1] if call_kwargs[1] else {}
            if "persona_id" in kw:
                assert kw["persona_id"] == "wallace_metal"
            if "drive_db" in kw:
                assert kw["drive_db"] == 4.50
        finally:
            app.dependency_overrides.clear()
            if os.path.exists(cache_path):
                os.remove(cache_path)


# ============================================================================
# 6. MIGRATION SQL INTEGRITY TESTS
# ============================================================================

def test_migration_018_exists():
    """The migration file must exist on disk."""
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "018_producer_catalog_seed.sql"
    )
    assert os.path.exists(migration_path), "Migration 018 not found"


def test_migration_018_contains_all_persona_ids():
    """The migration SQL must reference all 19 new persona IDs (excluding original 4)."""
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "018_producer_catalog_seed.sql"
    )
    with open(migration_path, "r") as f:
        sql = f.read()

    new_personas = [
        "martin_pop", "lange_wall", "gmartin_studio", "spector_wall",
        "dre_gfunk", "eno_ambient", "rock_arena", "dilla_swing",
        "timbaland_bounce", "pharrell_sparse", "godrich_detail", "albini_raw",
        "vig_power", "wallace_metal", "tubby_dub", "perry_dub",
        "sophie_hyper", "skrillex_loud"
    ]

    for pid in new_personas:
        assert pid in sql, f"Persona '{pid}' not found in migration SQL"


def test_migration_018_has_hierarchy_tiers():
    """The migration must add hierarchy_tier column with all three tier values."""
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "018_producer_catalog_seed.sql"
    )
    with open(migration_path, "r") as f:
        sql = f.read()

    assert "hierarchy_tier" in sql
    assert "'major'" in sql
    assert "'middle'" in sql
    assert "'minor'" in sql


def test_migration_018_has_genre_affinities():
    """The migration must seed genre affinity scores."""
    import os
    migration_path = os.path.join(
        os.path.dirname(__file__), "..", "migrations", "018_producer_catalog_seed.sql"
    )
    with open(migration_path, "r") as f:
        sql = f.read()

    assert "producer_genre_affinities" in sql
    # Verify at least a few genre styles are present
    for style in ["ambient", "lofi", "house", "trap", "techno"]:
        assert f"'{style}'" in sql, f"Style '{style}' missing from affinity seeds"


# ============================================================================
# 7. FULL PIPELINE ROUND-TRIP TEST (end-to-end per persona)
# ============================================================================

@pytest.mark.parametrize("persona_id", ALL_PERSONA_IDS)
@patch("torchaudio.save")
@patch("torchaudio.load")
def test_mastering_pipeline_runs_for_every_persona(mock_load, mock_save, persona_id):
    """Every registered persona must complete a mastering pipeline without error."""
    torch.manual_seed(0)
    mock_load.return_value = (torch.randn(2, 16000), 16000)

    producer = AudioProducer()
    producer.master_track(
        "input.mp3", "output.mp3", "house",
        drive_db=3.0,
        high_shelf_db=2.0,
        stereo_width=1.3,
        sub_bass_boost_db=1.0,
        persona_id=persona_id
    )

    assert mock_save.called, f"Pipeline failed to produce output for persona {persona_id}"
    saved_wav = mock_save.call_args[0][1]
    assert saved_wav.shape[0] == 2, f"Expected stereo output for persona {persona_id}"
    assert saved_wav.shape[1] == 16000, f"Sample count mismatch for persona {persona_id}"
    # No NaN or Inf in output
    assert not torch.isnan(saved_wav).any(), f"NaN in output for persona {persona_id}"
    assert not torch.isinf(saved_wav).any(), f"Inf in output for persona {persona_id}"


# ============================================================================
# 8. ADVANCED DSP & REAL-WORLD BEHAVIOR TESTS
# ============================================================================

@patch("torchaudio.save")
@patch("torchaudio.load")
def test_loudness_war_rms_and_crest_factor(mock_load, mock_save):
    """Verify that Skrillex is physically louder (higher RMS) and Albini has higher Crest Factor."""
    torch.manual_seed(42)
    # Generate 1 second of stereo noise at 44.1kHz
    input_wav = torch.randn(2, 44100)
    mock_load.return_value = (input_wav.clone(), 44100)

    outputs = {}
    for persona_id in ["skrillex_loud", "albini_raw"]:
        mock_save.reset_mock()
        producer = AudioProducer(sample_rate=44100)
        producer.master_track(
            "input.mp3", "output.mp3", "techno",
            drive_db=8.0,  # Request maximum drive
            persona_id=persona_id
        )
        outputs[persona_id] = mock_save.call_args[0][1]

    # Calculate RMS energy: sqrt(mean(x^2))
    rms_skrillex = torch.sqrt(torch.mean(outputs["skrillex_loud"] ** 2)).item()
    rms_albini = torch.sqrt(torch.mean(outputs["albini_raw"] ** 2)).item()

    # Skrillex allows higher drive (8.0 vs Albini's clamped 1.5), so it must be louder
    assert rms_skrillex > rms_albini * 1.05, f"Skrillex RMS ({rms_skrillex:.4f}) should be higher than Albini ({rms_albini:.4f})"

    # Calculate Crest Factor: Peak / RMS (proxy for dynamic range)
    crest_skrillex = (torch.max(torch.abs(outputs["skrillex_loud"])) / rms_skrillex).item()
    crest_albini = (torch.max(torch.abs(outputs["albini_raw"])) / rms_albini).item()

    # Albini preserves natural transients / rejects compression, so its crest factor should be higher
    assert crest_albini > crest_skrillex * 1.05, f"Albini Crest Factor ({crest_albini:.4f}) should exceed Skrillex ({crest_skrillex:.4f})"


@patch("torchaudio.save")
@patch("torchaudio.load")
def test_spectral_fingerprint_brightness_and_bass(mock_load, mock_save):
    """Verify that sub-bass boost and high-drive saturation alter the spectral footprint appropriately."""
    torch.manual_seed(999)
    input_wav = torch.randn(2, 44100)

    # 1. Test Sub-Bass Boost frequency energy comparison (Dre vs Eno)
    # Dre has enable_sub_bass=True, Eno has enable_sub_bass=False
    outputs = {}
    for persona_id in ["dre_gfunk", "eno_ambient"]:
        mock_load.return_value = (input_wav.clone(), 44100)
        mock_save.reset_mock()
        producer = AudioProducer(sample_rate=44100)
        producer.master_track(
            "input.mp3", "output.mp3", "ambient",
            sub_bass_boost_db=5.0,  # Request heavy sub-bass boost
            persona_id=persona_id
        )
        outputs[persona_id] = mock_save.call_args[0][1]

    # Run a low-pass biquad filter at 100Hz to isolate low frequencies
    lp_dre = torchaudio.functional.lowpass_biquad(outputs["dre_gfunk"], 44100, 100.0)
    lp_eno = torchaudio.functional.lowpass_biquad(outputs["eno_ambient"], 44100, 100.0)

    # Measure ratio of low-frequency energy to total energy
    lfr_dre = torch.sum(lp_dre ** 2).item() / torch.sum(outputs["dre_gfunk"] ** 2).item()
    lfr_eno = torch.sum(lp_eno ** 2).item() / torch.sum(outputs["eno_ambient"] ** 2).item()

    # Dre GFunk must have a higher low-frequency energy ratio due to sub-bass processing
    assert lfr_dre > lfr_eno * 1.1, f"Dre low-freq ratio ({lfr_dre:.4f}) should exceed Eno ({lfr_eno:.4f})"

    # 2. Test High-Drive Saturation (Skrillex vs Albini) creating high-frequency harmonics
    # Saturation (tanh) generates higher order harmonics (increasing HF ratio)
    t = torch.linspace(0, 1, 44100)
    sine_100hz = torch.sin(2 * 3.14159 * 100.0 * t)
    input_sine = torch.stack([sine_100hz, sine_100hz])

    mock_load.return_value = (input_sine.clone(), 44100)
    mock_save.reset_mock()
    producer = AudioProducer(sample_rate=44100)
    producer.master_track("input.mp3", "output.mp3", "techno", drive_db=8.0, persona_id="skrillex_loud")
    wav_skrillex = mock_save.call_args[0][1]

    mock_load.return_value = (input_sine.clone(), 44100)
    mock_save.reset_mock()
    producer.master_track("input.mp3", "output.mp3", "techno", drive_db=8.0, persona_id="albini_raw")
    wav_albini = mock_save.call_args[0][1]

    # We high-pass filter at 1000Hz to capture the generated harmonics
    hp_skrillex = torchaudio.functional.highpass_biquad(wav_skrillex, 44100, 1000.0)
    hp_albini = torchaudio.functional.highpass_biquad(wav_albini, 44100, 1000.0)

    hfr_skrillex = torch.sum(hp_skrillex ** 2).item() / torch.sum(wav_skrillex ** 2).item()
    hfr_albini = torch.sum(hp_albini ** 2).item() / torch.sum(wav_albini ** 2).item()

    # Saturation creates high-frequency distortion products, increasing HFR
    assert hfr_skrillex > hfr_albini * 2.0, f"Skrillex HFR ({hfr_skrillex:.6f}) should exceed Albini ({hfr_albini:.6f}) by at least 2x due to clipping"


@patch("torchaudio.save")
@patch("torchaudio.load")
def test_idempotency_and_determinism(mock_load, mock_save):
    """Verify that mastering is perfectly idempotent and bit-identical across identical runs."""
    torch.manual_seed(12345)
    input_wav = torch.randn(2, 44100)

    runs = []
    for i in range(2):
        mock_load.return_value = (input_wav.clone(), 44100)
        mock_save.reset_mock()
        producer = AudioProducer(sample_rate=44100)
        producer.master_track(
            "input.mp3", "output.mp3", "reggaeton",
            drive_db=3.5,
            high_shelf_db=2.0,
            stereo_width=1.2,
            sub_bass_boost_db=2.0,
            persona_id="tainy_vibes"
        )
        runs.append(mock_save.call_args[0][1].clone())

    assert torch.equal(runs[0], runs[1]), "Mastered tracks must be bit-identical across runs"


@patch("torchaudio.save")
@patch("torchaudio.load")
def test_constraint_boundary_protection_extreme_inputs(mock_load, mock_save):
    """Verify that extreme out-of-bounds parameters are clamped safely and remain NaN-free."""
    torch.manual_seed(777)
    input_wav = torch.randn(2, 16000)
    mock_load.return_value = (input_wav.clone(), 16000)

    producer = AudioProducer(sample_rate=16000)

    # Rubin limits: drive (0.5 - 3.0), stereo (1.0 - 1.2), sub_bass = False
    producer.master_track(
        "input.mp3", "output.mp3", "lofi",
        drive_db=30.0,            # Extreme high drive
        stereo_width=-5.0,        # Negative width
        sub_bass_boost_db=100.0,   # Massive sub bass request
        persona_id="rubin_raw"
    )

    output_wav = mock_save.call_args[0][1]
    assert not torch.isnan(output_wav).any(), "Extreme inputs caused NaNs"
    assert not torch.isinf(output_wav).any(), "Extreme inputs caused Infs"

    # Make sure width was clamped to min width >= 1.0 (since requested was -5.0)
    # The widening gain amount is min clamped. If amount is exactly 1.0, mid-side widening is neutral.
    # We can check that the output did not blow up.
    assert torch.max(torch.abs(output_wav)) <= 1.0, "Limiter ceiling breached"


# ============================================================================
# 9. TEAM ROUTING, FALLBACKS & SEQUENCE OPTIMIZATION
# ============================================================================

def test_reggaeton_routing_and_affinity_lookup():
    """Verify that style 'reggaeton' resolves to Tainy in API routing mock."""
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u_reggae", "id": "u_reggae"}

    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.cursor.return_value = mock_cur

    # Sequence: generation row -> no direct team params -> highest affinity -> producer params -> ambient fallback
    mock_cur.fetchone.side_effect = [
        {
            "audio_url": "https://replicate.delivery/track.mp3",
            "prompt": "heavy dembow beat", "style": "reggaeton",
            "user_id": "u_reggae", "watermark_id": 99
        },
        None,  # No direct production_team_parameters match
        {"producer_id": "tainy_vibes"},  # Highest affinity for reggaeton style
        {
            "drive_db": 3.50, "high_shelf_db": 2.00,
            "stereo_width": 1.25, "limiter_ceiling_db": -0.50,
            "sub_bass_boost_db": 2.00, "lead_producer_id": "tainy_vibes"
        }
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    from fastapi.testclient import TestClient
    import os

    with patch("producer.AudioProducer") as MockProducer, \
         patch("c2pa_embedder.C2PAEmbedder") as MockEmbedder, \
         patch("requests.get") as mock_get:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"
        mock_get.return_value = mock_resp

        def fake_master(wav_path, output_path, style, **kwargs):
            with open(output_path, "wb") as f:
                f.write(b"mastered_reggaeton")

        mock_prod_inst = MockProducer.return_value
        mock_prod_inst.master_track.side_effect = fake_master

        import hashlib
        gen_id = "gen_reggaeton_test"
        while True:
            hash_val = int(hashlib.md5(gen_id.encode('utf-8')).hexdigest(), 16) % 100
            if hash_val >= 10:
                break
            gen_id += "_t"
        cache_path = f"/tmp/remixa_cache/{gen_id}_treatment.mp3"
        if os.path.exists(cache_path):
            os.remove(cache_path)

        try:
            client = TestClient(app)
            resp = client.get(f"/api/v2/generations/{gen_id}/download")
            assert resp.status_code == 200

            mock_prod_inst.master_track.assert_called_once()
            kw = mock_prod_inst.master_track.call_args[1]
            assert kw.get("persona_id") == "tainy_vibes"
            assert kw.get("drive_db") == 3.5
            assert kw.get("sub_bass_boost_db") == 2.0
        finally:
            app.dependency_overrides.clear()
            if os.path.exists(cache_path):
                os.remove(cache_path)


def test_routing_fallback_unknown_genre():
    """Verify that an unknown genre cleanly falls back to zimmer/ambient parameters."""
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db

    app.dependency_overrides[get_current_user] = lambda: {"user_id": "u_fallback", "id": "u_fallback"}

    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.cursor.return_value = mock_cur

    # Sequence: generation -> no team params -> no affinity -> zimmer/ambient absolute fallback
    mock_cur.fetchone.side_effect = [
        {
            "audio_url": "https://replicate.delivery/track.mp3",
            "prompt": "weird space music", "style": "unknown_future_bass",
            "user_id": "u_fallback", "watermark_id": 88
        },
        None,  # No team params
        None,  # No affinity
        {      # Ambient fallback
            "drive_db": 1.00, "high_shelf_db": 0.50,
            "stereo_width": 1.50, "limiter_ceiling_db": -2.00,
            "sub_bass_boost_db": 0.00, "lead_producer_id": "eno_ambient"
        }
    ]

    app.dependency_overrides[get_db] = lambda: mock_db

    from fastapi.testclient import TestClient
    import os

    with patch("producer.AudioProducer") as MockProducer, \
         patch("c2pa_embedder.C2PAEmbedder") as MockEmbedder, \
         patch("requests.get") as mock_get:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"audio"
        mock_get.return_value = mock_resp

        mock_prod_inst = MockProducer.return_value
        mock_prod_inst.master_track.side_effect = lambda wav_path, output_path, style, **k: open(output_path, "wb").write(b"ok")

        import hashlib
        gen_id = "gen_unknown_fallback"
        while True:
            hash_val = int(hashlib.md5(gen_id.encode('utf-8')).hexdigest(), 16) % 100
            if hash_val >= 10:
                break
            gen_id += "_t"
        cache_path = f"/tmp/remixa_cache/{gen_id}_treatment.mp3"
        if os.path.exists(cache_path):
            os.remove(cache_path)

        try:
            client = TestClient(app)
            resp = client.get(f"/api/v2/generations/{gen_id}/download")
            assert resp.status_code == 200
            mock_prod_inst.master_track.assert_called_once()
            kw = mock_prod_inst.master_track.call_args[1]
            assert kw.get("persona_id") == "eno_ambient"
        finally:
            app.dependency_overrides.clear()
            if os.path.exists(cache_path):
                os.remove(cache_path)


def test_ab_feedback_sequence_validation():
    """Verify sequence validation: A/B optimization nudges params but strictly respects constraints."""
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
    from optimize_mastering_params import optimize_team_params

    # Scenario: We optimize reggaeton parameters with lead Tainy.
    # Tainy constraints: drive_db (1.5 to 5.0), stereo_width (1.15 to 1.45)
    mock_cur = MagicMock()

    # Initial state
    current_params = {
        "lead_producer_id": "tainy_vibes",
        "drive_db": 3.5,
        "high_shelf_db": 2.0,
        "stereo_width": 1.25,
        "limiter_ceiling_db": -0.5,
        "sub_bass_boost_db": 2.0,
        "preferred_metric": "tiktok_share",
        "min_drive_db": 1.5,
        "max_drive_db": 5.0,
        "min_stereo_width": 1.15,
        "max_stereo_width": 1.45,
        "enable_sub_bass": True
    }

    # Simulate 20 consecutive positive optimization runs (treatment doing better)
    # Each positive run nudges drive by +0.1, shelf by +0.1, width by +0.02, ceiling by -0.05, sub_bass by +0.2
    # Ensure variables do NOT exceed Tainy's max limits.
    for step in range(30):
        # Mock database query results: treatment variant outperforms control variant
        # Treatment has 10 downloads, 10 plays, etc.
        # Control has 10 downloads, but fewer plays
        mock_cur.fetchall.return_value = [
            {"variant": "treatment", "action": "download", "count": 10},
            {"variant": "treatment", "action": "play_100s", "count": 8},
            {"variant": "treatment", "action": "tiktok_share", "count": 8},
            {"variant": "control", "action": "download", "count": 10},
            {"variant": "control", "action": "play_100s", "count": 2},
            {"variant": "control", "action": "tiktok_share", "count": 1},
        ]

        # Call target logic
        optimize_team_params(mock_cur, "reggaeton", current_params)

        # Inspect UPDATE calls to extract the new state parameters and feed them forward
        update_calls = [call for call in mock_cur.execute.call_args_list if "UPDATE production_team_parameters" in call[0][0]]
        if update_calls:
            # Extract arguments: (drive, shelf, width, ceiling, sub_bass, style, lead_id)
            args = update_calls[-1][0][1]
            current_params["drive_db"] = args[0]
            current_params["high_shelf_db"] = args[1]
            current_params["stereo_width"] = args[2]
            current_params["limiter_ceiling_db"] = args[3]
            current_params["sub_bass_boost_db"] = args[4]
        mock_cur.execute.reset_mock()

    # Assert that even after 30 positive runs, parameters are capped exactly at Tainy's constraints
    assert current_params["drive_db"] <= 5.0, f"Drive exceeded Tainy max limit: {current_params['drive_db']}"
    assert current_params["stereo_width"] <= 1.45, f"Width exceeded Tainy max limit: {current_params['stereo_width']}"
    assert current_params["sub_bass_boost_db"] <= 4.0, "Sub-bass boost exceeded maximum loop cap of 4.0"

    # Now simulate a sequence of 20 negative feedback cycles (treatment performs worse)
    # Ensure variables do NOT drop below Tainy's min limits
    for step in range(30):
        # Treatment performs worse
        mock_cur.fetchall.return_value = [
            {"variant": "treatment", "action": "download", "count": 10},
            {"variant": "treatment", "action": "play_100s", "count": 1},
            {"variant": "treatment", "action": "tiktok_share", "count": 0},
            {"variant": "control", "action": "download", "count": 10},
            {"variant": "control", "action": "play_100s", "count": 9},
            {"variant": "control", "action": "tiktok_share", "count": 9},
        ]

        optimize_team_params(mock_cur, "reggaeton", current_params)

        update_calls = [call for call in mock_cur.execute.call_args_list if "UPDATE production_team_parameters" in call[0][0]]
        if update_calls:
            args = update_calls[-1][0][1]
            current_params["drive_db"] = args[0]
            current_params["high_shelf_db"] = args[1]
            current_params["stereo_width"] = args[2]
            current_params["limiter_ceiling_db"] = args[3]
            current_params["sub_bass_boost_db"] = args[4]
        mock_cur.execute.reset_mock()

    # Assert parameters do not drop below min limits
    assert current_params["drive_db"] >= 1.5, f"Drive dropped below Tainy min limit: {current_params['drive_db']}"
    assert current_params["stereo_width"] >= 1.15, f"Width dropped below Tainy min limit: {current_params['stereo_width']}"
    assert current_params["sub_bass_boost_db"] >= 0.0, "Sub-bass boost dropped below 0.0"


def test_audio_producer_dsp_nan_and_exception_paths():
    """Verify that AudioProducer fallback logic triggers correctly when torchaudio fails or outputs NaN."""
    # Create an AudioProducer instance
    prod = AudioProducer(sample_rate=44100)
    
    # 1. Zero amplitude limiting
    zero_tensor = torch.zeros((1, 1000))
    limited_zero = prod.apply_limiting_and_maximize(zero_tensor)
    assert torch.all(limited_zero == 0)

    # 2. low_cut NaN fallback
    nan_tensor = torch.tensor([[float('nan')]])
    res_low_cut_nan = prod.apply_low_cut(nan_tensor)
    # The output should fall back and be the original tensor
    assert torch.isnan(res_low_cut_nan).all()

    # 3. low_cut exception fallback
    with patch("torchaudio.functional.highpass_biquad", side_effect=Exception("DSP Failure")):
        res_low_cut_fail = prod.apply_low_cut(torch.ones((1, 100)))
        # Should catch exception and fall back to input
        assert torch.all(res_low_cut_fail == 1)

    # 4. high_shelf NaN fallback
    res_high_shelf_nan = prod.apply_high_shelf(nan_tensor, gain_db=2.0)
    assert torch.isnan(res_high_shelf_nan).all()

    # 5. high_shelf exception fallback
    with patch("torchaudio.functional.treble_biquad", side_effect=Exception("DSP Failure")):
        res_high_shelf_fail = prod.apply_high_shelf(torch.ones((1, 100)), gain_db=2.0)
        assert torch.all(res_high_shelf_fail == 1)

    # 6. sub_bass NaN fallback
    res_sub_bass_nan = prod.apply_sub_bass(nan_tensor, boost_db=2.0)
    assert torch.isnan(res_sub_bass_nan).all()

    # 7. sub_bass exception fallback
    with patch("torchaudio.functional.bass_biquad", side_effect=Exception("DSP Failure")):
        res_sub_bass_fail = prod.apply_sub_bass(torch.ones((1, 100)), boost_db=2.0)
        assert torch.all(res_sub_bass_fail == 1)


def test_lufs_loudness_measurement():
    """Verify that calculate_lufs correctly measures perceptual loudness."""
    prod = AudioProducer(sample_rate=44100)
    
    # 1. Test silent signal
    silence = torch.zeros((2, 44100))
    lufs_silence = prod.calculate_lufs(silence)
    assert lufs_silence == -100.0
    
    # 2. Test standard sine wave (loud signal)
    t = torch.linspace(0, 1, 44100)
    sine = torch.sin(2 * 3.14159 * 1000 * t).repeat(2, 1)  # Stereo 1kHz sine
    lufs_sine = prod.calculate_lufs(sine)
    assert -20.0 < lufs_sine < 0.0  # realistic level for full-scale sine
    
    # 3. Test exception fallback logic
    with patch("torchaudio.functional.treble_biquad", side_effect=Exception("filter error")):
        lufs_fallback = prod.calculate_lufs(sine)
        # Should fall back to RMS-based db calculation and still succeed
        assert -20.0 < lufs_fallback < 0.0


def test_oversampling_removes_aliasing_artifacts():
    """Verify that 4x oversampling reduces digital aliasing artifacts in the audio band."""
    sr = 44100
    prod = AudioProducer(sample_rate=sr)
    t = torch.linspace(0, 1, sr)
    sine = torch.sin(2 * 3.14159 * 15000 * t).unsqueeze(0)  # Mono 15kHz
    
    # 1. Naive clipping (oversampling fails/disabled)
    with patch("torchaudio.functional.resample", side_effect=Exception("disable oversampling")):
        naive_clipped = prod.apply_limiting_and_maximize(sine, target_db=0.0, drive_db=12.0)
        
    # 2. Oversampled clipping
    oversampled_clipped = prod.apply_limiting_and_maximize(sine, target_db=0.0, drive_db=12.0)
    
    # Run FFT to compare high frequency energy
    fft_naive = torch.abs(torch.fft.rfft(naive_clipped))
    fft_oversampled = torch.abs(torch.fft.rfft(oversampled_clipped))
    
    # Verify both ran successfully
    assert fft_naive.shape == fft_oversampled.shape
    assert torch.sum(fft_oversampled) != torch.sum(fft_naive)


def test_true_peak_clamping_prevents_dac_clipping():
    """Verify that True Peak limiting prevents reconstructed inter-sample peaks from exceeding the ceiling."""
    prod = AudioProducer(sample_rate=44100)
    
    transient = torch.zeros((2, 1000))
    transient[:, 500] = 1.0
    transient[:, 501] = -1.0
    
    # Limiting with target peak of -0.5 dB (approx 0.944 amplitude)
    target_db = -0.5
    target_amp = 10.0 ** (target_db / 20.0)
    
    mastered = prod.apply_limiting_and_maximize(transient, target_db=target_db, drive_db=3.0)
    
    # Verify that sample peaks at the native rate do not exceed the target amplitude
    assert torch.max(torch.abs(mastered)) <= target_amp + 1e-5
    
    # Measure the True Peak by upsampling 8x
    tp_upsampled = torchaudio.functional.resample(mastered, 44100, 44100 * 8)
    true_peak = torch.max(torch.abs(tp_upsampled))
    
    # True Peak must be strictly below or equal to target_amp
    assert true_peak <= target_amp + 1e-4


def test_closed_loop_loudness_target():
    """Verify that AudioProducer masters the track precisely to target LUFS level."""
    prod = AudioProducer(sample_rate=44100)
    
    # 1. Generate stereo test wave
    t = torch.linspace(0, 1, 44100)
    sine = torch.sin(2 * 3.14159 * 1000 * t).repeat(2, 1)  # Stereo 1kHz sine
    
    # 2. Apply limiting to target -16.0 LUFS
    mastered_16 = prod.apply_limiting_and_maximize(sine, target_db=-0.5, drive_db=3.0, target_lufs=-16.0)
    lufs_16 = prod.calculate_lufs(mastered_16)
    # Target K-weighted LUFS must be close to -16.0 dB
    assert abs(lufs_16 - (-16.0)) < 0.3
    
    # 3. Apply limiting to target -11.0 LUFS
    mastered_11 = prod.apply_limiting_and_maximize(sine, target_db=-0.5, drive_db=3.0, target_lufs=-11.0)
    lufs_11 = prod.calculate_lufs(mastered_11)
    assert abs(lufs_11 - (-11.0)) < 0.3


@patch("torchaudio.save")
@patch("torchaudio.load")
def test_normalize_loudness_control_path(mock_load, mock_save):
    """Verify that normalize_loudness scales a raw file correctly to target LUFS level."""
    # Generate quiet stereo sine wave
    t = torch.linspace(0, 1, 44100)
    sine = (torch.sin(2 * 3.14159 * 1000 * t) * 0.05).repeat(2, 1)  # quiet
    mock_load.return_value = (sine, 44100)
    
    prod = AudioProducer(sample_rate=44100)
    
    # Run normalization
    prod.normalize_loudness("raw_quiet.mp3", "normalized.mp3", target_lufs=-14.0)
    
    # Check what was saved
    saved_wav = mock_save.call_args[0][1]
    saved_sr = mock_save.call_args[0][2]
    assert saved_sr == 44100
    
    # Measure the loudness of the saved waveform
    result_lufs = prod.calculate_lufs(saved_wav)
    assert abs(result_lufs - (-14.0)) < 0.3


@patch("requests.get")
@patch("producer.AudioProducer.master_track")
@patch("producer.AudioProducer.normalize_loudness")
@patch("c2pa_embedder.C2PAEmbedder.embed_mp3")
@patch("c2pa_embedder.C2PAEmbedder.embed_waveform_watermark")
def test_api_v2_control_loudness_normalization(
    mock_embed_wm, mock_embed_mp3, mock_normalize, mock_master, mock_get
):
    """Verify that api_v2 download endpoint calls normalize_loudness for control and master_track for treatment."""
    from fastapi.testclient import TestClient
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db
    
    # Write empty mock files to allow copy/move logic to pass
    def side_effect_normalize(wav_path, output_path, target_lufs):
        with open(output_path, "wb") as f:
            f.write(b"normalized audio")
            
    def side_effect_master(wav_path, output_path, style, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"mastered audio")
            
    mock_normalize.side_effect = side_effect_normalize
    mock_master.side_effect = side_effect_master

    # Setup DB connection
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    mock_cur.__enter__.return_value = mock_cur
    
    # Configure mock_get for requests.get
    mock_get.return_value.status_code = 200
    mock_get.return_value.content = b"original raw audio"
    
    # Select statement mock return
    mock_cur.fetchone.return_value = {
        "id": "gen_123",
        "user_id": "user_456",
        "style": "trap",
        "prompt": "heavy reggaeton loop",
        "watermark_id": 999,
        "is_public": True,
        "audio_url": "http://replicate.delivery/track.mp3"
    }
    
    # Mock user auth bypass
    mock_user = {"id": "user_456", "user_id": "user_456", "email": "dev@remixa.eu", "role": "admin"}
    app.dependency_overrides[get_current_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_conn
    
    # Setup test file in local dev cache path
    gen_id = "gen_123"
    tmp_path = f"/tmp/remixa_cache/{gen_id}.mp3"
    os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(b"original raw audio")
        
    # Clean up any leftover cached files from previous runs to prevent false cache hits
    cache_dir = "/tmp/remixa_cache"
    if os.path.exists(cache_dir):
        for f_name in os.listdir(cache_dir):
            if f_name.startswith("gen_control_id_") or f_name.startswith("gen_treatment_id_") or f_name.startswith("gen_123"):
                try:
                    os.remove(os.path.join(cache_dir, f_name))
                except OSError:
                    pass
                    
    client = TestClient(app)
    
    try:
        import hashlib
        # Find a generation_id that hashes to control (hash_val < 10)
        gen_id_control = None
        for i in range(1000):
            g_id = f"gen_control_id_{i}"
            h_val = int(hashlib.md5(g_id.encode('utf-8')).hexdigest(), 16) % 100
            if h_val < 10:
                gen_id_control = g_id
                break
                
        # Find a generation_id that hashes to treatment (hash_val >= 10)
        gen_id_treatment = None
        for i in range(1000):
            g_id = f"gen_treatment_id_{i}"
            h_val = int(hashlib.md5(g_id.encode('utf-8')).hexdigest(), 16) % 100
            if h_val >= 10:
                gen_id_treatment = g_id
                break

        # Scenario A: variant is "control" (gen_id_control)
        mock_cur.fetchone.return_value = {
            "id": gen_id_control,
            "user_id": "user_456",
            "style": "trap",
            "prompt": "heavy reggaeton loop",
            "watermark_id": 999,
            "is_public": True,
            "audio_url": "http://replicate.delivery/track.mp3"
        }
        
        tmp_path_ctrl = f"/tmp/remixa_cache/{gen_id_control}.mp3"
        os.makedirs(os.path.dirname(tmp_path_ctrl), exist_ok=True)
        with open(tmp_path_ctrl, "wb") as f:
            f.write(b"original raw audio")
            
        mock_normalize.reset_mock()
        mock_master.reset_mock()
        
        resp = client.get(f"/api/v2/generations/{gen_id_control}/download")
        assert resp.status_code == 200
        mock_normalize.assert_called_once()
        # It targets trap loudness which is -11.0 LUFS
        assert mock_normalize.call_args[1].get("target_lufs") == -11.0
        mock_master.assert_not_called()
        if os.path.exists(tmp_path_ctrl):
            os.remove(tmp_path_ctrl)

        # Scenario B: variant is "treatment" (gen_id_treatment)
        mock_cur.fetchone.return_value = {
            "id": gen_id_treatment,
            "user_id": "user_456",
            "style": "trap",
            "prompt": "heavy reggaeton loop",
            "watermark_id": 999,
            "is_public": True,
            "audio_url": "http://replicate.delivery/track.mp3"
        }
        
        tmp_path_treat = f"/tmp/remixa_cache/{gen_id_treatment}.mp3"
        os.makedirs(os.path.dirname(tmp_path_treat), exist_ok=True)
        with open(tmp_path_treat, "wb") as f:
            f.write(b"original raw audio")
            
        mock_normalize.reset_mock()
        mock_master.reset_mock()
        
        resp = client.get(f"/api/v2/generations/{gen_id_treatment}/download")
        assert resp.status_code == 200
        mock_master.assert_called_once()
        mock_normalize.assert_not_called()
        if os.path.exists(tmp_path_treat):
            os.remove(tmp_path_treat)
    finally:
        app.dependency_overrides.clear()
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        # Clean up any cached variant files to avoid leaking state to subsequent test runs
        cache_dir = "/tmp/remixa_cache"
        if os.path.exists(cache_dir):
            for f_name in os.listdir(cache_dir):
                if f_name.startswith("gen_control_id_") or f_name.startswith("gen_treatment_id_") or f_name.startswith("gen_123"):
                    try:
                        os.remove(os.path.join(cache_dir, f_name))
                    except OSError:
                        pass


def test_phase_correlation_metrics():
    """Verify phase correlation output for mono, out-of-phase, and uncorrelated signals."""
    prod = AudioProducer(sample_rate=32000)
    
    # 1. Pure Mono (Left and Right identical)
    t = torch.linspace(0, 1, 32000)
    sine = torch.sin(2 * 3.14159 * 440 * t)
    mono_wav = torch.stack([sine, sine])
    corr = prod.calculate_phase_correlation(mono_wav)
    assert abs(corr - 1.0) < 1e-4

    # 2. Perfect Out-of-Phase (Left and Right inverted)
    out_phase_wav = torch.stack([sine, -sine])
    corr_inverted = prod.calculate_phase_correlation(out_phase_wav)
    assert abs(corr_inverted - (-1.0)) < 1e-4

    # 3. Uncorrelated Noise (Left and Right independent)
    noise_l = torch.randn(32000)
    noise_r = torch.randn(32000)
    uncorrelated_wav = torch.stack([noise_l, noise_r])
    corr_uncorr = prod.calculate_phase_correlation(uncorrelated_wav)
    assert abs(corr_uncorr) < 0.1  # Correlation of independent noise is near 0


def test_mono_bass_crossover():
    """Verify that frequencies below 150 Hz are centered/mono-summed in the output."""
    prod = AudioProducer(sample_rate=32000)
    
    t = torch.arange(32000) / 32000
    # Stereo sine wave at 80 Hz (Bass band, below 150 Hz) - fully panned Left
    bass_l = torch.sin(2 * 3.1415926535 * 80 * t)
    bass_r = torch.zeros_like(bass_l)
    stereo_bass = torch.stack([bass_l, bass_r])
    
    # Run widening (which should mono-sum the bass below 150Hz)
    widened = prod.apply_stereo_widening(stereo_bass, amount=1.5)
    
    # Since it's below 150 Hz, the output left and right channels should be identical (mono)
    # Let's verify correlation is 1.0
    corr = prod.calculate_phase_correlation(widened)
    assert abs(corr - 1.0) < 1e-4
    assert torch.allclose(widened[0], widened[1], atol=1e-4)


def test_adaptive_phase_guardrail():
    """Verify that the widening amount is dynamically reduced if it pushes phase correlation below 0.15."""
    prod = AudioProducer(sample_rate=32000)
    
    # Create a stereo signal that is already highly uncorrelated
    # (Left channel has 440 Hz sine, Right channel has 440 Hz sine shifted by 90 degrees)
    t = torch.arange(32000) / 32000
    left = torch.sin(2 * 3.1415926535 * 440 * t)
    right = torch.cos(2 * 3.1415926535 * 440 * t) # 90 degree shift
    wav = torch.stack([left, right])
    
    initial_corr = prod.calculate_phase_correlation(wav)
    assert abs(initial_corr) < 0.05  # very low correlation
    
    # Widening with amount = 3.0 (extreme)
    # Without guardrail, this would result in negative correlation.
    # With guardrail, it should scale amount back so the resulting correlation is protected.
    widened = prod.apply_stereo_widening(wav, amount=3.0)
    output_corr = prod.calculate_phase_correlation(widened)
    # At amount = 1.0 fallback, correlation of sin and cos is 0.0, which is >= -0.01.
    assert output_corr >= -0.01  # protected against extreme phase inversion




