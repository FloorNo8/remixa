#!/usr/bin/env python3
"""
Sound Producer Mastering Parameters Optimizer.
Periodically compares engagement scores between control (unmastered) and treatment (mastered) variants
for each music style and dynamically adjusts biquad and saturation drive parameters.
"""

import os
import psycopg2
import structlog
from psycopg2.extras import RealDictCursor

logger = structlog.get_logger()

def compute_engagement_score(metrics: dict) -> float:
    """
    Computes weighted engagement score based on user interactions.
    """
    downloads = float(metrics.get("download") or 0)
    if downloads == 0:
        return 0.0
        
    p10 = float(metrics.get("play_10s") or 0)
    p50 = float(metrics.get("play_50s") or 0)
    p100 = float(metrics.get("play_100s") or 0)
    share = float(metrics.get("tiktok_share") or 0)
    
    score = (0.1 * p10) + (0.3 * p50) + (0.6 * p100) + (1.0 * share)
    return score / downloads

def optimize_params_for_style(cur, style: str) -> None:
    # 1. Fetch current parameters
    cur.execute("""
        SELECT drive_db, high_shelf_db, stereo_width
        FROM mastering_parameters
        WHERE style = %s
    """, (style,))
    params = cur.fetchone()
    if not params:
        # Style parameters not seeded, skip or insert defaults
        return
        
    drive_db = float(params["drive_db"])
    high_shelf_db = float(params["high_shelf_db"])
    stereo_width = float(params["stereo_width"])
    
    # 2. Get metrics for treatment vs control variants
    # Filter metrics to generations matching this style
    cur.execute("""
        SELECT mm.variant, mm.action, COUNT(*) as count
        FROM mastering_metrics mm
        JOIN generations g ON mm.generation_id = g.id
        WHERE g.style = %s
        GROUP BY mm.variant, mm.action
    """, (style,))
    rows = cur.fetchall()
    
    metrics_by_variant = {
        "control": {},
        "treatment": {}
    }
    for row in rows:
        v = row["variant"]
        act = row["action"]
        cnt = row["count"]
        if v in metrics_by_variant:
            metrics_by_variant[v][act] = cnt
            
    # Calculate scores
    es_control = compute_engagement_score(metrics_by_variant["control"])
    es_treatment = compute_engagement_score(metrics_by_variant["treatment"])
    
    downloads_treatment = metrics_by_variant["treatment"].get("download", 0)
    downloads_control = metrics_by_variant["control"].get("download", 0)
    
    # Require at least a small threshold of feedback data before making parameter shifts
    min_exposures = 5
    if downloads_treatment < min_exposures or downloads_control < min_exposures:
        logger.info("insufficient_ab_testing_data_skipping_optimization", 
                    style=style, 
                    treatment_downloads=downloads_treatment, 
                    control_downloads=downloads_control)
        return
        
    # 3. Dynamic adjustment decisions
    old_drive, old_shelf, old_width = drive_db, high_shelf_db, stereo_width
    
    if es_treatment < es_control - 0.05:
        # Treatment is performing noticeably worse (over-processed, dynamic distortion, or fatigue)
        # Scale back parameters toward a cleaner, less saturated sound
        drive_db = max(1.0, drive_db - 0.2)
        high_shelf_db = max(0.0, high_shelf_db - 0.2)
        stereo_width = max(1.0, stereo_width - 0.05)
        action_taken = "scaled_down_parameters"
    elif es_treatment >= es_control:
        # Treatment is doing equal or better: nudge boundaries to explore more warmth/loudness
        # Saturated volume drive slightly increased up to safe ceiling
        drive_db = min(6.0, drive_db + 0.1)
        high_shelf_db = min(4.0, high_shelf_db + 0.1)
        stereo_width = min(1.5, stereo_width + 0.02)
        action_taken = "nudged_up_parameters"
    else:
        action_taken = "no_significant_difference"
        
    # 4. Save updated parameters
    if drive_db != old_drive or high_shelf_db != old_shelf or stereo_width != old_width:
        cur.execute("""
            UPDATE mastering_parameters
            SET drive_db = %s, high_shelf_db = %s, stereo_width = %s, updated_at = NOW()
            WHERE style = %s
        """, (drive_db, high_shelf_db, stereo_width, style))
        logger.info("mastering_parameters_updated", 
                    style=style, 
                    action=action_taken,
                    old={"drive_db": old_drive, "high_shelf_db": old_shelf, "stereo_width": old_width},
                    new={"drive_db": drive_db, "high_shelf_db": high_shelf_db, "stereo_width": stereo_width},
                    scores={"control": es_control, "treatment": es_treatment})
    else:
        logger.info("mastering_parameters_retained", 
                    style=style, 
                    action=action_taken, 
                    scores={"control": es_control, "treatment": es_treatment})

def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("database_url_not_found")
        return
        
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get list of styles configured in mastering parameters
            cur.execute("SELECT style FROM mastering_parameters")
            styles = [row["style"] for row in cur.fetchall()]
            
            for style in styles:
                optimize_params_for_style(cur, style)
                
        conn.close()
        logger.info("mastering_parameters_optimization_run_completed")
    except Exception as e:
        logger.exception("mastering_parameters_optimization_failed", error=str(e))

if __name__ == "__main__":
    main()
