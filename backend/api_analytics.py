"""
Remixa Creator Analytics Dashboard API

Endpoints:
  GET /api/analytics/overview           — Creator dashboard overview (royalties, remix count, top tracks)
  GET /api/analytics/royalties          — Detailed royalty breakdown over time
  GET /api/analytics/top-tracks         — Most remixed tracks by this creator  
  GET /api/analytics/geographic-reach   — Geographic distribution of remixes
  GET /api/analytics/usage              — Current-period usage vs. tier limits
  GET /api/analytics/shield-report      — Whitelisted video count & status per platform
"""

import os
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any, List
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timedelta
import structlog
from clerk_auth import get_current_user
from rate_limiter import RATE_LIMITS

logger = structlog.get_logger()

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

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


# ============================================================================
# CREATOR DASHBOARD OVERVIEW
# ============================================================================

@router.get("/overview")
async def creator_overview(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Creator Dashboard — one-call overview with:
      - Total royalties earned (all-time & this month)
      - Total generations & remixes received
      - Pending payout balance
      - Top 3 most-remixed tracks
      - Shield stats
    """
    user_id = current_user["id"]
    cur = db.cursor()
    try:
        # 1. All-time royalties earned
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_earned
            FROM user_ledger
            WHERE user_id = %s AND transaction_type IN ('remix_royalty', 'pool_share')
        """, (user_id,))
        total_earned = float(cur.fetchone()["total_earned"])

        # 2. This month's royalties
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as month_earned
            FROM user_ledger
            WHERE user_id = %s 
              AND transaction_type IN ('remix_royalty', 'pool_share')
              AND created_at >= date_trunc('month', CURRENT_DATE)
        """, (user_id,))
        month_earned = float(cur.fetchone()["month_earned"])

        # 3. Available balance for payout
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as available
            FROM user_ledger
            WHERE user_id = %s
        """, (user_id,))
        available_balance = float(cur.fetchone()["available"])

        # 4. Total generations
        cur.execute("""
            SELECT COUNT(*) as gen_count
            FROM generations
            WHERE user_id = %s
        """, (user_id,))
        total_generations = cur.fetchone()["gen_count"]

        # 5. Remixes received (tracks by this user that others remixed)
        cur.execute("""
            SELECT COUNT(*) as remix_count
            FROM generations child
            JOIN generations parent ON child.parent_id = parent.id
            WHERE parent.user_id = %s AND child.user_id != %s
        """, (user_id, user_id))
        remixes_received = cur.fetchone()["remix_count"]

        # 6. Top 3 most-remixed tracks
        cur.execute("""
            SELECT parent.id, parent.prompt, parent.style, 
                   COUNT(child.id) as remix_count
            FROM generations parent
            LEFT JOIN generations child ON child.parent_id = parent.id
            WHERE parent.user_id = %s
            GROUP BY parent.id, parent.prompt, parent.style
            ORDER BY remix_count DESC
            LIMIT 3
        """, (user_id,))
        top_tracks = [
            {
                "generation_id": str(row["id"]),
                "prompt": row["prompt"],
                "style": row["style"],
                "remix_count": row["remix_count"],
            }
            for row in cur.fetchall()
        ]

        # 7. Shield stats
        cur.execute("""
            SELECT COUNT(*) as total_whitelisted,
                   COUNT(CASE WHEN status = 'active' THEN 1 END) as active
            FROM licensed_videos
            WHERE user_id = %s
        """, (user_id,))
        shield_row = cur.fetchone()

        tier = current_user.get("subscription_tier", "free")

        return {
            "user_id": user_id,
            "subscription_tier": tier,
            "royalties": {
                "total_earned_eur": round(total_earned, 2),
                "this_month_eur": round(month_earned, 2),
                "available_payout_eur": round(max(available_balance, 0), 2),
            },
            "activity": {
                "total_generations": total_generations,
                "remixes_received": remixes_received,
            },
            "top_tracks": top_tracks,
            "shield": {
                "total_whitelisted": shield_row["total_whitelisted"],
                "active_whitelisted": shield_row["active"],
            },
        }
    finally:
        cur.close()


# ============================================================================
# ROYALTY BREAKDOWN OVER TIME
# ============================================================================

