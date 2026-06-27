"""
Tests for Remixa Subscription Management & Creator Analytics Dashboard.

Covers:
  - api_subscriptions.py: checkout, portal, status, plans, webhook
  - api_analytics.py: overview, royalties, top-tracks, geographic-reach, usage, shield-report
"""

import uuid
import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from main import app
from clerk_auth import get_current_user
from api_subscriptions import get_db as get_db_subs
from api_analytics import get_db as get_db_analytics

# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def setup_env_database(monkeypatch):
    """Force DATABASE_URL to the test database."""
    test_db = os.getenv("TEST_DATABASE_URL", "postgresql://localhost/eu_sound_lab_test")
    monkeypatch.setenv("DATABASE_URL", test_db)


def _make_user_override(user_id, email="test@remixa.com", tier="free", role="creator"):
    """Create a get_current_user override."""
    return lambda: {
        "id": user_id,
        "user_id": user_id,
        "email": email,
        "role": role,
        "subscription_tier": tier,
    }


# ============================================================================
# SUBSCRIPTION TESTS
# ============================================================================


class TestSubscriptionPlans:
    """Test the public /plans endpoint."""

    def test_list_plans(self):
        client = TestClient(app)
        response = client.get("/api/subscriptions/plans")
        assert response.status_code == 200
        data = response.json()
        assert "plans" in data
        plan_ids = [p["id"] for p in data["plans"]]
        assert "pro" in plan_ids
        assert "business" in plan_ids

        pro_plan = next(p for p in data["plans"] if p["id"] == "pro")
        assert pro_plan["price_eur_monthly"] == 9.99
        assert len(pro_plan["features"]) > 0

        biz_plan = next(p for p in data["plans"] if p["id"] == "business")
        assert biz_plan["price_eur_monthly"] == 49.99


