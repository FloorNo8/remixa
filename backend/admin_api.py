"""Admin API endpoints for Remixa."""
from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timedelta
from typing import Optional
import psycopg2
import os
from rbac import require_role, require_any_role, Role
from clerk_auth import get_current_user
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_db():
    """Get database connection."""
    return psycopg2.connect(os.getenv("DATABASE_URL"))


# get_current_user is imported from clerk_auth (real Clerk JWT verification) — FN8-689.
# The previous mock returned a hardcoded admin for everyone; it has been removed.


@router.get("/dashboard")
@require_role(Role.ADMIN)
async def get_dashboard(current_user: dict = Depends(get_current_user)):
    """
    Admin dashboard metrics.
    
    Returns:
        - User statistics (total, new today, active 7d)
        - Generation statistics (total, today, success rate)
        - Revenue metrics (total, today, pending payouts)
        - Moderation queue status
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        today = datetime.utcnow().date()
        week_ago = datetime.utcnow() - timedelta(days=7)
        
        # User metrics
        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM users WHERE DATE(created_at) = %s", (today,))
        new_users_today = cur.fetchone()[0]
        
        cur.execute(
            "SELECT COUNT(DISTINCT user_id) FROM generations WHERE created_at > %s",
            (week_ago,)
        )
        active_users_7d = cur.fetchone()[0]
        
        # Generation metrics
        cur.execute("SELECT COUNT(*) FROM generations")
        total_generations = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM generations WHERE DATE(created_at) = %s", (today,))
        generations_today = cur.fetchone()[0]
        
        cur.execute("""
            SELECT 
                CAST(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) AS FLOAT) / 
                NULLIF(COUNT(*), 0)
            FROM generations 
            WHERE created_at > %s
        """, (week_ago,))
        success_rate = cur.fetchone()[0] or 0.0
        
        # Revenue metrics
        cur.execute("SELECT COALESCE(SUM(amount), 0) FROM license_transactions")
        total_revenue = cur.fetchone()[0]
        
        cur.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM license_transactions WHERE DATE(created_at) = %s",
            (today,)
        )
        revenue_today = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COALESCE(SUM(user_balance), 0) FROM (
                SELECT SUM(amount) as user_balance 
                FROM user_ledger 
                GROUP BY user_id 
                HAVING SUM(amount) >= 20.00
            ) subq
        """)
        pending_payouts = cur.fetchone()[0]
        
        # Moderation metrics
        cur.execute("SELECT COUNT(*) FROM reports WHERE status='pending'")
        pending_reports = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM reports 
            WHERE status IN ('approved', 'rejected') 
            AND DATE(updated_at) = %s
        """, (today,))
        resolved_today = cur.fetchone()[0]
        
        metrics = {
            "users": {
                "total": total_users,
                "new_today": new_users_today,
                "active_7d": active_users_7d
            },
            "generations": {
                "total": total_generations,
                "today": generations_today,
                "success_rate": float(success_rate)
            },
            "revenue": {
                "total": float(total_revenue),
                "today": float(revenue_today),
                "pending_payouts": float(pending_payouts)
            },
            "moderation": {
                "pending_reports": pending_reports,
                "resolved_today": resolved_today
            }
        }
        
        logger.info("admin_dashboard_accessed", user_id=current_user["id"])
        return metrics
        
    finally:
        cur.close()
        conn.close()


@router.get("/moderation/queue")
@require_any_role([Role.MODERATOR, Role.ADMIN])
async def get_moderation_queue(
    status: str = Query("pending", regex="^(pending|approved|rejected)$"),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Get moderation queue.
    
    Args:
        status: Filter by status (pending, approved, rejected)
        limit: Maximum number of reports to return
    
    Returns:
        List of reports with generation and reporter details
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                r.id, r.generation_id, r.reason, r.status, r.created_at,
                r.moderator_id, r.moderator_reason,
                g.prompt, g.audio_url, g.layer_type,
                u.email as reporter_email, u.username as reporter_username,
                creator.username as creator_username
            FROM reports r
            JOIN generations g ON r.generation_id = g.id
            JOIN users u ON r.reporter_id = u.id
            JOIN users creator ON g.user_id = creator.id
            WHERE r.status = %s
            ORDER BY r.created_at ASC
            LIMIT %s
        """, (status, limit))
        
        columns = [desc[0] for desc in cur.description]
        reports = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        # Convert datetime objects to ISO strings
        for report in reports:
            if report.get('created_at'):
                report['created_at'] = report['created_at'].isoformat()
        
        logger.info(
            "moderation_queue_accessed",
            user_id=current_user["id"],
            status=status,
            count=len(reports)
        )
        
        return reports
        
    finally:
        cur.close()
        conn.close()


