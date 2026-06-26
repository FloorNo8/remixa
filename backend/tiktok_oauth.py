"""
TikTok OAuth Integration
Handles TikTok authentication and video upload for EU Sound Lab.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import RedirectResponse
import httpx
import os
from datetime import datetime
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from pydantic import BaseModel, Field
from clerk_auth import get_current_user

def get_db():
    conn = psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    try:
        yield conn
    finally:
        conn.close()

router = APIRouter()

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
TIKTOK_REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "https://api.yourdomain.com/api/tiktok/callback")

# TikTok API endpoints
TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_UPLOAD_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"


@router.get("/api/v1/tiktok/auth")
async def tiktok_auth(user=Depends(get_current_user)):
    """
    Redirect user to TikTok OAuth authorization page.
    Scopes: video.upload, user.info.basic
    """
    if not TIKTOK_CLIENT_KEY:
        raise HTTPException(status_code=500, detail="TikTok integration not configured")
    
    # Generate state token for CSRF protection
    state = f"{user['id']}_{datetime.utcnow().timestamp()}"
    
    # Build authorization URL
    params = {
        "client_key": TIKTOK_CLIENT_KEY,
        "scope": "user.info.basic,video.upload",
        "response_type": "code",
        "redirect_uri": TIKTOK_REDIRECT_URI,
        "state": state,
    }
    
    auth_url = f"{TIKTOK_AUTH_URL}?{'&'.join([f'{k}={v}' for k, v in params.items()])}"
    
    return RedirectResponse(url=auth_url)


@router.get("/api/v1/tiktok/callback")
async def tiktok_callback(
    code: str,
    state: str,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db=Depends(get_db)
):
    """
    Handle TikTok OAuth callback.
    Exchange authorization code for access token and store in database.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"TikTok authorization failed: {error_description or error}"
        )
    
    # Extract user_id from state
    try:
        user_id = state.split("_")[0]
    except:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        response = await client.post(
            TIKTOK_TOKEN_URL,
            json={
                "client_key": TIKTOK_CLIENT_KEY,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": TIKTOK_REDIRECT_URI,
            },
            headers={"Content-Type": "application/json"},
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to exchange code for token: {response.text}"
            )
        
        token_data = response.json()
    
    # Store tokens in database
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO user_tiktok_tokens (user_id, access_token, refresh_token, expires_at, open_id, scope)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            open_id = EXCLUDED.open_id,
            scope = EXCLUDED.scope,
            updated_at = NOW()
    """, (
        user_id,
        token_data["access_token"],
        token_data.get("refresh_token"),
        datetime.utcnow().timestamp() + token_data["expires_in"],
        token_data["open_id"],
        token_data["scope"],
    ))
    db.commit()
    
    # Redirect back to frontend
    return RedirectResponse(url=f"/profile/{user_id}?tiktok_connected=true")


class TikTokUploadRequest(BaseModel):
    generation_id: str
    caption: str = Field(..., max_length=2200)
    use_original_audio: bool = True

@router.post("/api/v1/tiktok/upload")
async def upload_to_tiktok(
    request: TikTokUploadRequest,
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Upload a generated tape to TikTok.
    
    Args:
        generation_id: ID of the generation to upload
        caption: Video caption (max 150 chars)
        use_original_audio: Whether to mark as original audio
    
    Returns:
        TikTok video URL and upload status
    """
    # Get user's TikTok access token
    cursor = db.cursor()
    cursor.execute("""
        SELECT access_token, expires_at, open_id
        FROM user_tiktok_tokens
        WHERE user_id = %s
    """, (user["id"],))
    
    token_row = cursor.fetchone()
    if not token_row:
        raise HTTPException(
            status_code=400,
            detail="TikTok account not connected. Please connect your account first."
        )
    
    access_token, expires_at, open_id = token_row
    
    # Check if token expired
    if datetime.utcnow().timestamp() > expires_at:
        raise HTTPException(
            status_code=401,
            detail="TikTok access token expired. Please reconnect your account."
        )
    
    # Get generation details
    cursor.execute("""
        SELECT audio_url, prompt, duration
        FROM generations
        WHERE id = %s AND user_id = %s
    """, (request.generation_id, user["id"]))
    
    gen_row = cursor.fetchone()
    if not gen_row:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    audio_url, prompt, duration = gen_row
    
    # Download audio from R2
    async with httpx.AsyncClient() as client:
        audio_response = await client.get(audio_url)
        if audio_response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to download audio")
        
        audio_bytes = audio_response.content
    
    # Initialize TikTok upload
    async with httpx.AsyncClient() as client:
        # Step 1: Initialize upload
        init_response = await client.post(
            TIKTOK_UPLOAD_URL,
            json={
                "post_info": {
                    "title": request.caption[:150],  # Max 150 chars
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": len(audio_bytes),
                    "chunk_size": len(audio_bytes),
                    "total_chunk_count": 1,
                }
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        
        if init_response.status_code != 200:
            raise HTTPException(
                status_code=init_response.status_code,
                detail=f"TikTok upload init failed: {init_response.text}"
            )
        
        upload_data = init_response.json()
        upload_url = upload_data["data"]["upload_url"]
        publish_id = upload_data["data"]["publish_id"]
        
        # Step 2: Upload video bytes
        upload_response = await client.put(
            upload_url,
            content=audio_bytes,
            headers={"Content-Type": "video/mp4"},
        )
        
        if upload_response.status_code not in [200, 201]:
            raise HTTPException(
                status_code=upload_response.status_code,
                detail=f"TikTok video upload failed: {upload_response.text}"
            )
    
    # Track upload in database
    cursor.execute("""
        INSERT INTO tiktok_uploads (user_id, generation_id, publish_id, caption, status)
        VALUES (%s, %s, %s, %s, 'processing')
    """, (user["id"], request.generation_id, publish_id, request.caption))
    db.commit()
    
    return {
        "success": True,
        "publish_id": publish_id,
        "status": "processing",
        "message": "Video uploaded to TikTok. Processing may take a few minutes.",
    }


@router.get("/api/v1/tiktok/status/{publish_id}")
async def get_upload_status(
    publish_id: str,
    user=Depends(get_current_user),
    db=Depends(get_db)
):
    """
    Check the status of a TikTok upload.
    """
    cursor = db.cursor()
    cursor.execute("""
        SELECT status, tiktok_video_id, created_at
        FROM tiktok_uploads
        WHERE publish_id = %s AND user_id = %s
    """, (publish_id, user["id"]))
    
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    status, video_id, created_at = row
    
    return {
        "publish_id": publish_id,
        "status": status,
        "video_id": video_id,
        "video_url": f"https://www.tiktok.com/@username/video/{video_id}" if video_id else None,
        "created_at": created_at.isoformat(),
    }


@router.delete("/api/v1/tiktok/disconnect")
async def disconnect_tiktok(user=Depends(get_current_user), db=Depends(get_db)):
    """
    Disconnect TikTok account (revoke tokens).
    """
    cursor = db.cursor()
    cursor.execute("DELETE FROM user_tiktok_tokens WHERE user_id = %s", (user["id"],))
    db.commit()
    
    return {"success": True, "message": "TikTok account disconnected"}
