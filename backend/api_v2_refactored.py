"""
EU TikTok Sound Lab v2 - Social & Remix API (REFACTORED)
Security-hardened version with proper authentication

CHANGES FROM ORIGINAL:
1. Added APIRouter with prefix /api/v2
2. All handlers use Depends(get_current_user) for identity
3. Added route decorators (@router.get, @router.post)
4. Removed plain identity parameters (user_id: str, etc.)
5. Added response models for type safety
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
from datetime import datetime, date
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import requests
import json
import structlog
from functools import wraps
import time

from clerk_auth import get_current_user
from rate_limiter import check_remix_rate_limit

# ============================================================================
# ROUTER SETUP
# ============================================================================

router = APIRouter(prefix="/api/v2", tags=["v2"])

# ============================================================================
# LOGGING SETUP
# ============================================================================

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================

def get_db():
    """Database connection dependency"""
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RemixRequest(BaseModel):
    prompt: str = Field(..., max_length=500)
    layer_type: str = Field("full", description="full, drums, bass, melody, vocals")

class PayoutResponse(BaseModel):
    payout_id: str
    amount: float
    status: str
    message: str

class EarningsResponse(BaseModel):
    total_earned: float
    available_balance: float
    pending_payouts: float
    lifetime_earnings: float

class RemixResponse(BaseModel):
    generation_id: str
    status: str
    audio_url: Optional[str]
    parent_id: str
    cost_eur: float

# ============================================================================
# MONEY ENDPOINTS (CRITICAL - REFACTORED)
# ============================================================================

@router.post("/payout", response_model=PayoutResponse)
async def request_payout(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Request payout (minimum €20)
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
    logger.info("payout_requested", user_id=user_id, request_id=request_id)
    
    cur = db.cursor()
    
    # Withdrawable balance = net of the append-only ledger
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS available
        FROM user_ledger
        WHERE user_id = %s
    """, (user_id,))
    available = float(cur.fetchone()['available'])

    cur.execute("""
        SELECT stripe_connect_account_id
        FROM users
        WHERE id = %s
    """, (user_id,))
    user = cur.fetchone()

    if available < 20:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum payout is €20. Current balance: €{available:.2f}"
        )

    if not user['stripe_connect_account_id']:
        raise HTTPException(
            status_code=400,
            detail="Please connect your Stripe account first at /settings/payouts"
        )

    # Create payout request
    payout_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO payout_requests (id, user_id, amount, status)
        VALUES (%s, %s, %s, 'pending')
    """, (payout_id, user_id, available))

    # Debit the ledger (append-only)
    cur.execute("""
        INSERT INTO user_ledger (user_id, transaction_type, amount, payout_request_id, description)
        VALUES (%s, 'payout_requested', %s, %s, 'Payout requested')
    """, (user_id, -available, payout_id))

    db.commit()
    
    logger.info(
        "payout_created",
        user_id=user_id,
        payout_id=payout_id,
        amount=available,
        request_id=request_id
    )

    return {
        "payout_id": payout_id,
        "amount": available,
        "status": "pending",
        "message": f"Payout of €{available:.2f} requested. Processing within 2-3 business days."
    }


@router.get("/earnings", response_model=EarningsResponse)
async def get_earnings(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Get user earnings breakdown
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    
    cur = db.cursor()
    
    # Available balance (net of ledger)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS available
        FROM user_ledger
        WHERE user_id = %s
    """, (user_id,))
    available = float(cur.fetchone()['available'])
    
    # Pending payouts
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS pending
        FROM payout_requests
        WHERE user_id = %s AND status = 'pending'
    """, (user_id,))
    pending = float(cur.fetchone()['pending'])
    
    # Lifetime earnings (all credits)
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) AS lifetime
        FROM user_ledger
        WHERE user_id = %s AND amount > 0
    """, (user_id,))
    lifetime = float(cur.fetchone()['lifetime'])
    
    return {
        "total_earned": lifetime,
        "available_balance": available,
        "pending_payouts": pending,
        "lifetime_earnings": lifetime
    }


