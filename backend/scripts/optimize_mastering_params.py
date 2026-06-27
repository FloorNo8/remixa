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

def compute_engagement_score(metrics: dict, preferred_metric: str = "default") -> float:
    """
    Computes weighted engagement score based on user interactions and the active producer persona.
    """
    downloads = float(metrics.get("download") or 0)
    if downloads == 0:
        return 0.0
        
    p10 = float(metrics.get("play_10s") or 0)
    p50 = float(metrics.get("play_50s") or 0)
    p100 = float(metrics.get("play_100s") or 0)
    share = float(metrics.get("tiktok_share") or 0)
    
    if preferred_metric == "play_100s":
        # Rick Rubin style (retention is paramount)
        score = (0.05 * p10) + (0.1 * p50) + (1.5 * p100) + (0.2 * share)
    elif preferred_metric == "tiktok_share":
        # Quincy Jones style (viral/sharing pop appeal is paramount)
        score = (0.05 * p10) + (0.1 * p50) + (0.2 * p100) + (2.0 * share)
    elif preferred_metric == "download":
        # Hans Zimmer style (epic tracks that get downloaded/saved)
        score = (0.1 * p10) + (0.2 * p50) + (0.4 * p100) + (1.2 * downloads)
    else:
        # Default weights
        score = (0.1 * p10) + (0.3 * p50) + (0.6 * p100) + (1.0 * share)
        
    return score / downloads

def optimize_team_params(cur, style: str, params: dict) -> None:
    lead_producer_id = params.get("lead_producer_id") or "default_producer"
    drive_db = float(params.get("drive_db") or 3.0)
    high_shelf_db = float(params.get("high_shelf_db") or 2.0)
    stereo_width = float(params.get("stereo_width") or 1.25)
    limiter_ceiling_db = float(params.get("limiter_ceiling_db") or -0.5)
    sub_bass_boost_db = float(params.get("sub_bass_boost_db") or 0.0)
    
    # Persona specific values (fallback to defaults if None/joined NULLs)
    pref_metric = params.get("preferred_metric") or "play_100s"
    min_drive = float(params.get("min_drive_db") or 1.0)
    max_drive = float(params.get("max_drive_db") or 6.0)
    min_width = float(params.get("min_stereo_width") or 1.0)
    max_width = float(params.get("max_stereo_width") or 1.5)
    enable_sub_bass = bool(params.get("enable_sub_bass"))
    
    # 2. Get metrics for treatment vs control variants
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
    es_control = compute_engagement_score(metrics_by_variant["control"], pref_metric)
    es_treatment = compute_engagement_score(metrics_by_variant["treatment"], pref_metric)
    
    downloads_treatment = metrics_by_variant["treatment"].get("download", 0)
    downloads_control = metrics_by_variant["control"].get("download", 0)
    
    # Require at least a small threshold of feedback data before making parameter shifts
    min_exposures = 5
    if downloads_treatment < min_exposures or downloads_control < min_exposures:
        logger.info("insufficient_ab_testing_data_skipping_optimization", 
                    style=style, 
                    lead_producer_id=lead_producer_id,
                    treatment_downloads=downloads_treatment, 
                    control_downloads=downloads_control)
        return
        
    # 3. Dynamic adjustment decisions
    old_drive, old_shelf, old_width = drive_db, high_shelf_db, stereo_width
    old_ceiling, old_sub_bass = limiter_ceiling_db, sub_bass_boost_db
    
    if es_treatment < es_control - 0.05:
        # Treatment is performing noticeably worse
        # Scale back parameters toward the clean side using persona constraints
        drive_db = max(min_drive, drive_db - 0.2)
        high_shelf_db = max(0.0, high_shelf_db - 0.2)
        stereo_width = max(min_width, stereo_width - 0.05)
        # Raise limiter ceiling (closer to 0.0) to reduce volume squeezing
        limiter_ceiling_db = min(-0.1, limiter_ceiling_db + 0.1)
        if enable_sub_bass:
            sub_bass_boost_db = max(0.0, sub_bass_boost_db - 0.5)
        action_taken = "scaled_down_parameters"
    elif es_treatment >= es_control:
        # Treatment is doing equal or better: nudge boundaries to explore more warmth/loudness
        drive_db = min(max_drive, drive_db + 0.1)
        high_shelf_db = min(4.0, high_shelf_db + 0.1)
        stereo_width = min(max_width, stereo_width + 0.02)
        # Lower ceiling slightly to squeeze extra perceived loudness
        limiter_ceiling_db = max(-1.0, limiter_ceiling_db - 0.05)
        if enable_sub_bass:
            sub_bass_boost_db = min(4.0, sub_bass_boost_db + 0.2)
        action_taken = "nudged_up_parameters"
    else:
        action_taken = "no_significant_difference"
        
    # 4. Save updated parameters
    if (drive_db != old_drive or high_shelf_db != old_shelf or stereo_width != old_width or
        limiter_ceiling_db != old_ceiling or sub_bass_boost_db != old_sub_bass):
        cur.execute("""
            UPDATE production_team_parameters
            SET drive_db = %s, high_shelf_db = %s, stereo_width = %s,
                limiter_ceiling_db = %s, sub_bass_boost_db = %s, updated_at = NOW()
            WHERE style = %s AND lead_producer_id = %s
        """, (drive_db, high_shelf_db, stereo_width, limiter_ceiling_db, sub_bass_boost_db, style, lead_producer_id))
        logger.info("production_team_parameters_updated", 
                    style=style, 
                    lead_producer_id=lead_producer_id,
                    action=action_taken,
                    old={
                        "drive_db": old_drive, "high_shelf_db": old_shelf, "stereo_width": old_width,
                        "limiter_ceiling_db": old_ceiling, "sub_bass_boost_db": old_sub_bass
                    },
                    new={
                        "drive_db": drive_db, "high_shelf_db": high_shelf_db, "stereo_width": stereo_width,
                        "limiter_ceiling_db": limiter_ceiling_db, "sub_bass_boost_db": sub_bass_boost_db
                    },
                    scores={"control": es_control, "treatment": es_treatment})
    else:
        logger.info("production_team_parameters_retained", 
                    style=style, 
                    lead_producer_id=lead_producer_id,
                    action=action_taken, 
                    scores={"control": es_control, "treatment": es_treatment})

def optimize_params_for_style(cur, style: str) -> None:
    # 1. Fetch current parameters, persona constraints and preferences
    cur.execute("""
        SELECT pt.drive_db, pt.high_shelf_db, pt.stereo_width, pt.limiter_ceiling_db, pt.sub_bass_boost_db, pt.lead_producer_id,
               pp.preferred_metric,
               pd.min_drive_db, pd.max_drive_db, pd.min_stereo_width, pd.max_stereo_width, pd.enable_sub_bass
        FROM production_team_parameters pt
        LEFT JOIN producer_personas pp ON pt.lead_producer_id = pp.id
        LEFT JOIN persona_dsp_constraints pd ON pp.id = pd.persona_id
        WHERE pt.style = %s
        LIMIT 1
    """, (style,))
    params = cur.fetchone()
    if params:
        optimize_team_params(cur, style, params)

def main():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("database_url_not_found")
        return
        
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get list of styles configured in production team parameters
            cur.execute("SELECT DISTINCT style FROM production_team_parameters")
            styles = [row["style"] for row in cur.fetchall()]
            
            for style in styles:
                optimize_params_for_style(cur, style)
                
        conn.close()
        logger.info("mastering_parameters_optimization_run_completed")
    except Exception as e:
        logger.exception("mastering_parameters_optimization_failed", error=str(e))

if __name__ == "__main__":
    main()
