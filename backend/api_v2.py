"""
EU TikTok Sound Lab v2 - Social & Remix API
Modules 2-7: Explore, Remix, Earnings, Streaks, Reports, Invites
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
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

async def get_explore_feed(
    sort: str = Query("trending", description="trending, recent, or top"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db = Depends(get_db)
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

async def get_generation_detail(
    generation_id: str,
    db = Depends(get_db)
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
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
) -> dict:
    """
    Create a remix of an existing generation
    
    Steps:
    1. Verify parent is public
    2. Check/charge user balance (€0.10)
    3. Distribute royalties
    4. Generate new audio
    5. Update remix chain
    """
    
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
        raise HTTPException(status_code=403, detail="Cannot remix private generation")
    
    # 2. Check user balance
    cur.execute("SELECT balance FROM user_balances WHERE user_id = %s", (user_id,))
    balance_row = cur.fetchone()
    balance = float(balance_row['balance']) if balance_row else 0.0
    
    if balance < 0.10:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient balance. Need €0.10, have €{balance:.2f}. Top up at /api/stripe/topup"
        )
    
    # Deduct balance
    cur.execute("""
        UPDATE user_balances 
        SET balance = balance - 0.10, updated_at = NOW()
        WHERE user_id = %s
    """, (user_id,))
    
    # 3. Generate new audio (background task)
    new_generation_id = str(uuid.uuid4())
    
    # Build remix chain
    new_remix_chain = parent['remix_chain'] + [str(parent['id'])]
    
    # Create generation record (audio will be uploaded by background task)
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
    
    # 4. Distribute royalties using stored procedure
    cur.execute("""
        SELECT distribute_remix_royalties(%s, %s, %s)
    """, (user_id, parent['id'], new_generation_id))
    
    db.commit()
    cur.close()
    
    # 5. Queue audio generation
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
        "message": "Remix queued. Check back in 10 seconds."
    }

async def generate_remix_audio(
    generation_id: str,
    parent_audio_url: str,
    prompt: str,
    layer_type: str,
    voice_model_id: Optional[str]
):
    """
    Background task: Generate remix audio using Replicate
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

async def get_earnings(
    user_id: str,
    db = Depends(get_db)
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

async def request_payout(
    user_id: str,
    db = Depends(get_db)
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

async def get_streak_badge(
    user_id: str,
    db = Depends(get_db)
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

async def get_leaderboard(
    leaderboard_type: str = Query("earnings", description="earnings, remixes, or streaks"),
    db = Depends(get_db)
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

async def create_report(
    request: ReportRequest,
    reporter_id: str,
    db = Depends(get_db)
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

async def generate_invite(
    user_id: str,
    db = Depends(get_db)
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

async def redeem_invite(
    code: str,
    user_id: str,
    db = Depends(get_db)
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

async def get_waitlist_status(
    user_id: str,
    db = Depends(get_db)
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