@router.post("/generations/{generation_id}/remix", response_model=RemixResponse)
async def create_remix(
    generation_id: str,
    request: RemixRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Create a remix of an existing generation
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    subscription_tier = current_user["subscription_tier"]
    request_id = str(uuid.uuid4())
    
    logger.info(
        "remix_requested",
        user_id=user_id,
        parent_id=generation_id,
        request_id=request_id
    )
    
    # Check rate limit
    await check_remix_rate_limit(
        user_id=user_id,
        subscription_tier=subscription_tier
    )
    
    cur = db.cursor()
    
    # 1. Verify parent exists and is public
    cur.execute("""
        SELECT id, user_id, audio_url, is_public, parent_id, remix_chain
        FROM generations
        WHERE id = %s
    """, (generation_id,))
    
    parent = cur.fetchone()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent generation not found")
    
    if not parent['is_public']:
        raise HTTPException(
            status_code=403,
            detail="Cannot remix private generation"
        )
    
    # 2. Get user's Stripe customer ID
    cur.execute("""
        SELECT stripe_customer_id, email 
        FROM users 
        WHERE id = %s
    """, (user_id,))
    
    user = cur.fetchone()
    if not user or not user['stripe_customer_id']:
        raise HTTPException(
            status_code=400,
            detail="Please add a payment method at /settings/billing"
        )
    
    # 3. Create Stripe charge with STABLE idempotency key
    import stripe
    
    idempotency_key = f"remix_{user_id}_{generation_id}"
    
    try:
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
        
        payment_intent = stripe.PaymentIntent.create(
            amount=10,  # €0.10 in cents
            currency="eur",
            customer=user['stripe_customer_id'],
            description=f"Remix license for generation {generation_id}",
            metadata={
                "user_id": user_id,
                "parent_generation_id": generation_id,
                "request_id": request_id
            },
            idempotency_key=idempotency_key,
            confirm=True,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"}
        )
        
        if payment_intent.status != "succeeded":
            raise HTTPException(
                status_code=402,
                detail="Payment failed. Please check your payment method."
            )
        
        logger.info(
            "remix_payment_succeeded",
            user_id=user_id,
            payment_intent_id=payment_intent.id,
            request_id=request_id
        )
        
    except stripe.error.CardError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Card declined: {e.user_message}"
        )
    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=500,
            detail="Payment processing failed. Please try again."
        )
    
    # 4. Create generation and distribute royalties
    new_generation_id = str(uuid.uuid4())
    new_remix_chain = parent['remix_chain'] + [str(parent['id'])]
    
    cur.execute("""
        INSERT INTO generations (
            id, user_id, prompt, layer_type, parent_id, remix_chain,
            is_public, audio_url, c2pa_manifest_url, generation_time_ms,
            cost_eur, model_version, training_data_hash
        ) VALUES (
            %s, %s, %s, %s, %s, %s, true, %s, %s, 0, 0.008, 'eu-sound-lab-v2', 'pending'
        )
    """, (
        new_generation_id,
        user_id,
        request.prompt,
        request.layer_type,
        parent['id'],
        new_remix_chain,
        f"https://cdn.eu-sound-lab.com/audio/{new_generation_id}.mp3",
        f"https://cdn.eu-sound-lab.com/audio/{new_generation_id}.c2pa.json"
    ))
    
    # Distribute royalties using the stored procedure
    cur.execute("""
        SELECT distribute_remix_royalties_v2(%s, %s, %s)
    """, (user_id, new_generation_id, parent['id']))
    
    db.commit()
    
    # 5. Generate audio in background
    # background_tasks.add_task(generate_remix_audio, new_generation_id, parent['audio_url'], request.prompt)
    
    logger.info(
        "remix_created",
        user_id=user_id,
        generation_id=new_generation_id,
        parent_id=generation_id,
        request_id=request_id
    )
    
    return {
        "generation_id": new_generation_id,
        "status": "processing",
        "audio_url": None,  # Will be updated when generation completes
        "parent_id": generation_id,
        "cost_eur": 0.10
    }

# ============================================================================
# TODO: Add remaining endpoints (explore, leaderboard, streak, etc.)
# These need similar refactoring but are lower priority (no money risk)
# ============================================================================
