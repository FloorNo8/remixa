"""
EU TikTok Sound Lab v2 - Discord Bot
Module 9: Community engagement, daily challenges, trending notifications
"""

import discord
from discord.ext import commands, tasks
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
import random
import asyncio

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Channel IDs (set these in .env)
TRENDING_CHANNEL_ID = int(os.getenv('DISCORD_TRENDING_CHANNEL', '0'))
DAILY_CHALLENGE_CHANNEL_ID = int(os.getenv('DISCORD_DAILY_CHALLENGE_CHANNEL', '0'))

# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db():
    """Get database connection"""
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )

# ============================================================================
# COMMANDS
# ============================================================================

@bot.command(name='trending')
async def trending(ctx):
    """
    Show top 5 trending tapes today
    Usage: /trending
    """
    
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT 
            g.id, g.prompt, g.audio_url, g.remix_count, g.earnings,
            u.username as creator
        FROM generations g
        JOIN users u ON g.user_id = u.id
        WHERE g.is_public = true 
          AND g.created_at > NOW() - INTERVAL '24 hours'
        ORDER BY g.remix_count DESC
        LIMIT 5
    """)
    
    tapes = cur.fetchall()
    cur.close()
    conn.close()
    
    if not tapes:
        await ctx.send("No trending tapes today yet. Be the first to create!")
        return
    
    embed = discord.Embed(
        title="🔥 Trending Tapes Today",
        description="Top 5 most remixed tracks in the last 24 hours",
        color=discord.Color.blue()
    )
    
    for i, tape in enumerate(tapes, 1):
        embed.add_field(
            name=f"#{i} {tape['prompt'][:50]}...",
            value=f"by @{tape['creator']} • {tape['remix_count']} remixes • €{tape['earnings']:.2f} earned\n[Listen]({tape['audio_url']})",
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='remix')
async def remix(ctx, generation_id: str):
    """
    Generate a remix in Discord
    Usage: /remix gen_abc123
    """
    
    await ctx.send(f"🎵 Generating remix of {generation_id}... This will take ~10 seconds.")
    
    # TODO: Call API to create remix
    # For now, mock response
    await asyncio.sleep(2)
    
    embed = discord.Embed(
        title="✅ Remix Complete!",
        description=f"Your remix of {generation_id} is ready",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="Listen",
        value=f"https://eu-sound-lab.com/tape/gen_new123",
        inline=False
    )
    
    embed.add_field(
        name="Cost",
        value="€0.10 (€0.07 to original creator)",
        inline=True
    )
    
    await ctx.send(embed=embed)

@bot.command(name='earnings')
async def earnings(ctx):
    """
    Show user's earnings
    Usage: /earnings
    """
    
    # TODO: Link Discord user to platform user
    # For now, mock response
    
    embed = discord.Embed(
        title="💰 Your Earnings",
        color=discord.Color.gold()
    )
    
    embed.add_field(name="Total Earned", value="€12.45", inline=True)
    embed.add_field(name="Pending Payout", value="€8.30", inline=True)
    embed.add_field(name="Total Remixes", value="23", inline=True)
    
    embed.add_field(
        name="Top Tape",
        value="'lofi beats for studying' - €4.20 earned",
        inline=False
    )
    
    embed.set_footer(text="View full dashboard at eu-sound-lab.com/earnings")
    
    await ctx.send(embed=embed)

@bot.command(name='challenge')
async def challenge(ctx):
    """
    Show today's daily challenge
    Usage: /challenge
    """
    
    conn = get_db()
    cur = conn.cursor()
    
    today = date.today()
    cur.execute("""
        SELECT prompt, winner_id, total_submissions
        FROM daily_challenges
        WHERE date = %s
    """, (today,))
    
    challenge = cur.fetchone()
    cur.close()
    conn.close()
    
    if not challenge:
        await ctx.send("No challenge today yet. Check back at 9am CET!")
        return
    
    embed = discord.Embed(
        title="🎯 Daily Challenge",
        description=challenge['prompt'],
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="Submissions",
        value=str(challenge['total_submissions']),
        inline=True
    )
    
    if challenge['winner_id']:
        embed.add_field(
            name="Winner",
            value="Announced at midnight!",
            inline=True
        )
    
    embed.set_footer(text="Create your entry at eu-sound-lab.com/challenge")
    
    await ctx.send(embed=embed)

@bot.command(name='leaderboard')
async def leaderboard(ctx, board_type: str = 'earnings'):
    """
    Show leaderboard
    Usage: /leaderboard [earnings|remixes|streaks]
    """
    
    if board_type not in ['earnings', 'remixes', 'streaks']:
        await ctx.send("Invalid leaderboard type. Use: earnings, remixes, or streaks")
        return
    
    conn = get_db()
    cur = conn.cursor()
    
    if board_type == 'earnings':
        cur.execute("SELECT * FROM leaderboard_earnings LIMIT 10")
        title = "💰 Top Earners"
        value_key = 'total_earned'
        value_format = "€{:.2f}"
    elif board_type == 'remixes':
        cur.execute("SELECT * FROM leaderboard_remixes LIMIT 10")
        title = "🔄 Most Remixed"
        value_key = 'total_remixes'
        value_format = "{} remixes"
    else:  # streaks
        cur.execute("SELECT * FROM leaderboard_streaks LIMIT 10")
        title = "🔥 Longest Streaks"
        value_key = 'streak_days'
        value_format = "{} days"
    
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    embed = discord.Embed(
        title=title,
        description="Top 10 this month",
        color=discord.Color.gold()
    )
    
    for i, row in enumerate(rows, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"#{i}"
        value = row[value_key]
        embed.add_field(
            name=f"{medal} @{row['username']}",
            value=value_format.format(value),
            inline=False
        )
    
    await ctx.send(embed=embed)

# ============================================================================
# BACKGROUND TASKS
# ============================================================================

@tasks.loop(hours=24)
async def post_daily_challenge():
    """
    Post daily challenge at 9am CET
    """
    
    # Wait until 9am CET
    now = datetime.now()
    if now.hour != 9:
        return
    
    channel = bot.get_channel(DAILY_CHALLENGE_CHANNEL_ID)
    if not channel:
        print("[DISCORD] Daily challenge channel not found")
        return
    
    # Generate random prompt
    prompts = [
        "Create a lofi track with rain sounds",
        "Make an upbeat house track for morning workouts",
        "Compose a chill ambient piece for meditation",
        "Generate a trap beat with heavy 808s",
        "Create a synthwave track inspired by 80s movies",
        "Make a jazz-influenced hip hop beat",
        "Compose a dreamy chillwave track",
        "Generate an energetic drum & bass track"
    ]
    
    prompt = random.choice(prompts)
    today = date.today()
    
    # Save to database
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO daily_challenges (date, prompt)
        VALUES (%s, %s)
        ON CONFLICT (date) DO NOTHING
    """, (today, prompt))
    conn.commit()
    cur.close()
    conn.close()
    
    # Post to Discord
    embed = discord.Embed(
        title="🎯 Daily Challenge",
        description=prompt,
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="How to Enter",
        value="1. Go to eu-sound-lab.com/challenge\n2. Create your track\n3. Submit before midnight CET",
        inline=False
    )
    
    embed.add_field(
        name="Prize",
        value="Winner gets featured + 5 bonus invites",
        inline=False
    )
    
    embed.set_footer(text="Good luck! 🎵")
    
    await channel.send("@everyone", embed=embed)
    print(f"[DISCORD] Posted daily challenge: {prompt}")