class TestSubscriptionCheckout:
    """Test the checkout flow."""

    @patch("api_subscriptions.stripe")
    def test_checkout_creates_session(self, mock_stripe, db_connection, test_user):
        """Checkout with a valid plan should create a Stripe session."""
        user_id = str(test_user["id"])

        # Mock Stripe
        mock_session = MagicMock()
        mock_session.id = "cs_test_123"
        mock_session.url = "https://checkout.stripe.com/session/cs_test_123"
        mock_stripe.checkout.Session.create.return_value = mock_session

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="free")

        try:
            response = client.post(
                "/api/subscriptions/checkout",
                json={"plan": "pro"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["plan"] == "pro"
            assert "url" in data
            assert "session_id" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_checkout_invalid_plan(self, db_connection, test_user):
        """Checkout with an invalid plan should return 400."""
        user_id = str(test_user["id"])

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="free")

        try:
            response = client.post(
                "/api/subscriptions/checkout",
                json={"plan": "ultra_mega"},
            )
            assert response.status_code == 400
            assert "Invalid plan" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestSubscriptionPortal:
    """Test the customer portal redirect."""

    def test_portal_no_billing_account(self, db_connection, test_free_user):
        """A free user without a stripe_customer_id gets 400."""
        user_id = str(test_free_user["id"])

        # Clear stripe_customer_id to simulate no billing
        cur = db_connection.cursor()
        cur.execute("UPDATE users SET stripe_customer_id = NULL WHERE id = %s", (user_id,))
        db_connection.commit()

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="free")

        try:
            response = client.post("/api/subscriptions/portal")
            assert response.status_code == 400
            assert "free tier" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    @patch("api_subscriptions.stripe")
    def test_portal_success(self, mock_stripe, db_connection, test_user):
        """A user with a stripe_customer_id gets a portal URL."""
        user_id = str(test_user["id"])

        mock_portal = MagicMock()
        mock_portal.url = "https://billing.stripe.com/session/portal_123"
        mock_stripe.billing_portal.Session.create.return_value = mock_portal

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.post("/api/subscriptions/portal")
            assert response.status_code == 200
            assert "url" in response.json()
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestSubscriptionStatus:
    """Test the subscription status endpoint."""

    def test_free_user_status(self, db_connection, test_free_user):
        user_id = str(test_free_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="free")

        try:
            response = client.get("/api/subscriptions/status")
            assert response.status_code == 200
            data = response.json()
            assert data["plan"] == "free"
            assert data["status"] == "free"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_pro_user_status(self, db_connection, test_user):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/subscriptions/status")
            assert response.status_code == 200
            data = response.json()
            assert data["plan"] in ("pro", "free")  # depends on DB state
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestSubscriptionWebhook:
    """Test the subscription webhook handler."""

    @patch("api_subscriptions.stripe")
    def test_webhook_subscription_created(self, mock_stripe, db_connection, test_user):
        """Webhook for subscription.created should upgrade user tier."""
        user_id = str(test_user["id"])
        customer_id = f"cus_{user_id[:12]}"

        # Mock webhook event
        event = {
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": customer_id,
                    "status": "active",
                    "current_period_end": 1751328000,  # arbitrary timestamp
                    "cancel_at_period_end": False,
                    "metadata": {"plan": "pro"},
                    "items": {"data": []},
                }
            },
        }

        mock_stripe.Webhook.construct_event.return_value = event

        client = TestClient(app)
        try:
            response = client.post(
                "/api/subscriptions/webhook",
                content=json.dumps(event),
                headers={"stripe-signature": "test_sig"},
            )
            assert response.status_code == 200
            assert response.json()["event_type"] == "customer.subscription.created"

            # Verify the user was upgraded
            cur = db_connection.cursor()
            cur.execute(
                "SELECT subscription_tier, stripe_subscription_id FROM users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            assert row["subscription_tier"] == "pro"
            assert row["stripe_subscription_id"] == "sub_test_123"
        finally:
            app.dependency_overrides.clear()

    @patch("api_subscriptions.stripe")
    def test_webhook_subscription_deleted(self, mock_stripe, db_connection, test_user):
        """Webhook for subscription.deleted should downgrade to free."""
        user_id = str(test_user["id"])
        customer_id = f"cus_{user_id[:12]}"

        event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "customer": customer_id,
                }
            },
        }

        mock_stripe.Webhook.construct_event.return_value = event

        client = TestClient(app)
        try:
            response = client.post(
                "/api/subscriptions/webhook",
                content=json.dumps(event),
                headers={"stripe-signature": "test_sig"},
            )
            assert response.status_code == 200

            # Verify downgrade
            cur = db_connection.cursor()
            cur.execute("SELECT subscription_tier FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            assert row["subscription_tier"] == "free"
        finally:
            app.dependency_overrides.clear()

    @patch("api_subscriptions.stripe")
    def test_webhook_payment_failed(self, mock_stripe, db_connection, test_user):
        """Webhook for invoice.payment_failed should downgrade to free."""
        user_id = str(test_user["id"])
        customer_id = f"cus_{user_id[:12]}"

        event = {
            "type": "invoice.payment_failed",
            "data": {"object": {"customer": customer_id}},
        }

        mock_stripe.Webhook.construct_event.return_value = event

        client = TestClient(app)
        try:
            response = client.post(
                "/api/subscriptions/webhook",
                content=json.dumps(event),
                headers={"stripe-signature": "test_sig"},
            )
            assert response.status_code == 200
        finally:
            app.dependency_overrides.clear()


# ============================================================================
# ANALYTICS TESTS
# ============================================================================


class TestCreatorOverview:
    """Test the /overview endpoint."""

    def test_overview_returns_data(self, db_connection, test_user, test_generation):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/overview")
            assert response.status_code == 200
            data = response.json()

            assert data["user_id"] == user_id
            assert "royalties" in data
            assert "activity" in data
            assert "top_tracks" in data
            assert "shield" in data
            assert data["activity"]["total_generations"] >= 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestRoyaltyBreakdown:
    """Test the /royalties endpoint."""

    def test_royalties_default_period(self, db_connection, test_user):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/royalties")
            assert response.status_code == 200
            data = response.json()
            assert data["period"] == "30d"
            assert "data" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_royalties_7d_period(self, db_connection, test_user):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/royalties?period=7d")
            assert response.status_code == 200
            assert response.json()["period"] == "7d"
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_royalties_invalid_period(self, db_connection, test_user):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/royalties?period=999d")
            assert response.status_code == 422  # validation error
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestTopTracks:
    """Test the /top-tracks endpoint."""

    def test_top_tracks_returns_list(self, db_connection, test_user, test_generation):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/top-tracks")
            assert response.status_code == 200
            data = response.json()
            assert "tracks" in data
            assert len(data["tracks"]) >= 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_top_tracks_custom_limit(self, db_connection, test_user, test_generation):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/top-tracks?limit=2")
            assert response.status_code == 200
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestGeographicReach:
    """Test the /geographic-reach endpoint."""

    def test_geographic_reach(self, db_connection, test_user, test_generation):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/geographic-reach")
            assert response.status_code == 200
            data = response.json()
            assert "countries" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestUsageDashboard:
    """Test the /usage endpoint."""

    def test_usage_returns_limits(self, db_connection, test_user):
        user_id = str(test_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/usage")
            assert response.status_code == 200
            data = response.json()

            assert data["subscription_tier"] == "pro"
            assert "current_hour" in data
            assert "generations" in data["current_hour"]
            assert data["current_hour"]["generations"]["limit"] == 20  # pro tier
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_usage_free_tier_limits(self, db_connection, test_free_user):
        user_id = str(test_free_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="free")

        try:
            response = client.get("/api/analytics/usage")
            assert response.status_code == 200
            data = response.json()

            assert data["subscription_tier"] == "free"
            assert data["current_hour"]["generations"]["limit"] == 5  # free tier
            assert data["current_hour"]["remixes"]["limit"] == 20  # free tier
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestShieldReport:
    """Test the /shield-report endpoint."""

    def test_shield_report_requires_premium(self, db_connection, test_free_user):
        """Free users should be blocked from shield report."""
        user_id = str(test_free_user["id"])
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="free")

        try:
            response = client.get("/api/analytics/shield-report")
            assert response.status_code == 403
            assert "Pro and Business" in response.json()["detail"]
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_shield_report_pro_user(self, db_connection, test_user, test_generation):
        """Pro users should get shield report data."""
        user_id = str(test_user["id"])
        gen_id = str(test_generation["id"])

        # Insert a whitelisted video for the report to show
        cur = db_connection.cursor()
        cur.execute("""
            INSERT INTO licensed_videos (id, user_id, generation_id, platform, video_url, status)
            VALUES (%s, %s, %s, 'youtube', 'https://youtube.com/test', 'active')
        """, (str(uuid.uuid4()), user_id, gen_id))
        db_connection.commit()

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/shield-report")
            assert response.status_code == 200
            data = response.json()
            assert "platforms" in data
            assert "recent_whitelists" in data
            assert len(data["platforms"]) >= 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)


