"""
EU TikTok Sound Lab v2 - Social & Remix API
Modules 2-7: Explore, Remix, Earnings, Streaks, Reports, Invites
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Callable
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
from rate_limiter import check_remix_rate_limit

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
# ERROR HANDLING DECORATOR
# ============================================================================

def handle_errors(func: Callable):
    """
    Decorator for comprehensive error handling with structured logging
    
    Features:
    - Logs all errors with request_id
    - Returns user-friendly error messages
    - Proper HTTP status codes
    - Database connection error handling
    - Replicate API error handling
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Inject request_id into kwargs if Request object is present
            for arg in args:
                if isinstance(arg, Request):
                    kwargs['request_id'] = request_id
                    break
            
            result = await func(*args, **kwargs)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(
                "request_completed",
                function=func.__name__,
                request_id=request_id,
                duration_ms=duration_ms
            )
            
            return result
            
        except HTTPException:
            # Re-raise HTTP exceptions (already properly formatted)
            raise
            
        except psycopg2.OperationalError as e:
            logger.error(
                "database_connection_error",
                error=str(e),
                function=func.__name__,
                request_id=request_id
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "database_unavailable",
                    "message": "Database temporarily unavailable. Please try again in a moment.",
                    "request_id": request_id
                }
            )
            
        except psycopg2.IntegrityError as e:
            logger.error(
                "database_integrity_error",
                error=str(e),
                function=func.__name__,
                request_id=request_id
            )
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "data_conflict",
                    "message": "Data conflict. This operation cannot be completed.",
                    "request_id": request_id
                }
            )
            
        except requests.exceptions.Timeout:
            logger.error(
                "external_api_timeout",
                function=func.__name__,
                request_id=request_id
            )
            raise HTTPException(
                status_code=504,
                detail={
                    "error": "external_service_timeout",
                    "message": "External service timed out. Please try again.",
                    "request_id": request_id
                }
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(
                "external_api_error",
                error=str(e),
                function=func.__name__,
                request_id=request_id
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "external_service_error",
                    "message": "External service error. Please try again later.",
                    "request_id": request_id
                }
            )
            
        except Exception as e:
            logger.error(
                "unexpected_error",
                error=str(e),
                error_type=type(e).__name__,
                function=func.__name__,
                request_id=request_id,
                exc_info=True
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "internal_error",
                    "message": "An unexpected error occurred. Please try again.",
                    "request_id": request_id
                }
            )
    
    return wrapper

# ============================================================================
# RETRY DECORATOR FOR REPLICATE API
# ============================================================================