@tasks.loop(minutes=15)
async def check_trending_tapes():
    """
    Post to #trending when a tape gets >10 remixes
    """
    
    channel = bot.get_channel(TRENDING_CHANNEL_ID)
    if not channel:
        return
    
    conn = get_db()
    cur = conn.cursor()
    
    # Find tapes that just crossed 10 remixes
    cur.execute("""
        SELECT 
            g.id, g.prompt, g.audio_url, g.remix_count, g.earnings,
            u.username as creator
        FROM generations g
        JOIN users u ON g.user_id = u.id
        WHERE g.remix_count >= 10
          AND g.created_at > NOW() - INTERVAL '1 hour'
          AND g.is_public = true
        ORDER BY g.created_at DESC
        LIMIT 5
    """)
    
    tapes = cur.fetchall()
    cur.close()
    conn.close()
    
    for tape in tapes:
        embed = discord.Embed(
            title="🔥 Trending Alert!",
            description=f"**{tape['prompt'][:100]}**",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="Creator", value=f"@{tape['creator']}", inline=True)
        embed.add_field(name="Remixes", value=str(tape['remix_count']), inline=True)
        embed.add_field(name="Earned", value=f"€{tape['earnings']:.2f}", inline=True)
        
        embed.add_field(
            name="Listen & Remix",
            value=f"https://eu-sound-lab.com/tape/{tape['id']}",
            inline=False
        )
        
        await channel.send(embed=embed)
        print(f"[DISCORD] Posted trending tape: {tape['id']}")

# ============================================================================
# EVENTS
# ============================================================================

@bot.event
async def on_ready():
    """Bot startup"""
    print(f'[DISCORD] Bot logged in as {bot.user}')
    
    # Start background tasks
    post_daily_challenge.start()
    check_trending_tapes.start()
    
    # Set status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.listening,
            name="AI-generated beats 🎵"
        )
    )

@bot.event
async def on_command_error(ctx, error):
    """Error handler"""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found. Try /trending, /remix, /earnings, /challenge, or /leaderboard")
    else:
        await ctx.send(f"Error: {str(error)}")
        print(f"[DISCORD] Error: {error}")

# ============================================================================
# RUN BOT
# ============================================================================

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN not set")
        exit(1)
    
    bot.run(token)
