import uuid
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
from clerk_auth import get_current_user
from api_v2 import get_db

@patch("c2pa_embedder.C2PAEmbedder.embed_waveform_watermark")
def test_download_mode_parameter_and_telemetry(mock_embed_watermark, db_connection, test_user):
    """
    Test that download_generation handles mode=raw vs mode=mastered correctly.
    It should store telemetry values in the database, and GET /generations/{id}
    should return them.
    """
    user_id = str(test_user["id"])
    gen_id = str(uuid.uuid4())
    
    # Pre-seed a generation
    cursor = db_connection.cursor()
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, earnings, remix_count
        ) VALUES 
        (%s, %s, 'test telemetry track', 'trap', 15, 'https://replicate.delivery/test.mp3', 'https://cdn.com/test.json', 1000, 0.0, 'v2', 'hash1', 'base', true, 0.1, 0, 0)
    """, (gen_id, user_id))
    db_connection.commit()

    # Authenticate as test user
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": user_id,
        "id": user_id,
        "email": "user@test.com",
        "role": "user"
    }
    app.dependency_overrides[get_db] = lambda: db_connection

    client = TestClient(app)
    try:
        # 1. Test invalid mode returns 400
        response = client.get(f"/api/v2/generations/{gen_id}/download?mode=invalid")
        assert response.status_code == 400
        assert "Invalid mode" in response.json()["detail"]

        # 2. Test mode=raw download flow
        # In testing/mock, it fallback generates a sine wave, saves raw metrics, and returns the file
        response = client.get(f"/api/v2/generations/{gen_id}/download?mode=raw")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"
        
        # Verify database has raw telemetry columns filled but not mastered
        cursor.execute("SELECT raw_lufs, raw_peak, mastered_lufs, mastered_peak FROM generations WHERE id = %s", (gen_id,))
        row = cursor.fetchone()
        assert row["raw_lufs"] is not None
        assert row["raw_peak"] is not None
        assert row["mastered_lufs"] is None
        assert row["mastered_peak"] is None

        # 3. Test mode=mastered download flow
        response = client.get(f"/api/v2/generations/{gen_id}/download?mode=mastered")
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/mpeg"

        # Verify database has raw AND mastered telemetry columns filled
        cursor.execute("SELECT raw_lufs, raw_peak, mastered_lufs, mastered_peak FROM generations WHERE id = %s", (gen_id,))
        row = cursor.fetchone()
        assert row["raw_lufs"] is not None
        assert row["raw_peak"] is not None
        assert row["mastered_lufs"] is not None
        assert row["mastered_peak"] is not None

        # 4. Test GET /generations/{generation_id} returns telemetry stats
        detail_response = client.get(f"/api/v2/generations/{gen_id}")
        assert detail_response.status_code == 200
        data = detail_response.json()
        assert "raw_lufs" in data
        assert "mastered_lufs" in data
        assert "raw_peak" in data
        assert "mastered_peak" in data
        assert data["raw_lufs"] == row["raw_lufs"]
        assert data["mastered_lufs"] == row["mastered_lufs"]
        assert data["raw_peak"] == row["raw_peak"]
        assert data["mastered_peak"] == row["mastered_peak"]
        
    finally:
        app.dependency_overrides.clear()
        cursor.close()
