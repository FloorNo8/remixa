#!/usr/bin/env python3
"""
Midnight Leaderboard Updater
Runs every day at midnight to update leaderboards and rankings.

Updates:
1. Top Earners (all-time)
2. Top Earners (this month)
3. Most Remixed Tapes
4. Trending Tapes (last 7 days)
5. Top Creators (by followers)
"""

import psycopg2
import os
from datetime import datetime, timedelta
import json

DATABASE_URL = os.getenv("DATABASE_URL")


def update_top_earners():
    """Update top earners leaderboard."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # All-time top earners
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.avatar_url,
                COALESCE(SUM(t.amount), 0) as total_earnings,
                COUNT(DISTINCT g.id) as tapes_count
            FROM users u
            LEFT JOIN transactions t ON t.user_id = u.id AND t.type IN ('remix_fee', 'royalty')
            LEFT JOIN generations g ON g.user_id = u.id
            GROUP BY u.id, u.username, u.avatar_url
            ORDER BY total_earnings DESC
            LIMIT 100
        """)
        
        all_time_earners = [
            {
                "rank": idx + 1,
                "user_id": row[0],
                "username": row[1],
                "avatar_url": row[2],
                "total_earnings": float(row[3]),
                "tapes_count": row[4],
            }
            for idx, row in enumerate(cursor.fetchall())
        ]
        
        # This month top earners
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.avatar_url,
                COALESCE(SUM(t.amount), 0) as month_earnings,
                COUNT(DISTINCT g.id) as tapes_count
            FROM users u
            LEFT JOIN transactions t ON t.user_id = u.id 
                AND t.type IN ('remix_fee', 'royalty')
                AND t.created_at >= DATE_TRUNC('month', CURRENT_DATE)
            LEFT JOIN generations g ON g.user_id = u.id
            GROUP BY u.id, u.username, u.avatar_url
            HAVING COALESCE(SUM(t.amount), 0) > 0
            ORDER BY month_earnings DESC
            LIMIT 100
        """)
        
        month_earners = [
            {
                "rank": idx + 1,
                "user_id": row[0],
                "username": row[1],
                "avatar_url": row[2],
                "month_earnings": float(row[3]),
                "tapes_count": row[4],
            }
            for idx, row in enumerate(cursor.fetchall())
        ]
        
        # Store in leaderboards table
        cursor.execute("""
            INSERT INTO leaderboards (type, data, updated_at)
            VALUES ('top_earners_all_time', %s, NOW()),
                   ('top_earners_month', %s, NOW())
            ON CONFLICT (type) DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at
        """, (json.dumps(all_time_earners), json.dumps(month_earners)))
        
        conn.commit()
        
        print(f"✅ Updated top earners leaderboards")
        print(f"   All-time: {len(all_time_earners)} users")
        print(f"   This month: {len(month_earners)} users")
        
    except Exception as e:
        print(f"❌ Error updating top earners: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_most_remixed():
    """Update most remixed tapes leaderboard."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                g.id,
                g.prompt,
                g.audio_url,
                u.id as creator_id,
                u.username as creator_username,
                COUNT(r.id) as remix_count,
                COALESCE(SUM(t.amount), 0) as total_earnings
            FROM generations g
            JOIN users u ON u.id = g.user_id
            LEFT JOIN generations r ON r.parent_id = g.id
            LEFT JOIN transactions t ON t.tape_id = g.id AND t.type IN ('remix_fee', 'royalty')
            GROUP BY g.id, g.prompt, g.audio_url, u.id, u.username
            HAVING COUNT(r.id) > 0
            ORDER BY remix_count DESC, total_earnings DESC
            LIMIT 100
        """)
        
        most_remixed = [
            {
                "rank": idx + 1,
                "tape_id": row[0],
                "prompt": row[1],
                "audio_url": row[2],
                "creator_id": row[3],
                "creator_username": row[4],
                "remix_count": row[5],
                "total_earnings": float(row[6]),
            }
            for idx, row in enumerate(cursor.fetchall())
        ]
        
        cursor.execute("""
            INSERT INTO leaderboards (type, data, updated_at)
            VALUES ('most_remixed', %s, NOW())
            ON CONFLICT (type) DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at
        """, (json.dumps(most_remixed),))
        
        conn.commit()
        
        print(f"✅ Updated most remixed leaderboard: {len(most_remixed)} tapes")
        
    except Exception as e:
        print(f"❌ Error updating most remixed: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_trending():
    """Update trending tapes (last 7 days)."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Calculate trending score: (plays * 1) + (likes * 2) + (remixes * 5)
        cursor.execute("""
            SELECT 
                g.id,
                g.prompt,
                g.audio_url,
                u.id as creator_id,
                u.username as creator_username,
                g.plays_count,
                g.likes_count,
                COUNT(r.id) as remix_count,
                (g.plays_count * 1 + g.likes_count * 2 + COUNT(r.id) * 5) as trending_score
            FROM generations g
            JOIN users u ON u.id = g.user_id
            LEFT JOIN generations r ON r.parent_id = g.id AND r.created_at >= NOW() - INTERVAL '7 days'
            WHERE g.created_at >= NOW() - INTERVAL '7 days'
            GROUP BY g.id, g.prompt, g.audio_url, u.id, u.username, g.plays_count, g.likes_count
            ORDER BY trending_score DESC
            LIMIT 100
        """)
        
        trending = [
            {
                "rank": idx + 1,
                "tape_id": row[0],
                "prompt": row[1],
                "audio_url": row[2],
                "creator_id": row[3],
                "creator_username": row[4],
                "plays_count": row[5],
                "likes_count": row[6],
                "remix_count": row[7],
                "trending_score": row[8],
            }
            for idx, row in enumerate(cursor.fetchall())
        ]
        
        cursor.execute("""
            INSERT INTO leaderboards (type, data, updated_at)
            VALUES ('trending_7d', %s, NOW())
            ON CONFLICT (type) DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at
        """, (json.dumps(trending),))
        
        conn.commit()
        
        print(f"✅ Updated trending leaderboard: {len(trending)} tapes")
        
    except Exception as e:
        print(f"❌ Error updating trending: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_top_creators():
    """Update top creators by followers."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT 
                u.id,
                u.username,
                u.avatar_url,
                u.bio,
                COUNT(DISTINCT f.follower_id) as followers_count,
                COUNT(DISTINCT g.id) as tapes_count,
                COALESCE(SUM(t.amount), 0) as total_earnings
            FROM users u
            LEFT JOIN follows f ON f.following_id = u.id
            LEFT JOIN generations g ON g.user_id = u.id
            LEFT JOIN transactions t ON t.user_id = u.id AND t.type IN ('remix_fee', 'royalty')
            GROUP BY u.id, u.username, u.avatar_url, u.bio
            HAVING COUNT(DISTINCT f.follower_id) > 0
            ORDER BY followers_count DESC, total_earnings DESC
            LIMIT 100
        """)
        
        top_creators = [
            {
                "rank": idx + 1,
                "user_id": row[0],
                "username": row[1],
                "avatar_url": row[2],
                "bio": row[3],
                "followers_count": row[4],
                "tapes_count": row[5],
                "total_earnings": float(row[6]),
            }
            for idx, row in enumerate(cursor.fetchall())
        ]
        
        cursor.execute("""
            INSERT INTO leaderboards (type, data, updated_at)
            VALUES ('top_creators', %s, NOW())
            ON CONFLICT (type) DO UPDATE SET
                data = EXCLUDED.data,
                updated_at = EXCLUDED.updated_at
        """, (json.dumps(top_creators),))
        
        conn.commit()
        
        print(f"✅ Updated top creators leaderboard: {len(top_creators)} creators")
        
    except Exception as e:
        print(f"❌ Error updating top creators: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def main():
    print("=" * 60)
    print(f"LEADERBOARD UPDATER - {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Update all leaderboards
    update_top_earners()
    update_most_remixed()
    update_trending()
    update_top_creators()
    
    print("=" * 60)
    print("✅ Leaderboard updater completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