@router.post("/moderation/{report_id}/action")
@require_any_role([Role.MODERATOR, Role.ADMIN])
async def moderate_report(
    report_id: str,
    action: str = Query(..., regex="^(approve|reject|delete_content)$"),
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Take action on a report.
    
    Args:
        report_id: ID of the report
        action: Action to take (approve, reject, delete_content)
        reason: Optional reason for the action
    
    Returns:
        Success confirmation
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Get report details
        cur.execute("SELECT generation_id FROM reports WHERE id = %s", (report_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        
        generation_id = row[0]
        
        if action == "delete_content":
            # Delete the generation
            cur.execute(
                "UPDATE generations SET status = 'deleted', deleted_at = %s WHERE id = %s",
                (datetime.utcnow(), generation_id)
            )
            cur.execute("""
                UPDATE reports 
                SET status = 'approved', moderator_id = %s, moderator_reason = %s, updated_at = %s 
                WHERE id = %s
            """, (current_user["id"], reason, datetime.utcnow(), report_id))
            
        elif action == "approve":
            cur.execute("""
                UPDATE reports 
                SET status = 'approved', moderator_id = %s, moderator_reason = %s, updated_at = %s 
                WHERE id = %s
            """, (current_user["id"], reason, datetime.utcnow(), report_id))
            
        elif action == "reject":
            cur.execute("""
                UPDATE reports 
                SET status = 'rejected', moderator_id = %s, moderator_reason = %s, updated_at = %s 
                WHERE id = %s
            """, (current_user["id"], reason, datetime.utcnow(), report_id))
        
        conn.commit()
        
        logger.info(
            "moderation_action_taken",
            user_id=current_user["id"],
            report_id=report_id,
            action=action,
            generation_id=generation_id
        )
        
        return {"ok": True, "action": action, "report_id": report_id}
        
    finally:
        cur.close()
        conn.close()


@router.get("/users/search")
@require_role(Role.ADMIN)
async def search_users(
    q: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Search users.
    
    Args:
        q: Search query (email or user ID)
        limit: Maximum number of users to return
    
    Returns:
        List of users with generation count and earnings
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        if q:
            cur.execute("""
                SELECT 
                    u.id, u.email, u.username, u.created_at, u.role, u.banned, u.ban_reason,
                    u.balance, u.stripe_account_id,
                    COUNT(DISTINCT g.id) as generation_count,
                    COALESCE(SUM(lt.creator_share), 0) as total_earnings
                FROM users u
                LEFT JOIN generations g ON u.id = g.user_id
                LEFT JOIN license_transactions lt ON u.id = lt.original_creator_id
                WHERE u.email ILIKE %s OR u.id::text ILIKE %s OR u.username ILIKE %s
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT %s
            """, (f"%{q}%", f"%{q}%", f"%{q}%", limit))
        else:
            cur.execute("""
                SELECT 
                    u.id, u.email, u.username, u.created_at, u.role, u.banned, u.ban_reason,
                    u.balance, u.stripe_account_id,
                    COUNT(DISTINCT g.id) as generation_count,
                    COALESCE(SUM(lt.creator_share), 0) as total_earnings
                FROM users u
                LEFT JOIN generations g ON u.id = g.user_id
                LEFT JOIN license_transactions lt ON u.id = lt.original_creator_id
                GROUP BY u.id
                ORDER BY u.created_at DESC
                LIMIT %s
            """, (limit,))
        
        columns = [desc[0] for desc in cur.description]
        users = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        # Convert datetime and decimal objects
        for user in users:
            if user.get('created_at'):
                user['created_at'] = user['created_at'].isoformat()
            if user.get('balance'):
                user['balance'] = float(user['balance'])
            if user.get('total_earnings'):
                user['total_earnings'] = float(user['total_earnings'])
        
        logger.info(
            "users_searched",
            user_id=current_user["id"],
            query=q,
            results=len(users)
        )
        
        return users
        
    finally:
        cur.close()
        conn.close()


@router.post("/users/{user_id}/ban")
@require_role(Role.ADMIN)
async def ban_user(
    user_id: str,
    reason: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Ban a user.
    
    Args:
        user_id: ID of user to ban
        reason: Reason for ban
    
    Returns:
        Success confirmation
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE users 
            SET banned = TRUE, ban_reason = %s, banned_at = %s, banned_by = %s 
            WHERE id = %s
        """, (reason, datetime.utcnow(), current_user["id"], user_id))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        conn.commit()
        
        logger.warning(
            "user_banned",
            admin_id=current_user["id"],
            banned_user_id=user_id,
            reason=reason
        )
        
        return {"ok": True, "user_id": user_id, "banned": True}
        
    finally:
        cur.close()
        conn.close()


@router.post("/users/{user_id}/unban")
@require_role(Role.ADMIN)
async def unban_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Unban a user."""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE users 
            SET banned = FALSE, ban_reason = NULL, banned_at = NULL, banned_by = NULL 
            WHERE id = %s
        """, (user_id,))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        conn.commit()
        
        logger.info(
            "user_unbanned",
            admin_id=current_user["id"],
            unbanned_user_id=user_id
        )
        
        return {"ok": True, "user_id": user_id, "banned": False}
        
    finally:
        cur.close()
        conn.close()


@router.get("/content")
@require_role(Role.ADMIN)
async def get_all_content(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all generations.
    
    Args:
        limit: Maximum number of generations to return
        offset: Offset for pagination
    
    Returns:
        List of generations with creator and remix count
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            SELECT 
                g.id, g.prompt, g.audio_url, g.layer_type, g.created_at, g.status,
                g.featured, g.plays, g.likes,
                u.email as creator_email, u.username as creator_username,
                COUNT(DISTINCT r.id) as remix_count
            FROM generations g
            JOIN users u ON g.user_id = u.id
            LEFT JOIN generations r ON r.parent_id = g.id
            WHERE g.status != 'deleted'
            GROUP BY g.id, u.email, u.username
            ORDER BY g.created_at DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        columns = [desc[0] for desc in cur.description]
        tapes = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        # Convert datetime objects
        for tape in tapes:
            if tape.get('created_at'):
                tape['created_at'] = tape['created_at'].isoformat()
        
        logger.info(
            "content_list_accessed",
            user_id=current_user["id"],
            limit=limit,
            offset=offset,
            count=len(tapes)
        )
        
        return tapes
        
    finally:
        cur.close()
        conn.close()


@router.post("/content/{generation_id}/feature")
@require_role(Role.ADMIN)
async def feature_content(
    generation_id: str,
    featured: bool,
    current_user: dict = Depends(get_current_user)
):
    """
    Feature or unfeature content.
    
    Args:
        generation_id: ID of generation
        featured: Whether to feature the content
    
    Returns:
        Success confirmation
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE generations 
            SET featured = %s, featured_at = %s, featured_by = %s 
            WHERE id = %s
        """, (featured, datetime.utcnow() if featured else None, current_user["id"] if featured else None, generation_id))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        conn.commit()
        
        logger.info(
            "content_featured" if featured else "content_unfeatured",
            admin_id=current_user["id"],
            generation_id=generation_id
        )
        
        return {"ok": True, "generation_id": generation_id, "featured": featured}
        
    finally:
        cur.close()
        conn.close()


@router.delete("/content/{generation_id}")
@require_role(Role.ADMIN)
async def delete_content(
    generation_id: str,
    reason: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete content.
    
    Args:
        generation_id: ID of generation to delete
        reason: Optional reason for deletion
    
    Returns:
        Success confirmation
    """
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("""
            UPDATE generations 
            SET status = 'deleted', deleted_at = %s, deleted_by = %s, deletion_reason = %s 
            WHERE id = %s
        """, (datetime.utcnow(), current_user["id"], reason, generation_id))
        
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Generation not found")
        
        conn.commit()
        
        logger.warning(
            "content_deleted",
            admin_id=current_user["id"],
            generation_id=generation_id,
            reason=reason
        )
        
        return {"ok": True, "generation_id": generation_id, "deleted": True}
        
    finally:
        cur.close()
        conn.close()


@router.get("/vat/report")
@require_role(Role.ADMIN)
async def generate_vat_report(
    quarter: str = Query(..., regex="^20[0-9]{2}-Q[1-4]$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate VAT MOSS report for a quarter.
    
    Args:
        quarter: Quarter in format YYYY-QN (e.g., "2024-Q1")
    
    Returns:
        VAT MOSS XML report
    """
    from vat_moss import generate_moss_xml
    
    year, q = quarter.split("-Q")
    start_month = (int(q) - 1) * 3 + 1
    end_month = start_month + 2
    
    start_date = f"{year}-{start_month:02d}-01"
    # Get last day of end month
    if end_month in [1, 3, 5, 7, 8, 10, 12]:
        last_day = 31
    elif end_month in [4, 6, 9, 11]:
        last_day = 30
    else:  # February
        last_day = 29 if int(year) % 4 == 0 else 28
    
    end_date = f"{year}-{end_month:02d}-{last_day}"
    
    logger.info(
        "vat_report_generated",
        admin_id=current_user["id"],
        quarter=quarter,
        start_date=start_date,
        end_date=end_date
    )
    
    xml = generate_moss_xml(start_date, end_date)
    return {"quarter": quarter, "xml": xml}


@router.get("/system/health")
@require_role(Role.ADMIN)
async def system_health(current_user: dict = Depends(get_current_user)):
    """
    System health check.
    
    Returns:
        Status of all system components and resource usage
    """
    import psutil
    from monitoring import health_checker
    
    # Get comprehensive health status
    health_status = health_checker.check_all()
    
    # Add system resources
    health_status["system"] = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
    }
    
    logger.info(
        "system_health_checked",
        admin_id=current_user["id"],
        status=health_status["status"]
    )
    
    return health_status