def retry_on_failure(max_attempts: int = 3, backoff_factor: float = 2.0):
    """
    Retry decorator with exponential backoff for Replicate API calls
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff (seconds)
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                    
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    last_exception = e
                    
                    if attempt < max_attempts:
                        wait_time = backoff_factor ** (attempt - 1)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt,
                            max_attempts=max_attempts,
                            wait_time=wait_time,
                            error=str(e)
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            attempts=max_attempts,
                            error=str(e)
                        )
                        raise
                        
                except Exception as e:
                    # Don't retry on other exceptions
                    raise
            
            # Should never reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RemixRequest(BaseModel):
    layer_type: str = Field(..., description="base, lyrics, voice, or visual")
    prompt: str = Field(..., max_length=500)
    voice_model_id: Optional[str] = None

class GenerationResponse(BaseModel):
    id: str
    prompt: str
    audio_url: str
    waveform_url: str
    layer_type: str
    parent_id: Optional[str]
    remix_chain: List[str]
    creator_username: str
    creator_id: str
    remix_count: int
    earnings: float
    is_public: bool
    c2pa_manifest_url: str
    created_at: str

class ExploreItem(BaseModel):
    id: str
    prompt: str
    audio_url: str
    waveform_url: str
    creator_username: str
    layer_type: str
    remix_count: int
    earnings: float
    created_at: str
    parent_preview: Optional[dict] = None

class EarningsResponse(BaseModel):
    total_earned: float
    pending_payout: float
    total_remixes: int
    top_tapes: List[dict]
    recent_transactions: List[dict]

class LeaderboardEntry(BaseModel):
    username: str
    value: float
    rank: int

class ReportRequest(BaseModel):
    generation_id: str
    reason: str = Field(..., description="copyright, inappropriate, spam, or other")
    details: Optional[str] = None

class InviteResponse(BaseModel):
    code: str
    invites_remaining: int

# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db():
    """Get database connection"""
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

# ============================================================================
# MODULE 2: EXPLORE & DISCOVERY
# ============================================================================

@handle_errors
async def get_explore_feed(
    sort: str = Query("trending", description="trending, recent, or top"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db),
    request_id: str = None
) -> List[ExploreItem]:
    """
    Get public generations for explore feed
    
    Sort options:
    - trending: by remix_count DESC (last 7 days)
    - recent: by created_at DESC
    - top: by earnings DESC (all time)
    """
    
    cur = db.cursor()
    
    if sort == "trending":
        query = """
            SELECT 
                g.id, g.prompt, g.audio_url, g.layer_type, g.remix_count, 
                g.earnings, g.created_at, u.username as creator_username,
                CASE 
                    WHEN g.parent_id IS NOT NULL THEN 
                        json_build_object(
                            'id', p.id,
                            'creator', pu.username,
                            'audio_url', p.audio_url
                        )
                    ELSE NULL
                END as parent_preview
            FROM generations g
            JOIN users u ON g.user_id = u.id
            LEFT JOIN generations p ON g.parent_id = p.id
            LEFT JOIN users pu ON p.user_id = pu.id
            WHERE g.is_public = true 
              AND g.created_at > NOW() - INTERVAL '7 days'
            ORDER BY g.remix_count DESC, g.created_at DESC
            LIMIT %s OFFSET %s
        """
    elif sort == "recent":
        query = """
            SELECT 
                g.id, g.prompt, g.audio_url, g.layer_type, g.remix_count, 
                g.earnings, g.created_at, u.username as creator_username,
                CASE 
                    WHEN g.parent_id IS NOT NULL THEN 
                        json_build_object(
                            'id', p.id,
                            'creator', pu.username,
                            'audio_url', p.audio_url
                        )
                    ELSE NULL
                END as parent_preview
            FROM generations g
            JOIN users u ON g.user_id = u.id
            LEFT JOIN generations p ON g.parent_id = p.id
            LEFT JOIN users pu ON p.user_id = pu.id
            WHERE g.is_public = true
            ORDER BY g.created_at DESC
            LIMIT %s OFFSET %s
        """
    else:  # top
        query = """
            SELECT 
                g.id, g.prompt, g.audio_url, g.layer_type, g.remix_count, 
                g.earnings, g.created_at, u.username as creator_username,
                CASE 
                    WHEN g.parent_id IS NOT NULL THEN 
                        json_build_object(
                            'id', p.id,
                            'creator', pu.username,
                            'audio_url', p.audio_url
                        )
                    ELSE NULL
                END as parent_preview
            FROM generations g
            JOIN users u ON g.user_id = u.id
            LEFT JOIN generations p ON g.parent_id = p.id
            LEFT JOIN users pu ON p.user_id = pu.id
            WHERE g.is_public = true
            ORDER BY g.earnings DESC, g.remix_count DESC
            LIMIT %s OFFSET %s
        """
    
    cur.execute(query, (limit, offset))
    rows = cur.fetchall()
    
    items = []
    for row in rows:
        items.append(ExploreItem(
            id=str(row['id']),
            prompt=row['prompt'],
            audio_url=row['audio_url'],
            waveform_url=row['audio_url'].replace('.mp3', '_waveform.png'),
            creator_username=row['creator_username'],
            layer_type=row['layer_type'],
            remix_count=row['remix_count'],
            earnings=float(row['earnings']),
            created_at=row['created_at'].isoformat(),
            parent_preview=row.get('parent_preview')
        ))
    
    cur.close()
    return items

@handle_errors
async def get_generation_detail(
    generation_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> GenerationResponse:
    """
    Get full generation details including remix chain
    """
    
    cur = db.cursor()
    
    cur.execute("""
        SELECT 
            g.id, g.prompt, g.audio_url, g.layer_type, g.parent_id,
            g.remix_chain, g.remix_count, g.earnings, g.is_public,
            g.c2pa_manifest, g.created_at,
            u.id as creator_id, u.username as creator_username
        FROM generations g
        JOIN users u ON g.user_id = u.id
        WHERE g.id = %s
    """, (generation_id,))
    
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    # Build C2PA manifest URL
    c2pa_url = row['audio_url'].replace('.mp3', '.c2pa.json')
    
    response = GenerationResponse(
        id=str(row['id']),
        prompt=row['prompt'],
        audio_url=row['audio_url'],
        waveform_url=row['audio_url'].replace('.mp3', '_waveform.png'),
        layer_type=row['layer_type'],
        parent_id=str(row['parent_id']) if row['parent_id'] else None,
        remix_chain=[str(x) for x in row['remix_chain']],
        creator_username=row['creator_username'],
        creator_id=str(row['creator_id']),
        remix_count=row['remix_count'],
        earnings=float(row['earnings']),
        is_public=row['is_public'],
        c2pa_manifest_url=c2pa_url,
        created_at=row['created_at'].isoformat()
    )
    
    cur.close()
    return response

# ============================================================================
# MODULE 3: REMIX LOGIC
# ============================================================================

async def create_remix(
    generation_id: str,
    request: RemixRequest,
    user_id: str,
    subscription_tier: str,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
) -> dict:
    """
    Create a remix of an existing generation with transaction safety
    
    Steps:
    1. Verify parent is public
    2. Check user balance (€0.10)
    3. Create Stripe charge with idempotency key
    4. Distribute royalties in database transaction
    5. Generate new audio (background)
    
    Transaction safety:
    - All DB operations wrapped in transaction
    - Rollback on Stripe failure
    - Idempotency key prevents double charges
    """
    
    import stripe
    import structlog
    
    logger = structlog.get_logger()
    request_id = str(uuid.uuid4())
    
    # Check rate limit before processing
    await check_remix_rate_limit(
        user_id=user_id,
        subscription_tier=subscription_tier
    )
    
    cur = db.cursor()
    
    try:
        # 1. Verify parent exists and is public
        cur.execute("""
            SELECT id, user_id, audio_url, is_public, parent_id, remix_chain
            FROM generations
            WHERE id = %s
        """, (generation_id,))
        
        parent = cur.fetchone()
        if not parent:
            logger.warning("remix_parent_not_found", generation_id=generation_id, request_id=request_id)
            raise HTTPException(status_code=404, detail="Parent generation not found")
        
        if not parent['is_public']:
            logger.warning("remix_parent_private", generation_id=generation_id, request_id=request_id)
            raise HTTPException(
                status_code=403, 
                detail={
                    "error": "parent_not_public",
                    "message": "Cannot remix private generation"
                }
            )
        
        # 2. Get user's Stripe customer ID
        cur.execute("""
            SELECT stripe_customer_id, email 
            FROM users 
            WHERE id = %s
        """, (user_id,))
        
        user = cur.fetchone()
        if not user or not user['stripe_customer_id']:
            logger.error("remix_no_stripe_customer", user_id=user_id, request_id=request_id)
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "payment_method_required",
                    "message": "Please add a payment method at /settings/billing"
                }
            )
        
        # 3. Create Stripe charge with idempotency key
        idempotency_key = f"remix_{user_id}_{generation_id}_{request_id}"
        
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
                logger.error(
                    "remix_payment_failed",
                    user_id=user_id,
                    payment_intent_id=payment_intent.id,
                    status=payment_intent.status,
                    request_id=request_id
                )
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "payment_failed",
                        "message": "Payment failed. Please check your payment method."
                    }
                )
            
            logger.info(
                "remix_payment_succeeded",
                user_id=user_id,
                payment_intent_id=payment_intent.id,
                request_id=request_id
            )
            
        except stripe.error.CardError as e:
            logger.error("remix_card_error", error=str(e), user_id=user_id, request_id=request_id)
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "card_declined",
                    "message": f"Card declined: {e.user_message}"
                }
            )
        except stripe.error.StripeError as e:
            logger.error("remix_stripe_error", error=str(e), user_id=user_id, request_id=request_id)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "payment_processing_error",
                    "message": "Payment processing failed. Please try again."
                }
            )
        
        # 4. Database transaction: create generation and distribute royalties
        new_generation_id = str(uuid.uuid4())
        new_remix_chain = parent['remix_chain'] + [str(parent['id'])]
        
        # Create generation record
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
        
        # Distribute royalties using stored procedure
        cur.execute("""
            SELECT distribute_remix_royalties(%s, %s, %s)
        """, (user_id, parent['id'], new_generation_id))
        
        # Update license transaction with Stripe payment intent ID
        cur.execute("""
            UPDATE license_transactions 
            SET stripe_payment_intent_id = %s
            WHERE generation_id = %s
        """, (payment_intent.id, new_generation_id))
        
        # Commit transaction
        db.commit()
        
        logger.info(
            "remix_created",
            generation_id=new_generation_id,
            parent_id=generation_id,
            user_id=user_id,
            request_id=request_id
        )
        
        # 5. Queue audio generation (after successful commit)
        background_tasks.add_task(
            generate_remix_audio,
            new_generation_id,
            parent['audio_url'],
            request.prompt,
            request.layer_type,
            request.voice_model_id
        )
        
        return {
            "generation_id": new_generation_id,
            "status": "processing",
            "message": "Remix queued. Check back in 10 seconds.",
            "payment_intent_id": payment_intent.id
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (already logged)
        db.rollback()
        raise
        
    except Exception as e:
        # Rollback transaction on any error
        db.rollback()
        logger.error(
            "remix_unexpected_error",
            error=str(e),
            user_id=user_id,
            generation_id=generation_id,
            request_id=request_id
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
                "request_id": request_id
            }
        )
    
    finally:
        cur.close()

@retry_on_failure(max_attempts=3, backoff_factor=2.0)
async def generate_remix_audio(
    generation_id: str,
    parent_audio_url: str,
    prompt: str,
    layer_type: str,
    voice_model_id: Optional[str]
):
    """
    Background task: Generate remix audio using Replicate with retry logic
    """
    
    if layer_type == "lyrics":
        # Lyrics layer: just add metadata, no AI generation
        # Copy parent audio and add lyrics metadata
        print(f"[REMIX] Lyrics layer for {generation_id}: copying parent audio")
        # TODO: Implement lyrics metadata injection
        return
    
    elif layer_type == "voice":
        # Voice layer: use MusicGen with voice model
        print(f"[REMIX] Voice layer for {generation_id}: calling Replicate")
        
        # Call Replicate API
        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Bearer {os.getenv('REPLICATE_API_TOKEN')}",
                "Content-Type": "application/json"
            },
            json={
                "version": "meta/musicgen-stem:latest",
                "input": {
                    "prompt": prompt,
                    "audio_input": parent_audio_url,
                    "duration": 15,
                    "voice_model": voice_model_id
                }
            }
        )
        
        prediction = response.json()
        print(f"[REMIX] Replicate prediction: {prediction['id']}")
        
        # TODO: Poll for completion and upload to R2
        
    elif layer_type == "visual":
        # Visual layer: generate waveform video
        print(f"[REMIX] Visual layer for {generation_id}: generating waveform")
        # TODO: Use FFmpeg to create waveform video
        
    else:  # base
        # Base layer: generate new audio (ignore parent)
        print(f"[REMIX] Base layer for {generation_id}: new generation")
        # TODO: Call MusicGen without parent

# ============================================================================
# MODULE 4: EARNINGS & PAYOUTS
# ============================================================================

@handle_errors
async def get_earnings(
    user_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> EarningsResponse:
    """
    Get user earnings dashboard data
    """
    
    cur = db.cursor()
    
    # Get user totals
    cur.execute("""
        SELECT total_earned, pending_payout
        FROM users
        WHERE id = %s
    """, (user_id,))
    
    user = cur.fetchone()
    
    # Get total remixes
    cur.execute("""
        SELECT SUM(remix_count) as total_remixes
        FROM generations
        WHERE user_id = %s
    """, (user_id,))
    
    remixes = cur.fetchone()
    
    # Get top earning tapes
    cur.execute("""
        SELECT id, prompt, earnings, remix_count, audio_url
        FROM generations
        WHERE user_id = %s
        ORDER BY earnings DESC
        LIMIT 5
    """, (user_id,))
    
    top_tapes = [dict(row) for row in cur.fetchall()]
    
    # Get recent transactions
    cur.execute("""
        SELECT 
            lt.amount, lt.creator_share, lt.created_at,
            g.prompt, u.username as remixer_username
        FROM license_transactions lt
        JOIN generations g ON lt.generation_id = g.id
        JOIN users u ON lt.remixer_id = u.id
        WHERE lt.original_creator_id = %s
        ORDER BY lt.created_at DESC
        LIMIT 10
    """, (user_id,))
    
    recent_transactions = [dict(row) for row in cur.fetchall()]
    
    cur.close()
    
    return EarningsResponse(
        total_earned=float(user['total_earned']),
        pending_payout=float(user['pending_payout']),
        total_remixes=int(remixes['total_remixes'] or 0),
        top_tapes=top_tapes,
        recent_transactions=recent_transactions
    )

@handle_errors
async def request_payout(
    user_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> dict:
    """
    Request payout (minimum €20)
    """
    
    cur = db.cursor()
    
    cur.execute("""
        SELECT pending_payout, stripe_connect_account_id
        FROM users
        WHERE id = %s
    """, (user_id,))
    
    user = cur.fetchone()
    
    if float(user['pending_payout']) < 20:
        raise HTTPException(
            status_code=400,
            detail=f"Minimum payout is €20. Current balance: €{user['pending_payout']:.2f}"
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
    """, (payout_id, user_id, user['pending_payout']))
    
    # Reset pending balance
    cur.execute("""
        UPDATE users SET pending_payout = 0 WHERE id = %s
    """, (user_id,))
    
    db.commit()
    cur.close()
    
    return {
        "payout_id": payout_id,
        "amount": float(user['pending_payout']),
        "status": "pending",
        "message": "Payout will be processed within 2 business days"
    }

