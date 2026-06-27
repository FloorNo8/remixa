"""
Remixa Shield Whitelisting API Endpoints
Provides endpoints to register and check copyright-cleared whitelisted video URLs.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from pydantic import BaseModel, HttpUrl
from typing import Optional, Dict, Any, List
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
import structlog
import os
from datetime import datetime
from clerk_auth import get_current_user
from rbac import Role, require_any_role, require_role

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/shield", tags=["shield"])

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
# MODELS
# ============================================================================

class WhitelistRequest(BaseModel):
    generation_id: str
    platform: str
    video_url: str

class WhitelistResponse(BaseModel):
    id: str
    user_id: Optional[str]
    generation_id: str
    platform: str
    video_url: str
    whitelisted_at: str
    status: str

class BatchWhitelistRequest(BaseModel):
    generation_id: str
    platform: str
    video_urls: List[str]

class BatchWhitelistResponse(BaseModel):
    whitelisted: List[WhitelistResponse]
    errors: List[Dict[str, str]]

# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/whitelist", response_model=WhitelistResponse)
async def register_whitelist(
    request: WhitelistRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    B2B Premium SaaS - Whitelist a video URL using a licensed Remixa generation.
    Ensures zero mute/delisting risk.
    """
    # 1. Enforce Premium Tier or Admin role for whitelisting (B2B SaaS Gate)
    user_tier = current_user.get("subscription_tier")
    user_role = current_user.get("role")
    
    if user_tier not in ("pro", "business") and user_role not in (Role.ADMIN, Role.MODERATOR):
        raise HTTPException(
            status_code=403,
            detail="Whitelisting is a premium feature. Please upgrade to Pro or Business tier."
        )

    cur = db.cursor()
    try:
        # 2. Check if the generation exists
        cur.execute("SELECT user_id FROM generations WHERE id = %s", (request.generation_id,))
        gen = cur.fetchone()
        if not gen:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        # 3. Check if current user is owner, or if they are admin/moderator, or premium tier licensing
        # Note: business users can whitelist any licensed sound remix, whereas pro can only whitelist their own
        if user_role not in (Role.ADMIN, Role.MODERATOR) and user_tier != "business":
            if str(gen["user_id"]) != current_user["id"]:
                raise HTTPException(
                    status_code=403,
                    detail="You can only whitelist videos for sound generations you own."
                )

        # Validate platform
        platform_lower = request.platform.lower()
        if platform_lower not in ('youtube', 'tiktok', 'instagram'):
            raise HTTPException(status_code=400, detail="Invalid platform. Must be youtube, tiktok, or instagram.")

        # 4. Insert whitelist entry
        entry_id = str(uuid.uuid4())
        try:
            cur.execute("""
                INSERT INTO licensed_videos (id, user_id, generation_id, platform, video_url, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                RETURNING id, user_id, generation_id, platform, video_url, whitelisted_at, status
            """, (entry_id, current_user["id"], request.generation_id, platform_lower, request.video_url))
            
            row = cur.fetchone()
            db.commit()
            
            logger.info(
                "video_whitelisted",
                user_id=current_user["id"],
                video_url=request.video_url,
                generation_id=request.generation_id,
                platform=platform_lower
            )
            
            return WhitelistResponse(
                id=str(row["id"]),
                user_id=str(row["user_id"]) if row["user_id"] else None,
                generation_id=str(row["generation_id"]),
                platform=row["platform"],
                video_url=row["video_url"],
                whitelisted_at=row["whitelisted_at"].isoformat(),
                status=row["status"]
            )
        except psycopg2.IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="This video URL has already been whitelisted.")
            
    finally:
        cur.close()


