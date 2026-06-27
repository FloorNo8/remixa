"""
Unit tests for user-level compute cost ledger (fact_user_compute_cogs) and admin COGS lookup endpoint.
"""
import uuid
import pytest
import os
from fastapi.testclient import TestClient
from main import app
from clerk_auth import get_current_user
from api_v2 import get_db as get_db_v2
from admin_api import get_db as get_db_admin
from unittest.mock import AsyncMock, patch

@pytest.fixture(autouse=True)
def setup_env_database(monkeypatch):
    """Force redirect DATABASE_URL to TEST_DATABASE_URL during test run."""
    test_db = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/eu_sound_lab_test")
    monkeypatch.setenv("DATABASE_URL", test_db)

def test_admin_cogs_access_and_aggregations(db_connection, test_user):
    """
    Test that admins can access user compute COGS endpoint, non-admins are rejected,
    and aggregates are calculated correctly.
    """
    user_id = str(test_user["id"])
    gen_id = str(uuid.uuid4())
    
    # Pre-seed generations and cogs records
    cursor = db_connection.cursor()
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, earnings, remix_count
        ) VALUES 
        (%s, %s, 'test cogs track', 'lofi', 10, 'https://replicate.delivery/test.mp3', 'https://cdn.com/test.json', 1000, 0.0, 'v1', 'hash1', 'base', true, 0.1, 0, 0)
    """, (gen_id, user_id))
    
    cursor.execute("""
        INSERT INTO fact_user_compute_cogs (
            user_id, generation_id, provider, resource_type, quantity, unit_cost_eur
        ) VALUES 
        (%s, %s, 'replicate', 'gpu_a10g_seconds', 60.0, 0.00038),
        (%s, %s, 'fly.io', 'audio_processing_cogs', 1.0, 0.001)
    """, (user_id, gen_id, user_id, gen_id))
    db_connection.commit()

    # 1. Test as standard user (Role.USER / Role.CREATOR) -> Expect 403
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "user_id": user_id,
        "email": "user@test.com",
        "role": "creator",
        "subscription_tier": "free"
    }
    app.dependency_overrides[get_db_admin] = lambda: db_connection
    app.dependency_overrides[get_db_v2] = lambda: db_connection

    client = TestClient(app)
    try:
        response = client.get(f"/api/admin/users/{user_id}/cogs")
        assert response.status_code == 403

        # 2. Test as Admin user -> Expect 200 and valid payload
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-id-999",
            "user_id": "admin-id-999",
            "email": "admin@test.com",
            "role": "admin",
            "subscription_tier": "free"
        }
        
        response = client.get(f"/api/admin/users/{user_id}/cogs")
        assert response.status_code == 200
        data = response.json()
        
        # Verify correctness of computation
        # Total cogs = 60.0 * 0.00038 + 1.0 * 0.001 = 0.0228 + 0.001 = 0.0238
        assert data["user_id"] == user_id
        assert abs(data["total_cogs_eur"] - 0.0238) < 1e-6
        assert data["total_generations"] == 1
        assert abs(data["cost_per_generation_eur"] - 0.0238) < 1e-6
        assert abs(data["provider_breakdown"]["replicate"] - 0.0228) < 1e-6
        assert abs(data["provider_breakdown"]["fly_io"] - 0.001) < 1e-6
        assert abs(data["compute_stats"]["gpu_seconds"] - 60.0) < 1e-6
        assert data["compute_stats"]["processing_sessions"] == 1
        # Margin: ((20 - 0.0238) / 20) * 100
        expected_margin = ((20.0 - 0.0238) / 20.0) * 100.0
        assert abs(data["margin_pct"] - expected_margin) < 1e-6

    finally:
        app.dependency_overrides.clear()
        cursor.close()

def test_generation_logs_replicate_cogs(db_connection, test_user):
    """
    Test that POST /api/v1/generate successfully adds a cogs log.
    """
    user_id = str(test_user["id"])
    
    app.dependency_overrides[get_current_user] = lambda: {
        "id": user_id,
        "user_id": user_id,
        "email": "user@test.com",
        "role": "creator",
        "subscription_tier": "free"
    }
    app.dependency_overrides[get_db_v2] = lambda: db_connection
    app.dependency_overrides[get_db_admin] = lambda: db_connection

    # Mock rate limits and replicate calls
    import main
    app.dependency_overrides[main.check_rate_limit] = lambda: True

    stub_result = {
        "audio_url": "https://replicate.delivery/test.mp3",
        "generation_time_ms": 15000, # 15 seconds
        "is_stub": True,
    }

    client = TestClient(app)
    try:
        with patch("main.generate_music", new_callable=AsyncMock, return_value=stub_result):
            response = client.post("/api/v1/generate", json={
                "prompt": "lofi hip hop chill beats",
                "style": "lofi",
                "duration": 15
            })
            assert response.status_code == 200
            gen_data = response.json()
            gen_id = gen_data["generation_id"]

        # Assert cogs table has a replicate entry for this generation
        cursor = db_connection.cursor()
        cursor.execute("""
            SELECT provider, resource_type, quantity, unit_cost_eur, total_cost_eur
            FROM fact_user_compute_cogs
            WHERE generation_id = %s
        """, (gen_id,))
        row = cursor.fetchone()
        assert row is not None
        assert row["provider"] == "replicate"
        assert row["resource_type"] == "gpu_a10g_seconds"
        assert abs(float(row["quantity"]) - 15.0) < 1e-6
        assert abs(float(row["unit_cost_eur"]) - 0.00038) < 1e-6
        assert abs(float(row["total_cost_eur"]) - 0.0057) < 1e-6
        cursor.close()

    finally:
        app.dependency_overrides.clear()


def test_billing_telemetry_endpoint(db_connection, test_user):
    """
    Test GET /api/admin/billing/telemetry aggregates platform figures correctly
    and enforces Role.ADMIN access control, using deltas to ignore pre-seeded data.
    """
    client = TestClient(app)

    # 1. Fetch initial billing telemetry as admin
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "admin-id-777",
        "user_id": "admin-id-777",
        "email": "admin@test.com",
        "role": "admin",
        "subscription_tier": "free"
    }
    app.dependency_overrides[get_db_admin] = lambda: db_connection
    app.dependency_overrides[get_db_v2] = lambda: db_connection

    try:
        response = client.get("/api/admin/billing/telemetry")
        assert response.status_code == 200
        initial_data = response.json()
    finally:
        app.dependency_overrides.clear()

    # 2. Seed database records
    cursor = db_connection.cursor()
    
    new_user_uuid = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO users (id, email, subscription_tier, subscription_status, stripe_customer_id)
        VALUES (%s, %s, 'pro', 'active', %s)
    """, (new_user_uuid, f"telemetry_{new_user_uuid[:8]}@example.com", f"cus_{new_user_uuid[:12]}"))
    
    # Add topup to ledger
    cursor.execute("""
        INSERT INTO user_ledger (user_id, transaction_type, amount, description)
        VALUES (%s, 'topup', 50.00, 'Stripe balance top-up')
    """, (new_user_uuid,))
    
    # Add generation and remix generations
    gen_id1 = str(uuid.uuid4())
    gen_id2 = str(uuid.uuid4()) # child remix
    
    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, earnings, remix_count
        ) VALUES 
        (%s, %s, 'test parent', 'lofi', 10, 'https://cdn.com/a.mp3', 'https://cdn.com/a.json', 1000, 0.012, 'v1', 'hash1', 'base', true, 0.1, 0, 1)
    """, (gen_id1, new_user_uuid))

    cursor.execute("""
        INSERT INTO generations (
            id, user_id, prompt, style, duration_seconds,
            audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash,
            layer_type, is_public, license_price, earnings, remix_count, parent_id
        ) VALUES 
        (%s, %s, 'test remix', 'lofi', 10, 'https://cdn.com/b.mp3', 'https://cdn.com/b.json', 1000, 0.012, 'v1', 'hash1', 'voice', true, 0.1, 0, 0, %s)
    """, (gen_id2, new_user_uuid, gen_id1))
    
    # Call distribute_remix_royalties_v2 to populate ledger entries dynamically
    cursor.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (new_user_uuid, gen_id1, gen_id2))
    
    # Add fact_user_compute_cogs entries
    cursor.execute("""
        INSERT INTO fact_user_compute_cogs (
            user_id, generation_id, provider, resource_type, quantity, unit_cost_eur
        ) VALUES 
        (%s, %s, 'replicate', 'gpu_a10g_seconds', 30.0, 0.00038),
        (%s, %s, 'fly.io', 'audio_processing_cogs', 1.0, 0.001)
    """, (new_user_uuid, gen_id1, new_user_uuid, gen_id2))
    
    db_connection.commit()
    cursor.close()

    try:
        # Standard User (Creator) -> Forbidden 403
        app.dependency_overrides[get_current_user] = lambda: {
            "id": new_user_uuid,
            "user_id": new_user_uuid,
            "email": "user@test.com",
            "role": "creator",
            "subscription_tier": "pro"
        }
        app.dependency_overrides[get_db_admin] = lambda: db_connection
        app.dependency_overrides[get_db_v2] = lambda: db_connection

        response = client.get("/api/admin/billing/telemetry")
        assert response.status_code == 403

        # Admin -> OK 200 and verify calculations
        app.dependency_overrides[get_current_user] = lambda: {
            "id": "admin-id-777",
            "user_id": "admin-id-777",
            "email": "admin@test.com",
            "role": "admin",
            "subscription_tier": "free"
        }
        
        response = client.get("/api/admin/billing/telemetry")
        assert response.status_code == 200
        data = response.json()
        
        # Verify MRR delta = 1 pro user * 9.99 = 9.99
        mrr_delta = data["mrr_eur"] - initial_data["mrr_eur"]
        assert abs(mrr_delta - 9.99) < 1e-6

        # Top-ups delta = 50.00, Remixes delta = 1 * 0.10 = 0.10 -> transactional revenue delta = 50.10
        tx_delta = data["transactional_revenue_eur"] - initial_data["transactional_revenue_eur"]
        assert abs(tx_delta - 50.10) < 1e-6

        # Total revenue delta = 9.99 + 50.10 = 60.09
        rev_delta = data["total_revenue_eur"] - initial_data["total_revenue_eur"]
        assert abs(rev_delta - 60.09) < 1e-6
        
        # COGS verification deltas
        # replicate_gpu = 30 * 0.00038 = 0.0114
        rep_delta = data["cogs"]["replicate_gpu_eur"] - initial_data["cogs"]["replicate_gpu_eur"]
        assert abs(rep_delta - 0.0114) < 1e-6

        # fly_io_processing = 1 * 0.001 = 0.001
        fly_delta = data["cogs"]["fly_io_processing_eur"] - initial_data["cogs"]["fly_io_processing_eur"]
        assert abs(fly_delta - 0.001) < 1e-6

        # cloudflare_r2 = 2 generations * 0.0001 = 0.0002
        r2_delta = data["cogs"]["cloudflare_r2_storage_eur"] - initial_data["cogs"]["cloudflare_r2_storage_eur"]
        assert abs(r2_delta - 0.0002) < 1e-6

        # stripe_fees = 50.00 * 0.015 + (1 topup + 1 remix) * 0.01 = 0.75 + 0.02 = 0.77
        stripe_delta = data["cogs"]["stripe_fees_eur"] - initial_data["cogs"]["stripe_fees_eur"]
        assert abs(stripe_delta - 0.77) < 1e-6

        # total_cogs delta = 0.0114 + 0.001 + 0.0002 + 0.77 = 0.7826
        total_cogs_delta = data["cogs"]["total_cogs_eur"] - initial_data["cogs"]["total_cogs_eur"]
        assert abs(total_cogs_delta - 0.7826) < 1e-6
        
        # Royalties: creators = 1 remix * 0.04 = 0.04, producers = 1 remix * 0.03 = 0.03 -> total = 0.07
        royalty_delta = data["royalty_obligations_eur"] - initial_data["royalty_obligations_eur"]
        assert abs(royalty_delta - 0.07) < 1e-6
        
        # Net Profit delta = 60.09 - 0.7826 - 0.07 = 59.2374
        profit_delta = data["net_profit_eur"] - initial_data["net_profit_eur"]
        assert abs(profit_delta - 59.2374) < 1e-6

        # Margin status is healthy
        assert data["margin_status"] == "healthy"

    finally:
        app.dependency_overrides.clear()