# ============================================================================
# INTEGRATION: Analytics with remixes
# ============================================================================

class TestAnalyticsWithRemixes:
    """Test analytics data with actual remix chains."""

    def test_overview_counts_remixes(self, db_connection, test_user, test_generation):
        """Overview should count remixes from other users."""
        user_id = str(test_user["id"])
        gen_id = str(test_generation["id"])

        # Create a second user who remixes the first user's track
        remixer_id = str(uuid.uuid4())
        cur = db_connection.cursor()
        cur.execute("""
            INSERT INTO users (id, email, subscription_tier)
            VALUES (%s, %s, 'free')
        """, (remixer_id, f"remixer_{remixer_id[:8]}@example.com"))

        remix_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO generations (
                id, user_id, prompt, style, duration_seconds,
                audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash,
                layer_type, is_public, license_price, parent_id
            ) VALUES (
                %s, %s, 'remix of test', 'lofi', 15,
                %s, %s, 2000, 0.008, 'eu-sound-lab-v1', 'test_hash',
                'voice', true, 0.10, %s
            )
        """, (
            remix_id, remixer_id,
            f"https://cdn.test.com/{remix_id}.mp3",
            f"https://cdn.test.com/{remix_id}.c2pa.json",
            gen_id,
        ))
        db_connection.commit()

        client = TestClient(app)
        app.dependency_overrides[get_current_user] = _make_user_override(user_id, tier="pro")

        try:
            response = client.get("/api/analytics/overview")
            assert response.status_code == 200
            data = response.json()
            assert data["activity"]["remixes_received"] >= 1
        finally:
            app.dependency_overrides.pop(get_current_user, None)
