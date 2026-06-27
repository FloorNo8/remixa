"""
EU TikTok Sound Lab v2 - Social & Remix API
Modules 2-7: Explore, Remix, Earnings, Streaks, Reports, Invites
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Callable, Dict
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
from clerk_auth import get_current_user
from rbac import require_role, Role

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
            if last_exception is not None:
                raise last_exception
            raise RuntimeError("Retry loop exited without exception")
        
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
    raw_lufs: Optional[float] = None
    mastered_lufs: Optional[float] = None
    raw_peak: Optional[float] = None
    mastered_peak: Optional[float] = None

class StemInfo(BaseModel):
    layer_type: str
    audio_url: str
    generation_id: str

class GameDevStemsResponse(BaseModel):
    generation_id: str
    style: str
    base_track_url: str
    stems: List[StemInfo]
    dsp_parameters: Dict[str, float]

class BranchInfoResponse(BaseModel):
    generation_id: str
    parent_id: Optional[str]
    grandparent_id: Optional[str]
    active_branches_count: int
    total_derivative_views: int
    royalties_split: Dict[str, float]
    lineage_chain: List[str]

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
    pending_balance: float
    total_remixes: int
    top_tapes: List[dict]
    recent_transactions: List[dict]
    stripe_connected: bool
    can_withdraw: bool
    this_month_earnings: float
    chart_data: List[dict]

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

@router.get("/explore")
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
            creator_username=row['creator_username'] or "anonymous",
            layer_type=row['layer_type'],
            remix_count=row['remix_count'],
            earnings=float(row['earnings']),
            created_at=row['created_at'].isoformat(),
            parent_preview=row.get('parent_preview')
        ))
    
    cur.close()
    return items

@router.get("/generations/{generation_id}")
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
            g.raw_lufs, g.mastered_lufs, g.raw_peak, g.mastered_peak,
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
        creator_username=row['creator_username'] or "anonymous",
        creator_id=str(row['creator_id']),
        remix_count=row['remix_count'],
        earnings=float(row['earnings']),
        is_public=row['is_public'],
        c2pa_manifest_url=c2pa_url,
        created_at=row['created_at'].isoformat(),
        raw_lufs=row['raw_lufs'],
        mastered_lufs=row['mastered_lufs'],
        raw_peak=row['raw_peak'],
        mastered_peak=row['mastered_peak']
    )
    
    cur.close()
    return response


@router.get("/generations/{generation_id}/stems", response_model=GameDevStemsResponse)
@handle_errors
async def get_generation_stems(
    generation_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
    request_id: str = None
) -> GameDevStemsResponse:
    """
    Get dynamic stems and audio parameters for game developers.
    """
    cur = db.cursor()
    
    # 1. Fetch generation details
    cur.execute("""
        SELECT id, audio_url, style, parent_id, layer_type
        FROM generations
        WHERE id = %s
    """, (generation_id,))
    
    gen = cur.fetchone()
    if not gen:
        cur.close()
        raise HTTPException(status_code=404, detail="Generation not found")
        
    # 2. Fetch all child generations (these act as stems like lyrics/voice/visuals overlays)
    cur.execute("""
        SELECT id, audio_url, layer_type
        FROM generations
        WHERE parent_id = %s
    """, (generation_id,))
    
    stems_rows = cur.fetchall()
    stems = []
    for r in stems_rows:
        stems.append(StemInfo(
            layer_type=r["layer_type"],
            audio_url=r["audio_url"],
            generation_id=str(r["id"])
        ))
        
    # If no child stems exist in DB, mock some stems based on the base track
    if not stems:
        stems.append(StemInfo(
            layer_type="drums",
            audio_url=gen["audio_url"].replace(".mp3", "_drums.mp3"),
            generation_id=generation_id
        ))
        stems.append(StemInfo(
            layer_type="voice",
            audio_url=gen["audio_url"].replace(".mp3", "_vocals.mp3"),
            generation_id=generation_id
        ))
        stems.append(StemInfo(
            layer_type="bass",
            audio_url=gen["audio_url"].replace(".mp3", "_bass.mp3"),
            generation_id=generation_id
        ))
        
    # 3. Fetch production team parameters for style
    cur.execute("""
        SELECT drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db
        FROM production_team_parameters
        WHERE style = %s
        ORDER BY updated_at DESC
        LIMIT 1
    """, (gen["style"],))
    
    params_row = cur.fetchone()
    
    if not params_row:
        # Fall back to mastering_parameters
        cur.execute("""
            SELECT drive_db, high_shelf_db, stereo_width
            FROM mastering_parameters
            WHERE style = %s
            LIMIT 1
        """, (gen["style"],))
        params_row = cur.fetchone()
        
    if params_row:
        dsp_parameters = {
            "drive_db": float(params_row.get("drive_db", 3.0)),
            "high_shelf_db": float(params_row.get("high_shelf_db", 2.0)),
            "stereo_width": float(params_row.get("stereo_width", 1.2)),
            "limiter_ceiling_db": float(params_row.get("limiter_ceiling_db") or -0.5),
            "sub_bass_boost_db": float(params_row.get("sub_bass_boost_db") or 0.0)
        }
    else:
        dsp_parameters = {
            "drive_db": 3.0,
            "high_shelf_db": 2.0,
            "stereo_width": 1.2,
            "limiter_ceiling_db": -0.5,
            "sub_bass_boost_db": 0.0
        }
        
    cur.close()
    
    return GameDevStemsResponse(
        generation_id=str(gen["id"]),
        style=gen["style"],
        base_track_url=gen["audio_url"],
        stems=stems,
        dsp_parameters=dsp_parameters
    )


@router.get("/generations/{generation_id}/branch-info", response_model=BranchInfoResponse)
@handle_errors
async def get_generation_branch_info(
    generation_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db),
    request_id: str = None
) -> BranchInfoResponse:
    """
    Get co-creation branch analytics and splits for social artists.
    """
    cur = db.cursor()
    
    # 1. Fetch generation details
    cur.execute("""
        SELECT id, parent_id, remix_chain
        FROM generations
        WHERE id = %s
    """, (generation_id,))
    
    gen = cur.fetchone()
    if not gen:
        cur.close()
        raise HTTPException(status_code=404, detail="Generation not found")
        
    # 2. Count active child branches
    cur.execute("""
        SELECT COUNT(*) as count
        FROM generations
        WHERE parent_id = %s
    """, (generation_id,))
    branches_count = cur.fetchone()["count"]
    
    # 3. Aggregate views (for mock/telemetry: default to 1:30 multiplier based on spotify streams,
    # or look up from license transactions/active videos)
    cur.execute("""
        SELECT COUNT(*) as whitelist_count
        FROM licensed_videos
        WHERE generation_id = %s
    """, (generation_id,))
    placements_count = cur.fetchone()["whitelist_count"]
    
    # Mock view count using active placements (weighted heavily)
    total_views = (branches_count * 1250) + (placements_count * 15000) + 1500
    
    # 4. Determine splits (40/30/30 platform splits)
    parent_id = str(gen["parent_id"]) if gen["parent_id"] else None
    remix_chain = [str(x) for x in gen["remix_chain"]]
    
    grandparent_id = remix_chain[-2] if len(remix_chain) >= 2 else None
    
    if parent_id:
        if grandparent_id:
            royalties_split = {
                "parent_creator_share": 30.0,
                "grandparent_creator_share": 10.0,
                "platform_fee": 30.0,
                "sound_producer_pool": 30.0
            }
        else:
            royalties_split = {
                "parent_creator_share": 40.0,
                "grandparent_creator_share": 0.0,
                "platform_fee": 30.0,
                "sound_producer_pool": 30.0
            }
    else:
        # Base track (non-remix) gets full creator share if licensed
        royalties_split = {
            "parent_creator_share": 70.0,
            "grandparent_creator_share": 0.0,
            "platform_fee": 30.0,
            "sound_producer_pool": 0.0
        }
        
    cur.close()
    
    return BranchInfoResponse(
        generation_id=str(gen["id"]),
        parent_id=parent_id,
        grandparent_id=grandparent_id,
        active_branches_count=branches_count,
        total_derivative_views=total_views,
        royalties_split=royalties_split,
        lineage_chain=remix_chain
    )


# ============================================================================
# MODULE 3: REMIX LOGIC
# ============================================================================

@router.post("/generations/{generation_id}/remix")
@handle_errors
async def create_remix(
    generation_id: str,
    request: RemixRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Create a remix of an existing generation with transaction safety
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    
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
    user_id = current_user["user_id"]
    subscription_tier = current_user.get("subscription_tier", "free")
    
    import stripe
    import structlog
    
    logger = structlog.get_logger()
    import hashlib
    # Stable request_id for idempotency
    request_id = hashlib.sha256(
        f"{user_id}:{generation_id}:{request.prompt}:{request.layer_type}".encode()
    ).hexdigest()[:32]
    
    # Check rate limit before processing
    await check_remix_rate_limit(
        user_id=user_id,
        subscription_tier=subscription_tier
    )
    
    cur = db.cursor()
    
    try:
        # 1. Verify parent exists and is public
        cur.execute("""
            SELECT id, user_id, audio_url, is_public, parent_id, remix_chain, style
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
        
        # 3. Create Stripe charge with a STABLE idempotency key per remix lineage edge.
        # A per-request UUID here defeated Stripe's idempotency, so a retry/double-submit
        # built a different key and double-charged (FN8-693). One payment per (remixer, parent);
        # `generation_id` is the parent being remixed.
        idempotency_key = f"remix_{request_id}"
        
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
        
        # Convert stable hex request_id to a valid UUID format to satisfy DB constraint
        new_generation_id = str(uuid.UUID(request_id))
        
        # Build the remix chain, parsing the Postgres array string representation if needed
        chain_list = []
        raw_chain = parent['remix_chain']
        if isinstance(raw_chain, list):
            chain_list = raw_chain
        elif isinstance(raw_chain, str):
            clean_str = raw_chain.strip('{}')
            if clean_str:
                chain_list = [item.strip() for item in clean_str.split(',') if item.strip()]
        
        # Keep elements as strings so they represent UUIDs cleanly
        new_remix_chain = [str(x) for x in chain_list]
        new_remix_chain.append(str(parent['id']))
        
        # Calculate deterministic 16-bit watermark ID for AudioSeal
        import hashlib
        watermark_id = int(hashlib.md5(new_generation_id.encode('utf-8')).hexdigest(), 16) % 65536
        
        # Create generation record
        cur.execute("""
            INSERT INTO generations (
                id, user_id, prompt, style, layer_type, parent_id, remix_chain,
                is_public, audio_url, c2pa_manifest_url, generation_time_ms,
                cost_eur, model_version, training_data_hash, watermark_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s::uuid[], true, %s, %s, 0, 0.008, 'eu-sound-lab-v2', 'pending', %s
            )
        """, (
            new_generation_id,
            user_id,
            request.prompt,
            parent['style'],
            request.layer_type,
            parent['id'],
            new_remix_chain,
            f"https://cdn.eu-sound-lab.com/audio/{new_generation_id}.mp3",
            f"https://cdn.eu-sound-lab.com/audio/{new_generation_id}.c2pa.json",
            watermark_id
        ))
        
        # Distribute royalties using stored procedure (v2 with money-correctness constraints)
        try:
            cur.execute("""
                SELECT distribute_remix_royalties_v2(%s, %s, %s)
            """, (user_id, parent['id'], new_generation_id))
            
            logger.info(
                "royalty_distribution_success",
                function="distribute_remix_royalties_v2",
                remixer_id=user_id,
                parent_id=parent['id'],
                generation_id=new_generation_id,
                request_id=request_id
            )
        except psycopg2.IntegrityError as e:
            # Constraint violation (conservation, idempotency, or C2PA binding)
            constraint_name = e.diag.constraint_name if hasattr(e.diag, 'constraint_name') else 'unknown'
            
            logger.error(
                "royalty_constraint_violation",
                error=str(e),
                constraint=constraint_name,
                remixer_id=user_id,
                parent_id=parent['id'],
                generation_id=new_generation_id,
                request_id=request_id
            )
            
            # Alert Sentry for money-correctness violations
            try:
                from monitoring.sentry_config import capture_constraint_violation
                capture_constraint_violation(
                    constraint_name=constraint_name,
                    error_message=str(e),
                    context={
                        "remixer_id": str(user_id),
                        "parent_id": str(parent['id']),
                        "generation_id": str(new_generation_id),
                        "request_id": request_id
                    }
                )
            except ImportError:
                # Fallback to basic Sentry
                try:
                    import sentry_sdk
                    sentry_sdk.capture_message(
                        f"CRITICAL: Money-correctness constraint violated: {constraint_name}",
                        level="error"
                    )
                except ImportError:
                    pass
            
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail={
                    "error": "royalty_distribution_failed",
                    "message": "Failed to distribute royalties. This has been logged for investigation.",
                    "request_id": request_id
                }
            )
        
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

