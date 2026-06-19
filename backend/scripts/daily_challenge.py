#!/usr/bin/env python3
"""
Daily Challenge Cron Job
Runs every day at 9am CET to create a new daily challenge.

Daily challenges encourage user engagement by providing:
- A themed prompt (e.g., "Summer Vibes", "Dark Phonk", "Chill Lofi")
- Bonus earnings (2x royalties for 24 hours)
- Leaderboard tracking
- Streak rewards
"""

import psycopg2
import os
from datetime import datetime, timedelta
import random

DATABASE_URL = os.getenv("DATABASE_URL")

# Challenge themes (rotates daily)
CHALLENGE_THEMES = [
    {"name": "Summer Vibes", "prompt": "Create a summer beach party track", "genre": "house"},
    {"name": "Dark Phonk", "prompt": "Create a dark aggressive phonk track", "genre": "phonk"},
    {"name": "Chill Lofi", "prompt": "Create a chill study lofi track", "genre": "lofi"},
    {"name": "Trap Energy", "prompt": "Create a hard trap banger", "genre": "trap"},
    {"name": "Ambient Journey", "prompt": "Create an ethereal ambient soundscape", "genre": "ambient"},
    {"name": "DnB Rush", "prompt": "Create a liquid drum and bass track", "genre": "dnb"},
    {"name": "Techno Warehouse", "prompt": "Create a dark industrial techno track", "genre": "techno"},
]


def create_daily_challenge():
    """Create a new daily challenge."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Select random theme
        theme = random.choice(CHALLENGE_THEMES)
        
        # Check if challenge already exists for today
        cursor.execute("""
            SELECT id FROM daily_challenges
            WHERE DATE(created_at) = CURRENT_DATE
        """)
        
        if cursor.fetchone():
            print(f"✅ Daily challenge already exists for {datetime.now().date()}")
            return
        
        # Create new challenge
        cursor.execute("""
            INSERT INTO daily_challenges (
                name, prompt, genre, bonus_multiplier, expires_at
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            theme["name"],
            theme["prompt"],
            theme["genre"],
            2.0,  # 2x earnings multiplier
            datetime.utcnow() + timedelta(hours=24)
        ))
        
        challenge_id = cursor.fetchone()[0]
        conn.commit()
        
        print(f"✅ Created daily challenge: {theme['name']} (ID: {challenge_id})")
        print(f"   Prompt: {theme['prompt']}")
        print(f"   Expires: {(datetime.utcnow() + timedelta(hours=24)).isoformat()}")
        
    except Exception as e:
        print(f"❌ Error creating daily challenge: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def update_user_streaks():
    """Update user streaks based on daily participation."""
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Get yesterday's challenge
        cursor.execute("""
            SELECT id FROM daily_challenges
            WHERE DATE(created_at) = CURRENT_DATE - INTERVAL '1 day'
        """)
        
        yesterday_challenge = cursor.fetchone()
        if not yesterday_challenge:
            print("ℹ️  No challenge from yesterday to process streaks")
            return
        
        challenge_id = yesterday_challenge[0]
        
        # Find users who participated yesterday
        cursor.execute("""
            SELECT DISTINCT user_id
            FROM generations
            WHERE challenge_id = %s
        """, (challenge_id,))
        
        participating_users = [row[0] for row in cursor.fetchall()]
        
        # Update streaks for participating users
        for user_id in participating_users:
            cursor.execute("""
                UPDATE users
                SET 
                    streak_days = streak_days + 1,
                    last_challenge_date = CURRENT_DATE
                WHERE id = %s
            """, (user_id,))
        
        # Reset streaks for users who didn't participate
        cursor.execute("""
            UPDATE users
            SET streak_days = 0
            WHERE last_challenge_date < CURRENT_DATE - INTERVAL '1 day'
            AND streak_days > 0
        """)
        
        conn.commit()
        
        print(f"✅ Updated streaks for {len(participating_users)} users")
        print(f"   Reset streaks for inactive users")
        
    except Exception as e:
        print(f"❌ Error updating streaks: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def send_challenge_notifications():
    """Send push notifications about new daily challenge."""
    # TODO: Integrate with push notification service (Firebase, OneSignal, etc.)
    print("ℹ️  Push notifications not yet implemented")


def main():
    print("=" * 60)
    print(f"DAILY CHALLENGE CRON - {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Create new challenge
    create_daily_challenge()
    
    # Update user streaks from yesterday
    update_user_streaks()
    
    # Send notifications
    send_challenge_notifications()
    
    print("=" * 60)
    print("✅ Daily challenge cron completed")
    print("=" * 60)


if __name__ == "__main__":
    main()
