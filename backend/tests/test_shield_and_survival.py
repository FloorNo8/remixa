"""
Tests for Remixa Shield (Whitelisting API) and Catalog Survival (GDPR Immunity).
"""

import uuid
import pytest
import os
from fastapi.testclient import TestClient
from main import app
from clerk_auth import get_current_user
from api_shield import get_db as get_db_shield
from gdpr_tools import GDPRTools

@pytest.fixture(autouse=True)
def setup_env_database(monkeypatch):
    """Force redirect DATABASE_URL to TEST_DATABASE_URL during test run."""
    test_db = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/eu_sound_lab_test")
    monkeypatch.setenv("DATABASE_URL", test_db)

def test_shield_whitelisting_rbac_and_flow(db_connection, test_user, test_generation):
    """
    Verify whitelisting endpoint access controls, duplicate registration prevention,
    validation failures, and public checking flow.
    We do NOT override get_db_shield here, so that the real get_db connection logic runs and gets covered.
    """
    user_id = str(test_user["id"])
    gen_id = str(test_generation["id"])
    video_url = "https://www.youtube.com/watch?v=viral_remix_123"

    client = TestClient(app)
    try:
        # 1. Standard user (free subscription) -> Expect 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "free"
        }
        
        response = client.post("/api/v1/shield/whitelist", json={
            "generation_id": gen_id,
            "platform": "youtube",
            "video_url": video_url
        })
        assert response.status_code == 403
        assert "premium feature" in response.json()["detail"]

        # 2. Premium user (pro subscription) -> Expect 200 OK
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }
        
        response = client.post("/api/v1/shield/whitelist", json={
            "generation_id": gen_id,
            "platform": "youtube",
            "video_url": video_url
        })
        assert response.status_code == 200
        data = response.json()
        entry_id = data["id"]
        assert data["video_url"] == video_url
        assert data["generation_id"] == gen_id
        assert data["status"] == "active"

        # 3. Duplicate registration -> Expect 400 Bad Request
        response = client.post("/api/v1/shield/whitelist", json={
            "generation_id": gen_id,
            "platform": "youtube",
            "video_url": video_url
        })
        assert response.status_code == 400

        # 4. Try whitelisting for a non-existent generation -> Expect 404 Not Found
        missing_gen = str(uuid.uuid4())
        response = client.post("/api/v1/shield/whitelist", json={
            "generation_id": missing_gen,
            "platform": "youtube",
            "video_url": "https://youtube.com/watch?v=another"
        })
        assert response.status_code == 404

        # 5. Try whitelisting with an invalid platform -> Expect 400 Bad Request
        response = client.post("/api/v1/shield/whitelist", json={
            "generation_id": gen_id,
            "platform": "invalid_platform",
            "video_url": "https://youtube.com/watch?v=another"
        })
        assert response.status_code == 400

        # 6. Try whitelisting for someone else's generation -> Expect 403 Forbidden
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "stranger-user-uuid",
            "user_id": "stranger-user-uuid",
            "email": "stranger@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }
        response = client.post("/api/v1/shield/whitelist", json={
            "generation_id": gen_id,
            "platform": "youtube",
            "video_url": "https://youtube.com/watch?v=another"
        })
        assert response.status_code == 403

        # Restore auth to owner
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }

        # 7. Public Check - Valid Whitelist
        check_response = client.get("/api/v1/shield/whitelist/check", params={"video_url": video_url})
        assert check_response.status_code == 200
        check_data = check_response.json()
        assert check_data["cleared"] is True
        assert check_data["video_url"] == video_url

        # 8. Public Check - Inactive Whitelist
        # Manually toggle status to inactive
        cursor = db_connection.cursor()
        cursor.execute("UPDATE licensed_videos SET status = 'inactive' WHERE id = %s", (entry_id,))
        db_connection.commit()
        cursor.close()

        check_response = client.get("/api/v1/shield/whitelist/check", params={"video_url": video_url})
        assert check_response.status_code == 200
        assert check_response.json()["cleared"] is False
        assert "inactive" in check_response.json()["reason"]

        # Restore status to active
        cursor = db_connection.cursor()
        cursor.execute("UPDATE licensed_videos SET status = 'active' WHERE id = %s", (entry_id,))
        db_connection.commit()
        cursor.close()

        # 9. Public Check - Missing URL
        check_response = client.get("/api/v1/shield/whitelist/check", params={"video_url": "https://unknown.com/123"})
        assert check_response.status_code == 200
        assert check_response.json()["cleared"] is False

        # 10. Delete whitelist entry - Unauthorized (different user)
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "different-user-uuid",
            "user_id": "different-user-uuid",
            "email": "diff@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }
        del_resp = client.delete(f"/api/v1/shield/whitelist/{entry_id}")
        assert del_resp.status_code == 403

        # 11. Delete non-existent whitelist entry -> Expect 404 Not Found
        app.dependency_overrides[get_current_user] = lambda: {
            "id": user_id,
            "user_id": user_id,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }
        del_resp = client.delete(f"/api/v1/shield/whitelist/{uuid.uuid4()}")
        assert del_resp.status_code == 404

        # 12. Delete whitelist entry - Authorized (owner)
        del_resp = client.delete(f"/api/v1/shield/whitelist/{entry_id}")
        assert del_resp.status_code == 200

    finally:
        app.dependency_overrides.clear()


def test_catalog_survival_immunity_on_gdpr_erasure(db_connection, test_user, test_generation):
    """
    Verify GDPR erase logic handles Catalog Survival/Immunity:
    - If a user has a generation that has been remixed or whitelisted, they are anonymized, NOT hard deleted.
    - If they have no remixes/licenses, they are hard deleted.
    """
    user_id = str(test_user["id"])
    gen_id = str(test_generation["id"])
    
    tools = GDPRTools(database_url=os.getenv("TEST_DATABASE_URL"), storage_url="")
    
    # CASE 1: User has a whitelisted video on their generation
    cursor = db_connection.cursor()
    cursor.execute("""
        INSERT INTO licensed_videos (id, user_id, generation_id, platform, video_url, status)
        VALUES (%s, %s, %s, 'youtube', 'https://youtube.com/watch?v=immunity_test', 'active')
    """, (str(uuid.uuid4()), user_id, gen_id))
    db_connection.commit()
    
    # Run immediate delete -> Should anonymize instead of deleting row
    result = tools.delete_user_data(user_id, immediate=True)
    assert result["status"] == "erased_or_deleted"
    
    # Verify user row still exists but email is anonymized and is_erased is TRUE
    cursor.execute("SELECT email, is_erased FROM users WHERE id = %s", (user_id,))
    user_row = cursor.fetchone()
    assert user_row is not None
    assert "erased_" in user_row["email"]
    assert user_row["is_erased"] is True
    
    # Verify generation row STILL exists (anonymized prompt)
    cursor.execute("SELECT id, prompt FROM generations WHERE id = %s", (gen_id,))
    gen_row = cursor.fetchone()
    assert gen_row is not None
    assert gen_row["prompt"] is None
    
    # CASE 2: User with NO remixes or whitelisted videos is hard deleted
    other_user_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, stripe_customer_id)
        VALUES (%s, 'other@test.com', 'free', 'cus_other123')
    """, (other_user_id,))
    db_connection.commit()
    
    result2 = tools.delete_user_data(other_user_id, immediate=True)
    assert result2["status"] == "erased_or_deleted"
    
    # Verify user row is completely deleted
    cursor.execute("SELECT * FROM users WHERE id = %s", (other_user_id,))
    assert cursor.fetchone() is None
    
    cursor.close()