@router.get("/earnings")
@handle_errors
async def get_earnings(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> EarningsResponse:
    """
    Get user earnings dashboard data
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
    cur = db.cursor()
    
    # Get user totals from ledger (single source of truth)
    cur.execute("""
        SELECT 
            COALESCE(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 0) as total_earned,
            COALESCE(SUM(amount), 0) as current_balance
        FROM user_ledger
        WHERE user_id = %s
    """, (user_id,))
    
    ledger_totals = cur.fetchone()
    
    # Withdrawable balance comes from the append-only ledger (single source of truth),
    # NOT the stale users.pending_payout column that distribute_remix_royalties_v2 never
    # updates (FN8-692). current_balance below is the net of the ledger.

    # Get total remixes
    cur.execute("""
        SELECT SUM(remix_count) as total_remixes
        FROM generations
        WHERE user_id = %s
    """, (user_id,))
    
    remixes = cur.fetchone()

    # Get Stripe Connect status
    cur.execute("""
        SELECT stripe_connect_account_id
        FROM users
        WHERE id = %s
    """, (user_id,))
    user_row = cur.fetchone()
    stripe_connected = bool(user_row and user_row.get("stripe_connect_account_id"))
    
    # Get top earning tapes
    cur.execute("""
        SELECT id, prompt, earnings, remix_count, audio_url
        FROM generations
        WHERE user_id = %s
        ORDER BY earnings DESC
        LIMIT 5
    """, (user_id,))
    
    top_tapes = [dict(row) for row in cur.fetchall()]
    
    # Get recent transactions from user_ledger (single source of truth)
    cur.execute("""
        SELECT 
            ul.id, ul.amount, ul.transaction_type, ul.license_transaction_id, ul.payout_request_id, ul.created_at,
            g.prompt, u.username as remixer_username
        FROM user_ledger ul
        LEFT JOIN license_transactions lt ON ul.license_transaction_id = lt.id
        LEFT JOIN generations g ON lt.generation_id = g.id
        LEFT JOIN users u ON lt.remixer_id = u.id
        WHERE ul.user_id = %s
        ORDER BY ul.created_at DESC
        LIMIT 10
    """, (user_id,))
    
    raw_txs = [dict(row) for row in cur.fetchall()]
    cur.close()

    formatted_txs = []
    for row in raw_txs:
        tx_type = "royalty"
        tx_status = "completed"
        amount = float(row["amount"])
        
        t_type = row["transaction_type"]
        if t_type == "remix_earned":
            tx_type = "royalty"
        elif t_type in ("payout_requested", "payout_completed", "payout_failed", "payout_reversed"):
            tx_type = "withdrawal"
            amount = abs(amount)
            if t_type == "payout_requested":
                tx_status = "pending"
            elif t_type in ("payout_failed", "payout_reversed"):
                tx_status = "failed"
        elif t_type == "topup":
            tx_type = "remix_fee"
        elif t_type == "refund":
            tx_type = "withdrawal"
            amount = abs(amount)

        ref_id = str(row["license_transaction_id"]) if row["license_transaction_id"] else (str(row["payout_request_id"]) if row["payout_request_id"] else "")

        formatted_txs.append({
            "id": str(row["id"]),
            "type": tx_type,
            "amount": amount,
            "from_user": {
                "id": "",
                "username": row["remixer_username"]
            } if row["remixer_username"] else {
                "id": "",
                "username": "system"
            },
            "tape": {
                "id": ref_id,
                "prompt": row["prompt"]
            } if row["prompt"] else {
                "id": "",
                "prompt": f"System Ledger Entry: {row['transaction_type']}"
            },
            "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
            "status": tx_status
        })
    
    # Get this month's earnings
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as month_earned
        FROM user_ledger
        WHERE user_id = %s AND amount > 0 AND created_at >= DATE_TRUNC('month', NOW())
    """, (user_id,))
    this_month_earnings = float(cur.fetchone()['month_earned'])

    # Get chart data (group by date)
    cur.execute("""
        SELECT DATE(created_at) as date, COALESCE(SUM(amount), 0) as earnings
        FROM user_ledger
        WHERE user_id = %s AND amount > 0 AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
    """, (user_id,))
    chart_rows = cur.fetchall()
    chart_data = [{"date": str(row["date"]), "earnings": float(row["earnings"])} for row in chart_rows]

    pending_balance = float(ledger_totals['current_balance'])
    return EarningsResponse(
        total_earned=float(ledger_totals['total_earned']),
        pending_payout=pending_balance,
        pending_balance=pending_balance,
        total_remixes=int(remixes['total_remixes'] or 0),
        top_tapes=top_tapes,
        recent_transactions=formatted_txs,
        stripe_connected=stripe_connected,
        can_withdraw=pending_balance >= 20.0,
        this_month_earnings=this_month_earnings,
        chart_data=chart_data
    )

