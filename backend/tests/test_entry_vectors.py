"""
Tests for Collaborative Utility Engine Entry Vectors (FN8-686 implementation).
Media Creator Lead, Game Developer API Lead, and Social Artist Co-Creation Lead endpoints.
"""

import uuid
import pytest
import os
from fastapi.testclient import TestClient
from main import app
from clerk_auth import get_current_user
from rbac import Role

@pytest.fixture(autouse=True)
def setup_env_database(monkeypatch):
    """Force redirect DATABASE_URL to TEST_DATABASE_URL during test run."""
    test_db = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/eu_sound_lab_test")
    monkeypatch.setenv("DATABASE_URL", test_db)

def test_batch_whitelisting_rbac_and_flow(db_connection, test_user, test_generation):
    """
    Verify batch whitelisting access control, bulk insertion, savepoint rollbacks for duplicates,
    and platform validation.
    """
    user_id = str(test_user["id"])
    gen_id = str(test_generation["id"])
    video_url_1 = "https://www.youtube.com/watch?v=batch_remix_1"
    video_url_2 = "https://www.youtube.com/watch?v=batch_remix_2"
    duplicate_url = "https://www.youtube.com/watch?v=batch_remix_duplicate"

    client = TestClient(app)
    try:
        # Pre-seed one duplicate URL
        cur = db_connection.cursor()
        cur.execute("""
            INSERT INTO licensed_videos (id, user_id, generation_id, platform, video_url, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
        """, (str(uuid.uuid4()), user_id, gen_id, "youtube", duplicate_url))
        db_connection.commit()
        cur.close()

        # 1. Standard user (free subscription) -> Expect 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "free"
        }
        
        response = client.post("/api/v1/shield/batch-whitelist", json={
            "generation_id": gen_id,
            "platform": "youtube",
            "video_urls": [video_url_1, video_url_2]
        })
        assert response.status_code == 403
        assert "premium feature" in response.json()["detail"]

        # 2. Premium user (pro subscription) -> Expect 200 OK with mixed results (success & duplicates isolated)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }
        
        response = client.post("/api/v1/shield/batch-whitelist", json={
            "generation_id": gen_id,
            "platform": "youtube",
            "video_urls": [video_url_1, video_url_2, duplicate_url]
        })
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["whitelisted"]) == 2
        assert len(data["errors"]) == 1
        assert data["whitelisted"][0]["video_url"] == video_url_1
        assert data["whitelisted"][1]["video_url"] == video_url_2
        assert data["errors"][0]["url"] == duplicate_url
        assert "already been whitelisted" in data["errors"][0]["error"]

        # 3. Invalid platform -> Expect 400 Bad Request
        response = client.post("/api/v1/shield/batch-whitelist", json={
            "generation_id": gen_id,
            "platform": "invalid_plat",
            "video_urls": [video_url_1]
        })
        assert response.status_code == 400

        # 4. Generation not found -> Expect 404
        missing_gen = str(uuid.uuid4())
        response = client.post("/api/v1/shield/batch-whitelist", json={
            "generation_id": missing_gen,
            "platform": "youtube",
            "video_urls": ["https://youtube.com/watch?v=missing"]
        })
        assert response.status_code == 404

    finally:
        app.dependency_overrides.clear()


def test_game_dev_stems_endpoint(db_connection, test_user, test_generation):
    """
    Verify stems endpoint returns stem metadata and fallback parameters.
    """
    user_id = str(test_user["id"])
    gen_id = str(test_generation["id"])

    client = TestClient(app)
    try:
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }

        # Request stems
        response = client.get(f"/api/v2/generations/{gen_id}/stems")
        assert response.status_code == 200
        data = response.json()

        assert data["generation_id"] == gen_id
        assert "dsp_parameters" in data
        assert len(data["stems"]) >= 3  # Fallback dynamic stems: drums, vocals, bass
        assert data["dsp_parameters"]["drive_db"] > 0
        assert data["dsp_parameters"]["high_shelf_db"] > 0
        assert data["dsp_parameters"]["stereo_width"] > 0
        assert data["dsp_parameters"]["limiter_ceiling_db"] == -2.0

    finally:
        app.dependency_overrides.clear()


def test_social_artist_branch_info_endpoint(db_connection, test_user, test_generation):
    """
    Verify branch info endpoint returns branch counts, splits, and views.
    """
    user_id = str(test_user["id"])
    gen_id = str(test_generation["id"])

    client = TestClient(app)
    try:
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }

        # Request branch info
        response = client.get(f"/api/v2/generations/{gen_id}/branch-info")
        assert response.status_code == 200
        data = response.json()

        assert data["generation_id"] == gen_id
        assert "royalties_split" in data
        assert data["active_branches_count"] >= 0
        assert data["total_derivative_views"] >= 1500  # Default mock baseline
        assert data["royalties_split"]["parent_creator_share"] == 70.0  # Base track full creator share

    finally:
        app.dependency_overrides.clear()
