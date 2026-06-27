"""
Remixa Subscription Management — Pro / Business Tier Checkout & Lifecycle

Endpoints:
  POST /api/subscriptions/checkout    — Create a Stripe Checkout Session for Pro or Business
  POST /api/subscriptions/portal      — Redirect to Stripe Customer Portal (manage/cancel)
  GET  /api/subscriptions/status      — Current subscription status for the logged-in user
  POST /api/subscriptions/webhook     — Stripe webhook for subscription lifecycle events

Pricing:
  Pro:      €9.99/month   — 20 gen/hr, 100 remixes/hr, Shield whitelisting (own only)
  Business: €49.99/month  — 100 gen/hr, 500 remixes/hr, Shield whitelisting (any), API keys, batch ops
"""

import stripe
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import structlog
from clerk_auth import get_current_user

logger = structlog.get_logger()

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# ============================================================================
# PRICING CONFIGURATION
# ============================================================================

SUBSCRIPTION_PLANS = {
    "pro": {
        "name": "Remixa Pro",
        "price_eur_monthly": 9.99,
        "stripe_price_id": os.getenv("STRIPE_PRO_PRICE_ID", "price_pro_placeholder"),
        "features": [
            "20 generations/hour",
            "100 remixes/hour",
            "Shield whitelisting (own tracks)",
            "Watermark-free exports",
            "Priority email support",
        ],
    },
    "business": {
        "name": "Remixa Business",
        "price_eur_monthly": 49.99,
        "stripe_price_id": os.getenv("STRIPE_BUSINESS_PRICE_ID", "price_biz_placeholder"),
        "features": [
            "100 generations/hour",
            "500 remixes/hour",
            "Shield whitelisting (any licensed track)",
            "Batch Shield CSV upload",
            "Programmatic API keys",
            "Priority GPU queue",
            "Dedicated account manager",
        ],
    },
}

# ============================================================================
# MODELS
# ============================================================================

class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "business"

class SubscriptionStatus(BaseModel):
    plan: str
    status: str  # "active", "past_due", "canceled", "free"
    current_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    features: list = []

# ============================================================================
# HELPERS
# ============================================================================

def get_db():
    """Database connection dependency"""
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()