@router.post("/payout")
@handle_errors
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
    
    cur = db.cursor()
    
    # Withdrawable balance = net of the append-only ledger (FN8-692). users.pending_payout
    # is never updated by distribute_remix_royalties_v2, so it must NOT gate payouts.
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

    # Create payout request for the full available balance
    payout_id = str(uuid.uuid4())
    cur.execute("""
        INSERT INTO payout_requests (id, user_id, amount, status)
        VALUES (%s, %s, %s, 'pending')
    """, (payout_id, user_id, available))

    # Debit the ledger (append-only) instead of mutating users.pending_payout.
    # A later 'payout_failed'/'payout_reversed' entry credits it back per the schema design.
    cur.execute("""
        INSERT INTO user_ledger (user_id, transaction_type, amount, payout_request_id, description)
        VALUES (%s, 'payout_requested', %s, %s, 'Payout requested')
    """, (user_id, -available, payout_id))
    
    db.commit()
    cur.close()
    
    return {
        "payout_id": payout_id,
        "amount": available,
        "status": "pending",
        "message": "Payout will be processed within 2 business days"
    }

# ============================================================================
# MODULE 5: STREAKS & LEADERBOARDS
# ============================================================================

@router.get("/streak")
@handle_errors
async def get_streak_badge(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> StreamingResponse:
    """
    Generate streak badge PNG
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
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

@router.get("/leaderboard")
@handle_errors
async def get_leaderboard(
    leaderboard_type: str = Query("earnings", description="earnings, remixes, or streaks"),
    db = Depends(get_db)
) -> List[LeaderboardEntry]:
    """
    Get leaderboard (top 20)
    
    No authentication required - public endpoint
    """
    request_id = str(uuid.uuid4())
    
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

@router.post("/reports")
@handle_errors
async def create_report(
    request: ReportRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Create content report (DSA Art 35)
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    reporter_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
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

@router.post("/invites")
@handle_errors
async def generate_invite(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> InviteResponse:
    """
    Generate invite code (if user has invites remaining)
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
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

@router.post("/invites/redeem")
@handle_errors
async def redeem_invite(
    code: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Redeem invite code
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
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

@router.get("/waitlist")
@handle_errors
async def get_waitlist_status(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Get waitlist position
    
    SECURITY: Identity from verified JWT token, not caller-supplied parameter
    """
    user_id = current_user["user_id"]
    request_id = str(uuid.uuid4())
    
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


@router.post("/generations/{generation_id}/publish")
@handle_errors
async def publish_generation(
    generation_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
) -> dict:
    """
    Publish a generation to the explore feed.
    """
    user_id = current_user["user_id"]
    cur = db.cursor()
    try:
        # Verify ownership
        cur.execute("SELECT user_id FROM generations WHERE id = %s", (generation_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Generation not found")
        if str(row["user_id"]) != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to publish this generation")
            
        cur.execute("UPDATE generations SET is_public = true WHERE id = %s", (generation_id,))
        db.commit()
        return {"success": True, "message": "Generation published successfully"}
    finally:
        cur.close()


@router.get("/generations/{generation_id}/download")
@handle_errors
async def download_generation(
    generation_id: str,
    background_tasks: BackgroundTasks,
    mode: str = "mastered",
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Download a generation, dynamically injecting C2PA metadata and AudioSeal watermark.
    Supports mode='mastered' (A/B testing dynamic mastering) or mode='raw' (unmastered raw stream).
    """
    if mode not in ("mastered", "raw"):
        raise HTTPException(status_code=400, detail="Invalid mode")

    user_id = current_user["user_id"]
    cur = db.cursor()
    try:
        cur.execute("""
            SELECT audio_url, prompt, style, user_id, watermark_id
            FROM generations WHERE id = %s
        """, (generation_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Generation not found")
            
        audio_url = row["audio_url"]
        
        # Fallback to redirect if it is a stub/dummy track, except in development
        if os.getenv("ENVIRONMENT") != "development" and "replicate.delivery" not in audio_url and "cdn.eu-sound-lab.com" in audio_url:
            return RedirectResponse(url=audio_url)
            
        import tempfile
        import requests
        import shutil
        import hashlib
        from fastapi.responses import FileResponse
        from c2pa_embedder import C2PAEmbedder
        from producer import AudioProducer
        import torch
        import torchaudio
        
        # Deterministic 10% control / 90% treatment variant split
        hash_val = int(hashlib.md5(generation_id.encode('utf-8')).hexdigest(), 16) % 100
        variant = "control" if hash_val < 10 else "treatment"
        
        # Load dynamic mastering parameters if variant is treatment
        drive_db = None
        high_shelf_db = None
        stereo_width = None
        limiter_ceiling_db = None
        sub_bass_boost_db = None
        persona_id = None
        
        if variant == "treatment":
            cur.execute("""
                SELECT drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db, lead_producer_id
                FROM production_team_parameters WHERE style = %s
            """, (row["style"],))
            params = cur.fetchone()
            if not params:
                # Query highest-affinity producer for this style
                cur.execute("""
                    SELECT producer_id FROM producer_genre_affinities
                    WHERE style = %s
                    ORDER BY affinity_score DESC LIMIT 1
                """, (row["style"],))
                aff_row = cur.fetchone()
                lead_producer_id = aff_row["producer_id"] if aff_row else "default_producer"
                
                # Fetch default parameters for this lead producer
                cur.execute("""
                    SELECT drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db, lead_producer_id
                    FROM production_team_parameters WHERE lead_producer_id = %s LIMIT 1
                """, (lead_producer_id,))
                params = cur.fetchone()
                
            if not params:
                # Absolute fallback to ambient/zimmer parameters
                cur.execute("""
                    SELECT drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db, lead_producer_id
                    FROM production_team_parameters WHERE style = 'ambient'
                """)
                params = cur.fetchone()
            
            if params and isinstance(params, dict):
                drive_db = float(params.get("drive_db") or 3.0)
                high_shelf_db = float(params.get("high_shelf_db") or 2.0)
                stereo_width = float(params.get("stereo_width") or 1.25)
                limiter_ceiling_db = float(params.get("limiter_ceiling_db") or -0.5)
                sub_bass_boost_db = float(params.get("sub_bass_boost_db") or 0.0)
                persona_id = params.get("lead_producer_id") or "default_producer"
        
        cache_dir = "/tmp/remixa_cache"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Mode & Variant-specific cache path to prevent leaking
        if mode == "raw":
            cache_path = os.path.join(cache_dir, f"{generation_id}_raw.mp3")
        else:
            cache_path = os.path.join(cache_dir, f"{generation_id}_{variant}.mp3")
        
        # If cache exists, serve directly
        if os.path.exists(cache_path):
            return FileResponse(
                path=cache_path,
                filename=f"{generation_id}.mp3",
                media_type="audio/mpeg"
            )
            
        embedder = C2PAEmbedder()
        producer = AudioProducer()
        
        # Download the audio file to a temporary location or synthesize a dev fallback
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name
            
        try:
            is_downloaded = False
            # Only try download for real external files
            if "replicate.delivery" in audio_url:
                try:
                    response = requests.get(audio_url, timeout=15)
                    if response.status_code == 200:
                        with open(tmp_path, "wb") as f:
                            f.write(response.content)
                        is_downloaded = True
                except Exception as ex:
                    logger.warning("replicate_download_failed_falling_back", error=str(ex))
            
            if not is_downloaded:
                # Local dev fallback: generate a synthetic stereo sine wave so the mastering pipeline can run offline
                sr = 32000
                t = torch.linspace(0, 5, sr * 5)
                # Create a simple stereo sine wave
                left = torch.sin(2 * 3.14159 * 440 * t)
                right = torch.sin(2 * 3.14159 * 440 * t)
                wav = torch.stack([left, right])
                torchaudio.save(tmp_path, wav, sr)
                
            # Load raw audio to compute raw metrics
            raw_lufs = 0.0
            raw_peak = 0.0
            try:
                wav_raw, sr_raw = torchaudio.load(tmp_path)
                # Compute raw telemetry metrics
                raw_lufs = producer.calculate_lufs(wav_raw)
                try:
                    oversampling_factor = 4
                    tp_upsampled = torchaudio.functional.resample(wav_raw, sr_raw, sr_raw * oversampling_factor)
                    raw_peak_val = torch.max(torch.abs(tp_upsampled))
                    raw_peak = float(20.0 * torch.log10(torch.clamp(raw_peak_val, min=1e-6)).item())
                except Exception as e:
                    logger.warning("calculate_raw_peak_failed", error=str(e))
                    max_val = torch.max(torch.abs(wav_raw))
                    raw_peak = float(20.0 * torch.log10(torch.clamp(max_val, min=1e-6)).item())
            except Exception as e:
                logger.warning("load_raw_audio_failed_using_telemetry_defaults", error=str(e))
                wav_raw = None

            if mode == "raw":
                # Convert raw WAV/MP3 to a standard cached MP3 directly
                if wav_raw is not None:
                    torchaudio.save(tmp_path, wav_raw, sr_raw)
                
                # Save raw telemetry to database
                cur.execute("""
                    UPDATE generations
                    SET raw_lufs = %s, raw_peak = %s
                    WHERE id = %s
                """, (raw_lufs, raw_peak, generation_id))
                
                # Log processing cost
                cur.execute("""
                    INSERT INTO fact_user_compute_cogs (
                        user_id, generation_id, provider, resource_type, quantity, unit_cost_eur
                    ) VALUES (%s, %s, 'fly.io', 'audio_processing_cogs', 1.0, 0.001)
                """, (user_id, generation_id))
                
                db.commit()
                
                # Save to cache
                shutil.copy(tmp_path, cache_path)
                
                # Log the download event in metrics
                cur.execute("""
                    INSERT INTO mastering_metrics (generation_id, user_id, variant, action)
                    VALUES (%s, %s, %s, 'download')
                """, (generation_id, user_id, 'control'))
                db.commit()
                
                background_tasks.add_task(os.remove, tmp_path)
                return FileResponse(
                    path=cache_path,
                    filename=f"{generation_id}.mp3",
                    media_type="audio/mpeg"
                )
                
            # 1. Master the track using Sound Producer Module only if Treatment variant
            # If Control variant, apply equal-loudness normalization to remove volume bias
            if variant == "treatment":
                mastered_tmp_path = tmp_path.replace(".mp3", "_mastered.mp3")
                producer.master_track(
                    wav_path=tmp_path,
                    output_path=mastered_tmp_path,
                    style=row["style"],
                    drive_db=drive_db,
                    high_shelf_db=high_shelf_db,
                    stereo_width=stereo_width,
                    limiter_ceiling_db=limiter_ceiling_db,
                    sub_bass_boost_db=sub_bass_boost_db,
                    persona_id=persona_id
                )
                # Remove original raw file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                tmp_path = mastered_tmp_path
            else:
                control_tmp_path = tmp_path.replace(".mp3", "_control.mp3")
                target_lufs = producer.STYLE_TARGET_LUFS.get(row["style"], producer.DEFAULT_TARGET_LUFS)
                producer.normalize_loudness(
                    wav_path=tmp_path,
                    output_path=control_tmp_path,
                    target_lufs=target_lufs
                )
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                tmp_path = control_tmp_path
                
            # Compute mastered telemetry metrics
            mastered_lufs = 0.0
            mastered_peak = 0.0
            try:
                wav_mastered, sr_mastered = torchaudio.load(tmp_path)
                mastered_lufs = producer.calculate_lufs(wav_mastered)
                try:
                    oversampling_factor = 4
                    tp_upsampled = torchaudio.functional.resample(wav_mastered, sr_mastered, sr_mastered * oversampling_factor)
                    mastered_peak_val = torch.max(torch.abs(tp_upsampled))
                    mastered_peak = float(20.0 * torch.log10(torch.clamp(mastered_peak_val, min=1e-6)).item())
                except Exception as e:
                    logger.warning("calculate_mastered_peak_failed", error=str(e))
                    max_val = torch.max(torch.abs(wav_mastered))
                    mastered_peak = float(20.0 * torch.log10(torch.clamp(max_val, min=1e-6)).item())
            except Exception as e:
                logger.warning("load_mastered_audio_failed_using_telemetry_defaults", error=str(e))
 
            # 2. Embed AudioSeal waveform watermark
            watermark_id = row["watermark_id"]
            if watermark_id is None:
                watermark_id = int(hashlib.md5(generation_id.encode('utf-8')).hexdigest(), 16) % 65536
                
            embedder.embed_waveform_watermark(tmp_path, watermark_id)

            # 3. Embed C2PA manifest metadata in ID3 GEOB tags
            embedder.embed_mp3(
                audio_path=tmp_path,
                generation_id=generation_id,
                prompt=row["prompt"] or "",
                style=row["style"],
                user_id=str(row["user_id"])
            )
            
            # Save telemetry to database
            cur.execute("""
                UPDATE generations
                SET raw_lufs = %s, raw_peak = %s, mastered_lufs = %s, mastered_peak = %s
                WHERE id = %s
            """, (raw_lufs, raw_peak, mastered_lufs, mastered_peak, generation_id))
            
            # Log processing cost
            cur.execute("""
                INSERT INTO fact_user_compute_cogs (
                    user_id, generation_id, provider, resource_type, quantity, unit_cost_eur
                ) VALUES (%s, %s, 'fly.io', 'audio_processing_cogs', 1.0, 0.001)
            """, (user_id, generation_id))
            
            db.commit()
            
            # 4. Save to cache
            shutil.copy(tmp_path, cache_path)
            
            # 5. Log the download event in metrics
            cur.execute("""
                INSERT INTO mastering_metrics (generation_id, user_id, variant, action)
                VALUES (%s, %s, %s, 'download')
            """, (generation_id, user_id, variant))
            db.commit()
            
            background_tasks.add_task(os.remove, tmp_path)
            return FileResponse(
                path=cache_path,
                filename=f"{generation_id}.mp3",
                media_type="audio/mpeg"
            )

        except Exception as e:
            logger.error("download_processing_failed", error=str(e), generation_id=generation_id)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            return RedirectResponse(url=audio_url)
    finally:
        cur.close()


class MetricRequest(BaseModel):
    generation_id: str
    action: str  # play_10s, play_50s, play_100s, tiktok_share


@router.post("/metrics")
@handle_errors
async def collect_metrics(
    req: MetricRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Record user engagement metrics for audio playback and TikTok shares.
    """
    user_id = current_user["user_id"]
    generation_id = req.generation_id
    action = req.action
    
    if action not in ('play_10s', 'play_50s', 'play_100s', 'tiktok_share'):
        raise HTTPException(status_code=400, detail="Invalid action type")
        
    import hashlib
    # Reconstruct variant deterministically
    hash_val = int(hashlib.md5(generation_id.encode('utf-8')).hexdigest(), 16) % 100
    variant = "control" if hash_val < 10 else "treatment"
    
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO mastering_metrics (generation_id, user_id, variant, action)
            VALUES (%s, %s, %s, %s)
        """, (generation_id, user_id, variant, action))
        db.commit()
    finally:
        cur.close()
        
    return {"status": "logged", "variant": variant, "action": action}

@router.get("/admin/mastering-analytics")
@require_role(Role.ADMIN)
@handle_errors
async def get_mastering_analytics(
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    Get aggregate metrics for equal-loudness A/B testing, segmented globally
    and by style (ambient, lofi, house, trap, techno, reggaeton).
    """
    cur = db.cursor()
    try:
        cur.execute("""
            SELECT g.style, m.variant, m.action, COUNT(*) as action_count
            FROM mastering_metrics m
            JOIN generations g ON m.generation_id = g.id
            GROUP BY g.style, m.variant, m.action
        """)
        rows = cur.fetchall()
        
        # Helper to initialize metrics structure
        def init_metrics():
            return {
                "play_10s": 0,
                "play_50s": 0,
                "play_100s": 0,
                "download": 0,
                "tiktok_share": 0
            }
            
        def compute_rates(metrics):
            p10 = metrics["play_10s"]
            return {
                "midpoint_rate": round(metrics["play_50s"] / p10, 4) if p10 > 0 else 0.0,
                "completion_rate": round(metrics["play_100s"] / p10, 4) if p10 > 0 else 0.0,
                "share_rate": round(metrics["tiktok_share"] / p10, 4) if p10 > 0 else 0.0
            }
            
        # Initialize
        global_stats = {
            "control": {"metrics": init_metrics()},
            "treatment": {"metrics": init_metrics()}
        }
        
        by_style = {}
        
        for row in rows:
            style = row["style"] or "default"
            variant = row["variant"]
            action = row["action"]
            count = row["action_count"]
            
            # Skip invalid variants or actions dynamically
            if variant not in ("control", "treatment") or action not in init_metrics():
                continue
                
            if style not in by_style:
                by_style[style] = {
                    "control": {"metrics": init_metrics()},
                    "treatment": {"metrics": init_metrics()}
                }
                
            by_style[style][variant]["metrics"][action] = count
            global_stats[variant]["metrics"][action] += count
            
        # Calculate rates for global
        for var in ("control", "treatment"):
            global_stats[var]["rates"] = compute_rates(global_stats[var]["metrics"])
            
        # Calculate rates for each style
        for style in by_style:
            for var in ("control", "treatment"):
                by_style[style][var]["rates"] = compute_rates(by_style[style][var]["metrics"])
                
        return {
            "global": global_stats,
            "by_style": by_style
        }
        
    finally:
        cur.close()
