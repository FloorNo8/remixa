import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_mastering_analytics_rbac_failure(db_connection, test_user):
    """
    Verify that standard users without admin role are forbidden
    from calling the mastering analytics endpoint.
    """
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db

    # Overwrite auth user as a standard user
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": str(test_user['id']),
        "id": str(test_user['id']),
        "email": "user@test.com",
        "role": "user"  # standard role
    }
    app.dependency_overrides[get_db] = lambda: db_connection

    client = TestClient(app)
    try:
        response = client.get("/api/v2/admin/mastering-analytics")
        assert response.status_code == 403
        assert "Insufficient permissions" in response.text
    finally:
        app.dependency_overrides.clear()


def test_mastering_analytics_success(db_connection, test_user):
    """
    Verify that an admin user can successfully query the endpoint
    and receive accurate aggregate stats and rates.
    """
    from main import app
    from clerk_auth import get_current_user
    from api_v2 import get_db

    # Overwrite auth user as an admin
    admin_id = str(uuid.uuid4())
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": admin_id,
        "id": admin_id,
        "email": "admin@test.com",
        "role": "admin"  # admin role
    }
    app.dependency_overrides[get_db] = lambda: db_connection

    cursor = db_connection.cursor()

    try:
        # Create user record
        cursor.execute("""
            INSERT INTO users (id, email, subscription_tier, role)
            VALUES (%s, 'admin@test.com', 'pro', 'admin')
        """, (admin_id,))

        # Create two generations with different styles
        gen_id_ambient = str(uuid.uuid4())
        gen_id_trap = str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO generations (
                id, user_id, prompt, style, duration_seconds,
                audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash,
                layer_type, is_public, license_price, earnings, remix_count
            ) VALUES 
            (%s, %s, 'ambient track', 'ambient', 15, 'https://cdn.com/a.mp3', 'https://cdn.com/a.json', 1000, 0.0, 'v2', 'hash1', 'base', true, 0.1, 0, 0),
            (%s, %s, 'trap track', 'trap', 15, 'https://cdn.com/t.mp3', 'https://cdn.com/t.json', 1000, 0.0, 'v2', 'hash2', 'base', true, 0.1, 0, 0)
        """, (gen_id_ambient, admin_id, gen_id_trap, admin_id))

        # Insert A/B metrics
        # Ambient: 10 plays of 10s (control), 6 plays of 50s (control), 4 plays of 100s (control), 1 share (control)
        # Trap: 20 plays of 10s (treatment), 15 plays of 50s (treatment), 10 plays of 100s (treatment), 2 shares (treatment)
        cursor.execute("""
            INSERT INTO mastering_metrics (generation_id, variant, action) VALUES
            -- Ambient Control
            (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'),
            (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'),
            (%s, 'control', 'play_10s'), (%s, 'control', 'play_10s'),
            (%s, 'control', 'play_50s'), (%s, 'control', 'play_50s'), (%s, 'control', 'play_50s'), (%s, 'control', 'play_50s'),
            (%s, 'control', 'play_50s'), (%s, 'control', 'play_50s'),
            (%s, 'control', 'play_100s'), (%s, 'control', 'play_100s'), (%s, 'control', 'play_100s'), (%s, 'control', 'play_100s'),
            (%s, 'control', 'tiktok_share'),

            -- Trap Treatment
            (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'),
            (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'),
            (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'),
            (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'),
            (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'), (%s, 'treatment', 'play_10s'),
            (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'),
            (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'),
            (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'),
            (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'), (%s, 'treatment', 'play_50s'),
            (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'),
            (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'),
            (%s, 'treatment', 'play_100s'), (%s, 'treatment', 'play_100s'),
            (%s, 'treatment', 'tiktok_share'), (%s, 'treatment', 'tiktok_share')
        """, (
            # Ambient Control plays
            gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient,
            gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient,
            # Ambient Control play_50s
            gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient,
            # Ambient Control play_100s
            gen_id_ambient, gen_id_ambient, gen_id_ambient, gen_id_ambient,
            # Ambient Control share
            gen_id_ambient,

            # Trap Treatment plays (20)
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            # Trap Treatment play_50s (15)
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            # Trap Treatment play_100s (10)
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap, gen_id_trap,
            # Trap Treatment shares (2)
            gen_id_trap, gen_id_trap
        ))

        db_connection.commit()

        client = TestClient(app)
        response = client.get("/api/v2/admin/mastering-analytics")
        assert response.status_code == 200

        data = response.json()
        assert "global" in data
        assert "by_style" in data

        # Check Ambient Control metrics
        ambient_ctrl = data["by_style"]["ambient"]["control"]
        assert ambient_ctrl["metrics"]["play_10s"] == 10
        assert ambient_ctrl["metrics"]["play_50s"] == 6
        assert ambient_ctrl["metrics"]["play_100s"] == 4
        assert ambient_ctrl["metrics"]["tiktok_share"] == 1
        assert ambient_ctrl["rates"]["midpoint_rate"] == 0.60
        assert ambient_ctrl["rates"]["completion_rate"] == 0.40
        assert ambient_ctrl["rates"]["share_rate"] == 0.10

        # Check Trap Treatment metrics
        trap_treat = data["by_style"]["trap"]["treatment"]
        assert trap_treat["metrics"]["play_10s"] == 20
        assert trap_treat["metrics"]["play_50s"] == 15
        assert trap_treat["metrics"]["play_100s"] == 10
        assert trap_treat["metrics"]["tiktok_share"] == 2
        assert trap_treat["rates"]["midpoint_rate"] == 0.75
        assert trap_treat["rates"]["completion_rate"] == 0.50
        assert trap_treat["rates"]["share_rate"] == 0.10

        # Check Global stats aggregates
        global_ctrl = data["global"]["control"]
        assert global_ctrl["metrics"]["play_10s"] == 10
        assert global_ctrl["metrics"]["tiktok_share"] == 1

        global_treat = data["global"]["treatment"]
        assert global_treat["metrics"]["play_10s"] == 20
        assert global_treat["metrics"]["tiktok_share"] == 2

    finally:
        app.dependency_overrides.clear()
