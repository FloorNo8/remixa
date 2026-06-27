import pytest
import hashlib
import os
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app
from clerk_auth import get_current_user
from api_v2 import get_db

# Override conftest autouse database fixture to run offline unit tests
@pytest.fixture(scope="session", autouse=True)
def _setup_test_schema():
    pass

@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()

def test_deterministic_variant_split():
    # Verify deterministic variant assignment based on md5 hashing of generation IDs
    gen_id_1 = "gen_test_control_123" # Should map to control or treatment deterministically
    gen_id_2 = "gen_test_treatment_456"
    
    def get_variant(gen_id):
        hash_val = int(hashlib.md5(gen_id.encode('utf-8')).hexdigest(), 16) % 100
        return "control" if hash_val < 10 else "treatment"
        
    v1 = get_variant(gen_id_1)
    v2 = get_variant(gen_id_2)
    
    assert v1 in ("control", "treatment")
    assert v2 in ("control", "treatment")
    
    # Assert same ID always returns same variant
    assert get_variant(gen_id_1) == v1
    assert get_variant(gen_id_1) == v1

def test_collect_metrics_endpoint():
    # Mock current user and DB connection via dependency overrides
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user_mock123", "role": "admin"}
    
    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.cursor.return_value = mock_cur
    app.dependency_overrides[get_db] = lambda: mock_db
    
    client = TestClient(app)
    
    # Send metrics POST request
    payload = {
        "generation_id": "gen_test123",
        "action": "play_50s"
    }
    
    response = client.post("/api/v2/metrics", json=payload)
    
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "logged"
    assert res_data["action"] == "play_50s"
    assert "variant" in res_data
    
    # Verify DB call was executed
    mock_cur.execute.assert_called_once()
    sql_arg = mock_cur.execute.call_args[0][0]
    params_arg = mock_cur.execute.call_args[0][1]
    assert "INSERT INTO mastering_metrics" in sql_arg
    assert params_arg[0] == "gen_test123"
    assert params_arg[1] == "user_mock123"
    assert params_arg[3] == "play_50s"

@patch("requests.get")
@patch("c2pa_embedder.C2PAEmbedder")
@patch("producer.AudioProducer")
def test_download_endpoint_ab_treatment(
    mock_audio_producer, mock_c2pa, mock_http_get
):
    # Mock current user and DB connection via dependency overrides
    app.dependency_overrides[get_current_user] = lambda: {"user_id": "user_mock123"}
    
    mock_db = MagicMock()
    mock_cur = MagicMock()
    mock_db.cursor.return_value = mock_cur
    app.dependency_overrides[get_db] = lambda: mock_db
    
    client = TestClient(app)
    
    # Mock generation metadata fetch
    # Gen ID mapping to treatment (e.g. hash % 100 >= 10)
    treatment_gen_id = "gen_treatment_abc123"
    mock_cur.fetchone.side_effect = [
        # 1st fetch: Generation details
        {
            "audio_url": "https://replicate.delivery/some_track.mp3",
            "prompt": "heavy phonk drum beats",
            "style": "trap",
            "user_id": "user_mock123",
            "watermark_id": 999
        },
        # 2nd fetch: Dynamic mastering parameters
        {
            "drive_db": 4.50,
            "high_shelf_db": 2.80,
            "stereo_width": 1.30
        }
    ]
    
    # Mock Replicate HTTP response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake audio binary data"
    mock_http_get.return_value = mock_resp
    
    # Mock AudioProducer to write a dummy file to simulate mastering output creation
    def mock_master_track(wav_path, output_path, style, **kwargs):
        with open(output_path, "wb") as f:
            f.write(b"dummy mastered audio data")
            
    mock_producer_instance = mock_audio_producer.return_value
    mock_producer_instance.master_track.side_effect = mock_master_track
    
    cache_path = f"/tmp/remixa_cache/{treatment_gen_id}_treatment.mp3"
    if os.path.exists(cache_path):
        os.remove(cache_path)
        
    try:
        # Run request
        response = client.get(f"/api/v2/generations/{treatment_gen_id}/download")
        assert response.status_code == 200
        
        # Verify dynamic parameters were fetched and used in AudioProducer
        from unittest.mock import ANY
        mock_producer_instance.master_track.assert_called_once_with(
            wav_path=ANY,
            output_path=ANY,
            style="trap",
            drive_db=4.50,
            high_shelf_db=2.80,
            stereo_width=1.30,
            limiter_ceiling_db=-0.50,
            sub_bass_boost_db=0.00,
            persona_id="default_producer"
        )
        
        # Verify download action log in metrics DB
        db_calls = [call[0][0] for call in mock_cur.execute.call_args_list]
        assert any("INSERT INTO mastering_metrics" in sql for sql in db_calls)
    finally:
        if os.path.exists(cache_path):
            os.remove(cache_path)