@router.post("/batch-whitelist", response_model=BatchWhitelistResponse)
async def register_batch_whitelist(
    request: BatchWhitelistRequest,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """
    B2B Premium SaaS - Whitelist multiple video URLs at once.
    """
    user_tier = current_user.get("subscription_tier")
    user_role = current_user.get("role")
    
    if user_tier not in ("pro", "business") and user_role not in (Role.ADMIN, Role.MODERATOR):
        raise HTTPException(
            status_code=403,
            detail="Whitelisting is a premium feature. Please upgrade to Pro or Business tier."
        )

    platform_lower = request.platform.lower()
    if platform_lower not in ('youtube', 'tiktok', 'instagram'):
        raise HTTPException(status_code=400, detail="Invalid platform. Must be youtube, tiktok, or instagram.")

    cur = db.cursor()
    try:
        # Check if the generation exists
        cur.execute("SELECT user_id FROM generations WHERE id = %s", (request.generation_id,))
        gen = cur.fetchone()
        if not gen:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        # Ownership check
        if user_role not in (Role.ADMIN, Role.MODERATOR) and user_tier != "business":
            if str(gen["user_id"]) != current_user["id"]:
                raise HTTPException(
                    status_code=403,
                    detail="You can only whitelist videos for sound generations you own."
                )

        whitelisted = []
        errors = []

        for url in request.video_urls:
            # We use savepoints to isolate errors for individual URLs
            cur.execute("SAVEPOINT batch_url_savepoint")
            entry_id = str(uuid.uuid4())
            try:
                cur.execute("""
                    INSERT INTO licensed_videos (id, user_id, generation_id, platform, video_url, status)
                    VALUES (%s, %s, %s, %s, %s, 'active')
                    RETURNING id, user_id, generation_id, platform, video_url, whitelisted_at, status
                """, (entry_id, current_user["id"], request.generation_id, platform_lower, url))
                row = cur.fetchone()
                cur.execute("RELEASE SAVEPOINT batch_url_savepoint")
                
                whitelisted.append(WhitelistResponse(
                    id=str(row["id"]),
                    user_id=str(row["user_id"]) if row["user_id"] else None,
                    generation_id=str(row["generation_id"]),
                    platform=row["platform"],
                    video_url=row["video_url"],
                    whitelisted_at=row["whitelisted_at"].isoformat(),
                    status=row["status"]
                ))
            except psycopg2.IntegrityError:
                cur.execute("ROLLBACK TO SAVEPOINT batch_url_savepoint")
                errors.append({"url": url, "error": "This video URL has already been whitelisted."})
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT batch_url_savepoint")
                errors.append({"url": url, "error": str(e)})

        db.commit()
        
        logger.info(
            "batch_whitelisted",
            user_id=current_user["id"],
            count_success=len(whitelisted),
            count_errors=len(errors)
        )
        
        return BatchWhitelistResponse(whitelisted=whitelisted, errors=errors)
    finally:
        cur.close()


@router.get("/whitelist/check")
async def check_whitelist(
    video_url: str = Query(..., min_length=1),
    db = Depends(get_db)
):
    """
    Public Endpoint - Check if a video URL is copyright-cleared/whitelisted on Remixa.
    Used by DSP clearing pipelines or platforms to prevent muting.
    """
    cur = db.cursor()
    try:
        cur.execute("""
            SELECT id, platform, video_url, status, whitelisted_at, generation_id
            FROM licensed_videos
            WHERE video_url = %s
        """, (video_url,))
        row = cur.fetchone()
        
        if not row:
            return {"cleared": False, "reason": "No whitelist registration found for this URL."}
            
        if row["status"] != "active":
            return {"cleared": False, "reason": "Whitelist registration is inactive."}
            
        return {
            "cleared": True,
            "id": str(row["id"]),
            "platform": row["platform"],
            "video_url": row["video_url"],
            "generation_id": str(row["generation_id"]),
            "whitelisted_at": row["whitelisted_at"].isoformat(),
            "status": row["status"]
        }
    finally:
        cur.close()


@router.delete("/whitelist/{entry_id}")
async def remove_whitelist(
    entry_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """Remove a whitelisted URL registration."""
    cur = db.cursor()
    try:
        cur.execute("SELECT user_id FROM licensed_videos WHERE id = %s", (entry_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Whitelist registration not found")
            
        user_role = current_user.get("role")
        if user_role not in (Role.ADMIN, Role.MODERATOR) and str(row["user_id"]) != current_user["id"]:
            raise HTTPException(status_code=403, detail="You do not have permission to delete this registration.")
            
        cur.execute("DELETE FROM licensed_videos WHERE id = %s", (entry_id,))
        db.commit()
        
        logger.info("whitelist_removed", user_id=current_user["id"], entry_id=entry_id)
        return {"ok": True, "entry_id": entry_id, "deleted": True}
    finally:
        cur.close()