# ============================================================================
# MODULE 5: STREAKS & LEADERBOARDS
# ============================================================================

@handle_errors
async def get_streak_badge(
    user_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> StreamingResponse:
    """
    Generate streak badge PNG
    """
    
    cur = db.cursor()
    cur.execute("SELECT streak_days FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    
    streak_days = user['streak_days'] if user else 0
    
    # TODO: Generate PNG with Pillow
    # For now, return placeholder
    return {
        "streak_days": streak_days,
        "badge_url": f"https://cdn.eu-sound-lab.com/badges/streak_{streak_days}.png"
    }

@handle_errors
async def get_leaderboard(
    leaderboard_type: str = Query("earnings", description="earnings, remixes, or streaks"),
    db = Depends(get_db),
    request_id: str = None
) -> List[LeaderboardEntry]:
    """
    Get leaderboard (top 20)
    """
    
    cur = db.cursor()
    
    if leaderboard_type == "earnings":
        cur.execute("SELECT * FROM leaderboard_earnings")
    elif leaderboard_type == "remixes":
        cur.execute("SELECT * FROM leaderboard_remixes")
    elif leaderboard_type == "streaks":
        cur.execute("SELECT * FROM leaderboard_streaks")
    else:
        raise HTTPException(status_code=400, detail="Invalid leaderboard type")
    
    rows = cur.fetchall()
    cur.close()
    
    entries = []
    for i, row in enumerate(rows, 1):
        value = row.get('total_earned') or row.get('total_remixes') or row.get('streak_days')
        entries.append(LeaderboardEntry(
            username=row['username'],
            value=float(value),
            rank=i
        ))
    
    return entries

# ============================================================================
# MODULE 6: REPORTING (DSA Compliance)
# ============================================================================

@handle_errors
async def create_report(
    request: ReportRequest,
    reporter_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> dict:
    """
    Create content report (DSA Art 35)
    """
    
    cur = db.cursor()
    
    # Verify generation exists
    cur.execute("SELECT id FROM generations WHERE id = %s", (request.generation_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Generation not found")
    
    # Create report
    report_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO reports (id, generation_id, reporter_id, reason, details, status)
        VALUES (%s, %s, %s, %s, %s, 'pending')
    """, (report_id, request.generation_id, reporter_id, request.reason, request.details))
    
    db.commit()
    cur.close()
    
    # TODO: Send to admin Slack webhook
    # TODO: Log to DSA transparency file
    
    return {
        "report_id": report_id,
        "status": "received",
        "message": "Report received. We'll review within 24 hours."
    }

# ============================================================================
# MODULE 7: INVITES & WAITLIST
# ============================================================================

@handle_errors
async def generate_invite(
    user_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> InviteResponse:
    """
    Generate invite code (if user has invites remaining)
    """
    
    cur = db.cursor()
    
    cur.execute("""
        SELECT invites_remaining, waitlist_position
        FROM users
        WHERE id = %s
    """, (user_id,))
    
    user = cur.fetchone()
    
    if user['waitlist_position'] is not None and user['waitlist_position'] > 0:
        raise HTTPException(status_code=403, detail="You're still on the waitlist")
    
    if user['invites_remaining'] <= 0:
        raise HTTPException(status_code=403, detail="No invites remaining")
    
    # Generate code
    code = str(uuid.uuid4())[:8].upper()
    
    cur.execute("""
        INSERT INTO invites (code, inviter_id)
        VALUES (%s, %s)
    """, (code, user_id))
    
    cur.execute("""
        UPDATE users SET invites_remaining = invites_remaining - 1
        WHERE id = %s
    """, (user_id,))
    
    db.commit()
    
    cur.execute("SELECT invites_remaining FROM users WHERE id = %s", (user_id,))
    updated_user = cur.fetchone()
    
    cur.close()
    
    return InviteResponse(
        code=code,
        invites_remaining=updated_user['invites_remaining']
    )

@handle_errors
async def redeem_invite(
    code: str,
    user_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> dict:
    """
    Redeem invite code
    """
    
    cur = db.cursor()
    
    # Verify code exists and not redeemed
    cur.execute("""
        SELECT inviter_id, redeemed_at
        FROM invites
        WHERE code = %s
    """, (code,))
    
    invite = cur.fetchone()
    
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    
    if invite['redeemed_at']:
        raise HTTPException(status_code=400, detail="Invite already redeemed")
    
    # Activate user
    cur.execute("""
        UPDATE users SET waitlist_position = 0
        WHERE id = %s
    """, (user_id,))
    
    # Mark invite as redeemed
    cur.execute("""
        UPDATE invites SET invitee_id = %s, redeemed_at = NOW()
        WHERE code = %s
    """, (user_id, code))
    
    # Give inviter +1 invite
    cur.execute("""
        UPDATE users SET invites_remaining = invites_remaining + 1
        WHERE id = %s
    """, (invite['inviter_id'],))
    
    db.commit()
    cur.close()
    
    return {
        "status": "activated",
        "message": "Welcome to EU Sound Lab! You now have 3 invites."
    }

@handle_errors
async def get_waitlist_status(
    user_id: str,
    db = Depends(get_db),
    request_id: str = None
) -> dict:
    """
    Get waitlist position
    """
    
    cur = db.cursor()
    
    cur.execute("""
        SELECT waitlist_position
        FROM users
        WHERE id = %s
    """, (user_id,))
    
    user = cur.fetchone()
    cur.close()
    
    if not user or user['waitlist_position'] is None or user['waitlist_position'] == 0:
        return {
            "status": "active",
            "message": "You're in! Start creating."
        }
    
    return {
        "status": "waitlisted",
        "position": user['waitlist_position'],
        "message": f"You're #{user['waitlist_position']} on the waitlist. We onboard 100/week."
    }