def test_optimizer_computations():
    from scripts.optimize_mastering_params import compute_engagement_score
    
    # Score formula: (0.1 * play_10s) + (0.3 * play_50s) + (0.6 * play_100s) + (1.0 * share) / downloads
    
    metrics = {
        "download": 10,
        "play_10s": 8,
        "play_50s": 5,
        "play_100s": 3,
        "tiktok_share": 1
    }
    
    # Score = (0.1 * 8) + (0.3 * 5) + (0.6 * 3) + (1.0 * 1) = 0.8 + 1.5 + 1.8 + 1.0 = 5.1 / 10 = 0.51
    score = compute_engagement_score(metrics)
    assert abs(score - 0.51) < 1e-6
    
    # Division by zero safety
    assert compute_engagement_score({}) == 0.0

@patch("scripts.optimize_mastering_params.logger")
def test_optimizer_parameter_nudges(mock_logger):
    from scripts.optimize_mastering_params import optimize_params_for_style
    
    mock_cur = MagicMock()
    
    # Scenario A: Treatment outperforms Control (ES_treatment >= ES_control)
    # Param drive_db should be nudged up
    mock_cur.fetchone.return_value = {
        "drive_db": 3.0,
        "high_shelf_db": 2.0,
        "stereo_width": 1.25
    }
    
    # Fetch returns count values for style
    mock_cur.fetchall.return_value = [
        {"variant": "treatment", "action": "download", "count": 10},
        {"variant": "treatment", "action": "play_100s", "count": 9}, # high treatment score
        {"variant": "control", "action": "download", "count": 10},
        {"variant": "control", "action": "play_100s", "count": 2}   # low control score
    ]
    
    optimize_params_for_style(mock_cur, "dnb")
    
    # Verify UPDATE statement was called with incremented parameters
    updates = [call[0][0] for call in mock_cur.execute.call_args_list if "UPDATE production_team_parameters" in call[0][0]]
    assert len(updates) > 0
    update_params = [call[0][1] for call in mock_cur.execute.call_args_list if "UPDATE production_team_parameters" in call[0][0]][0]
    # Check that drive_db was increased (from 3.0 to 3.1)
    assert float(update_params[0]) > 3.0
    assert float(update_params[1]) > 2.0
    assert float(update_params[2]) > 1.25

    # Scenario B: Treatment performs worse (ES_treatment < ES_control - 0.05)
    # Param drive_db should be reduced
    mock_cur.reset_mock()
    mock_cur.fetchone.return_value = {
        "drive_db": 3.0,
        "high_shelf_db": 2.0,
        "stereo_width": 1.25
    }
    
    mock_cur.fetchall.return_value = [
        {"variant": "treatment", "action": "download", "count": 10},
        {"variant": "treatment", "action": "play_100s", "count": 1}, # low treatment score
        {"variant": "control", "action": "download", "count": 10},
        {"variant": "control", "action": "play_100s", "count": 8}   # high control score
    ]
    
    optimize_params_for_style(mock_cur, "lofi")
    
    update_params_desc = [call[0][1] for call in mock_cur.execute.call_args_list if "UPDATE production_team_parameters" in call[0][0]][0]
    # Check that drive_db was decreased (from 3.0 to 2.8)
    assert float(update_params_desc[0]) < 3.0
    assert float(update_params_desc[1]) < 2.0
    assert float(update_params_desc[2]) < 1.25