def _ensure_stripe_customer(cur, conn, user_id: str, email: str) -> str:
    """Create or retrieve a Stripe customer for this user."""
    cur.execute(
        "SELECT stripe_customer_id FROM users WHERE id = %s", (user_id,)
    )
    row = cur.fetchone()
    if row and row["stripe_customer_id"]:
        return row["stripe_customer_id"]

    customer = stripe.Customer.create(
        email=email, metadata={"remixa_user_id": user_id}
    )
    cur.execute(
        "UPDATE users SET stripe_customer_id = %s WHERE id = %s",
        (customer.id, user_id),
    )
    conn.commit()
    return customer.id

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/checkout")
async def create_subscription_checkout(
    body: CheckoutRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Create a Stripe Checkout Session to upgrade the user to Pro or Business.
    Returns a redirect URL.
    """
    plan = body.plan.lower()
    if plan not in SUBSCRIPTION_PLANS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid plan '{plan}'. Must be 'pro' or 'business'.",
        )

    plan_config = SUBSCRIPTION_PLANS[plan]
    cur = db.cursor()
    try:
        customer_id = _ensure_stripe_customer(
            cur, db, current_user["id"], current_user.get("email", "")
        )

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan_config["stripe_price_id"],
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL', 'http://localhost:3000')}/dashboard?upgrade=success&plan={plan}",
            cancel_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL', 'http://localhost:3000')}/pricing?upgrade=cancelled",
            metadata={
                "remixa_user_id": current_user["id"],
                "plan": plan,
                "type": "subscription_upgrade",
            },
        )

        logger.info(
            "subscription_checkout_created",
            user_id=current_user["id"],
            plan=plan,
            session_id=session.id,
        )

        return {"session_id": session.id, "url": session.url, "plan": plan}
    finally:
        cur.close()


@router.post("/portal")
async def create_customer_portal(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Redirect the user to Stripe's Customer Portal to manage/cancel subscription.
    """
    cur = db.cursor()
    try:
        cur.execute(
            "SELECT stripe_customer_id FROM users WHERE id = %s",
            (current_user["id"],),
        )
        row = cur.fetchone()
        if not row or not row["stripe_customer_id"]:
            raise HTTPException(
                status_code=400,
                detail="No billing account found. You are on the free tier.",
            )

        portal_session = stripe.billing_portal.Session.create(
            customer=row["stripe_customer_id"],
            return_url=f"{os.getenv('NEXT_PUBLIC_SITE_URL', 'http://localhost:3000')}/settings/billing",
        )

        return {"url": portal_session.url}
    finally:
        cur.close()


@router.get("/status", response_model=SubscriptionStatus)
async def get_subscription_status(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Return the current user's subscription status and features.
    """
    cur = db.cursor()
    try:
        cur.execute(
            """
            SELECT subscription_tier, stripe_subscription_id, 
                   subscription_period_end, subscription_cancel_at_period_end
            FROM users WHERE id = %s
            """,
            (current_user["id"],),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        tier = row.get("subscription_tier") or "free"
        plan_config = SUBSCRIPTION_PLANS.get(tier, {})

        return SubscriptionStatus(
            plan=tier,
            status="active" if tier != "free" else "free",
            current_period_end=(
                row["subscription_period_end"].isoformat()
                if row.get("subscription_period_end")
                else None
            ),
            cancel_at_period_end=bool(row.get("subscription_cancel_at_period_end")),
            features=plan_config.get("features", []),
        )
    finally:
        cur.close()


@router.get("/plans")
async def list_plans():
    """
    Public endpoint — return available subscription plans and pricing.
    """
    plans = []
    for key, config in SUBSCRIPTION_PLANS.items():
        plans.append(
            {
                "id": key,
                "name": config["name"],
                "price_eur_monthly": config["price_eur_monthly"],
                "features": config["features"],
            }
        )
    return {"plans": plans}


# ============================================================================
# WEBHOOK — Subscription Lifecycle
# ============================================================================

async def handle_subscription_webhook(request: Request) -> Dict:
    """
    Handle Stripe webhook events for subscription lifecycle:
      - customer.subscription.created   → upgrade user tier
      - customer.subscription.updated   → sync period/cancel status
      - customer.subscription.deleted   → downgrade to free
      - invoice.payment_failed          → flag past_due
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_SUBSCRIPTION_WEBHOOK_SECRET")
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    conn = psycopg2.connect(os.getenv("DATABASE_URL"), cursor_factory=RealDictCursor)
    cur = conn.cursor()

    try:
        event_type = event["type"]
        obj = event["data"]["object"]

        if event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
        ):
            customer_id = obj["customer"]
            subscription_id = obj["id"]
            status = obj["status"]  # active, past_due, canceled, etc.

            # Determine plan from metadata or price lookup
            plan = "free"
            if obj.get("metadata", {}).get("plan"):
                plan = obj["metadata"]["plan"]
            else:
                # Resolve from price ID
                items = obj.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id", "")
                    for tier_key, tier_config in SUBSCRIPTION_PLANS.items():
                        if tier_config["stripe_price_id"] == price_id:
                            plan = tier_key
                            break

            # Only set tier to paid if subscription is active
            effective_tier = plan if status == "active" else "free"

            period_end = datetime.utcfromtimestamp(
                obj.get("current_period_end", 0)
            )
            cancel_at_period_end = obj.get("cancel_at_period_end", False)

            cur.execute(
                """
                UPDATE users 
                SET subscription_tier = %s,
                    stripe_subscription_id = %s,
                    subscription_period_end = %s,
                    subscription_cancel_at_period_end = %s
                WHERE stripe_customer_id = %s
                """,
                (
                    effective_tier,
                    subscription_id,
                    period_end,
                    cancel_at_period_end,
                    customer_id,
                ),
            )
            conn.commit()
            logger.info(
                "subscription_synced",
                customer_id=customer_id,
                plan=plan,
                status=status,
                effective_tier=effective_tier,
            )

        elif event_type == "customer.subscription.deleted":
            customer_id = obj["customer"]
            cur.execute(
                """
                UPDATE users 
                SET subscription_tier = 'free',
                    stripe_subscription_id = NULL,
                    subscription_period_end = NULL,
                    subscription_cancel_at_period_end = FALSE
                WHERE stripe_customer_id = %s
                """,
                (customer_id,),
            )
            conn.commit()
            logger.info("subscription_canceled", customer_id=customer_id)

        elif event_type == "invoice.payment_failed":
            customer_id = obj["customer"]
            cur.execute(
                "UPDATE users SET subscription_tier = 'free' WHERE stripe_customer_id = %s",
                (customer_id,),
            )
            conn.commit()
            logger.warning("subscription_payment_failed", customer_id=customer_id)

        return {"status": "ok", "event_type": event_type}

    finally:
        cur.close()
        conn.close()


@router.post("/webhook")
async def subscription_webhook(request: Request):
    """Stripe subscription webhook handler"""
    return await handle_subscription_webhook(request)