@router.get("/royalties")
async def royalty_breakdown(
    period: str = Query("30d", regex="^(7d|30d|90d|1y|all)$"),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Detailed royalty breakdown, grouped by day.
    period: 7d | 30d | 90d | 1y | all
    """
    user_id = current_user["id"]

    interval_map = {
        "7d": "7 days",
        "30d": "30 days",
        "90d": "90 days",
        "1y": "365 days",
        "all": "100 years",  # effectively all-time
    }
    interval = interval_map[period]

    cur = db.cursor()
    try:
        cur.execute("""
            SELECT 
                date_trunc('day', created_at)::date as day,
                transaction_type,
                COALESCE(SUM(amount), 0) as amount,
                COUNT(*) as tx_count
            FROM user_ledger
            WHERE user_id = %s 
              AND transaction_type IN ('remix_royalty', 'pool_share', 'remix_fee')
              AND created_at >= NOW() - INTERVAL %s
            GROUP BY day, transaction_type
            ORDER BY day DESC
        """, (user_id, interval))
        rows = cur.fetchall()

        return {
            "period": period,
            "data": [
                {
                    "date": row["day"].isoformat(),
                    "type": row["transaction_type"],
                    "amount_eur": round(float(row["amount"]), 4),
                    "transaction_count": row["tx_count"],
                }
                for row in rows
            ],
        }
    finally:
        cur.close()


# ============================================================================
# TOP TRACKS (most remixed)
# ============================================================================

@router.get("/top-tracks")
async def top_tracks(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Most-remixed tracks by this creator with royalty earned per track.
    """
    user_id = current_user["id"]
    cur = db.cursor()
    try:
        cur.execute("""
            SELECT 
                parent.id,
                parent.prompt,
                parent.style,
                parent.created_at,
                COUNT(child.id) as remix_count,
                COALESCE(SUM(
                    CASE WHEN ledger.transaction_type = 'remix_royalty' 
                         THEN ledger.amount ELSE 0 END
                ), 0) as royalty_earned
            FROM generations parent
            LEFT JOIN generations child ON child.parent_id = parent.id
            LEFT JOIN user_ledger ledger 
                ON ledger.user_id = parent.user_id 
                AND ledger.description LIKE '%%' || parent.id::text || '%%'
                AND ledger.transaction_type = 'remix_royalty'
            WHERE parent.user_id = %s
            GROUP BY parent.id, parent.prompt, parent.style, parent.created_at
            ORDER BY remix_count DESC
            LIMIT %s
        """, (user_id, limit))
        rows = cur.fetchall()

        return {
            "tracks": [
                {
                    "generation_id": str(row["id"]),
                    "prompt": row["prompt"],
                    "style": row["style"],
                    "created_at": row["created_at"].isoformat(),
                    "remix_count": row["remix_count"],
                    "royalty_earned_eur": round(float(row["royalty_earned"]), 4),
                }
                for row in rows
            ]
        }
    finally:
        cur.close()


# ============================================================================
# GEOGRAPHIC REACH
# ============================================================================

@router.get("/geographic-reach")
async def geographic_reach(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Geographic distribution of users who remixed this creator's tracks.
    Requires vat_transactions join (country from billing) or user country.
    """
    user_id = current_user["id"]
    cur = db.cursor()
    try:
        cur.execute("""
            SELECT 
                COALESCE(vt.country_code, 'UNKNOWN') as country,
                COUNT(DISTINCT child.id) as remix_count,
                COUNT(DISTINCT child.user_id) as unique_remixers
            FROM generations parent
            JOIN generations child ON child.parent_id = parent.id
            LEFT JOIN vat_transactions vt ON vt.user_id = child.user_id
            WHERE parent.user_id = %s AND child.user_id != %s
            GROUP BY country
            ORDER BY remix_count DESC
        """, (user_id, user_id))
        rows = cur.fetchall()

        return {
            "countries": [
                {
                    "country_code": row["country"],
                    "remix_count": row["remix_count"],
                    "unique_remixers": row["unique_remixers"],
                }
                for row in rows
            ]
        }
    finally:
        cur.close()


# ============================================================================
# USAGE DASHBOARD — Current period usage vs. tier limits
# ============================================================================

@router.get("/usage")
async def usage_dashboard(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Returns current-period usage vs. tier limits.
    Pulls from Redis counters (via rate_limiter) and DB generation counts.
    """
    user_id = current_user["id"]
    tier = current_user.get("subscription_tier", "free")
    tier_limits = RATE_LIMITS.get(tier, RATE_LIMITS["free"])

    cur = db.cursor()
    try:
        # This hour's generation count
        cur.execute("""
            SELECT COUNT(*) as gen_count
            FROM generations
            WHERE user_id = %s 
              AND created_at >= date_trunc('hour', NOW())
        """, (user_id,))
        gen_this_hour = cur.fetchone()["gen_count"]

        # This hour's remix count
        cur.execute("""
            SELECT COUNT(*) as remix_count
            FROM generations
            WHERE user_id = %s 
              AND parent_id IS NOT NULL
              AND created_at >= date_trunc('hour', NOW())
        """, (user_id,))
        remix_this_hour = cur.fetchone()["remix_count"]

        # This month's total generation count
        cur.execute("""
            SELECT COUNT(*) as gen_count
            FROM generations
            WHERE user_id = %s 
              AND created_at >= date_trunc('month', NOW())
        """, (user_id,))
        gen_this_month = cur.fetchone()["gen_count"]

        # Shield usage this month
        cur.execute("""
            SELECT COUNT(*) as shield_count
            FROM licensed_videos
            WHERE user_id = %s
              AND whitelisted_at >= date_trunc('month', NOW())
        """, (user_id,))
        shield_this_month = cur.fetchone()["shield_count"]

        return {
            "user_id": user_id,
            "subscription_tier": tier,
            "current_hour": {
                "generations": {
                    "used": gen_this_hour,
                    "limit": tier_limits["generations_per_hour"],
                    "remaining": max(0, tier_limits["generations_per_hour"] - gen_this_hour),
                },
                "remixes": {
                    "used": remix_this_hour,
                    "limit": tier_limits["remixes_per_hour"],
                    "remaining": max(0, tier_limits["remixes_per_hour"] - remix_this_hour),
                },
            },
            "current_month": {
                "total_generations": gen_this_month,
                "shield_whitelists": shield_this_month,
            },
            "api_limit_per_minute": tier_limits["api_requests_per_minute"],
        }
    finally:
        cur.close()


# ============================================================================
# SHIELD REPORT — Whitelisted video status
# ============================================================================

@router.get("/shield-report")
async def shield_report(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    Shield / Copyright Hygiene report:
      - Per-platform whitelist count
      - Active vs. inactive
      - Recent whitelists
    """
    user_id = current_user["id"]
    tier = current_user.get("subscription_tier", "free")
    
    if tier not in ("pro", "business"):
        raise HTTPException(
            status_code=403, 
            detail="Shield report is available for Pro and Business tiers."
        )

    cur = db.cursor()
    try:
        # Platform breakdown
        cur.execute("""
            SELECT 
                platform,
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active,
                COUNT(CASE WHEN status != 'active' THEN 1 END) as inactive
            FROM licensed_videos
            WHERE user_id = %s
            GROUP BY platform
        """, (user_id,))
        platforms = cur.fetchall()

        # Recent 10 whitelists
        cur.execute("""
            SELECT id, platform, video_url, status, whitelisted_at, generation_id
            FROM licensed_videos
            WHERE user_id = %s
            ORDER BY whitelisted_at DESC
            LIMIT 10
        """, (user_id,))
        recent = cur.fetchall()

        return {
            "platforms": [
                {
                    "platform": row["platform"],
                    "total": row["total"],
                    "active": row["active"],
                    "inactive": row["inactive"],
                }
                for row in platforms
            ],
            "recent_whitelists": [
                {
                    "id": str(row["id"]),
                    "platform": row["platform"],
                    "video_url": row["video_url"],
                    "status": row["status"],
                    "whitelisted_at": row["whitelisted_at"].isoformat(),
                    "generation_id": str(row["generation_id"]),
                }
                for row in recent
            ],
        }
    finally:
        cur.close()
