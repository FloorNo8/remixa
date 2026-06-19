# EU TikTok Sound Lab v2 - Social Remix Platform

**AI Music Generator with Remix Mechanics & Automatic Royalties**

Generate 15-second instrumental tracks, remix others' work, and earn royalties automatically. Full EU compliance (GDPR, AI Act, DSA, VAT MOSS).

---

## 🆕 What's New in v2

### Social Features
- **Remix Mechanics**: Layer vocals, lyrics, or visuals on existing tracks
- **Automatic Royalties**: Creators earn €0.07 per remix (€0.05 + €0.02 for grandparent)
- **Explore Feed**: Discover trending tracks sorted by remixes or earnings
- **Remix Chain Visualization**: See the full lineage of any track

### Gamification
- **Daily Streaks**: Generate daily to maintain your streak
- **Leaderboards**: Top earners, most remixed, longest streaks
- **Daily Challenges**: Community prompts with prizes
- **Invite System**: Waitlist with invite codes

### Community
- **Discord Bot**: `/trending`, `/remix`, `/earnings`, `/challenge` commands
- **Content Reporting**: DSA-compliant reporting system
- **Community Notes**: Collaborative context on tracks

### Monetization
- **Balance Top-ups**: Add €10 credits for remixing
- **Stripe Connect Payouts**: Withdraw earnings (min €20)
- **License Fees**: €0.10 per remix (€0.03 platform, €0.07 creator)

---

## 🏗️ Architecture Changes

```
┌─────────────────────────────────────────────────────────────┐
│                EU TikTok Sound Lab v2                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Next.js    │─────▶│  FastAPI     │─────▶│ Replicate │ │
│  │   Frontend   │      │   Backend    │      │  MusicGen │ │
│  │              │      │              │      │           │ │
│  │  - Explore   │      │  - /explore  │      │  <10s gen │ │
│  │  - Remix UI  │      │  - /remix    │      │           │ │
│  │  - Earnings  │      │  - /earnings │      └───────────┘ │
│  └──────────────┘      └──────────────┘                     │
│         │                      │                             │
│         │                      │                             │
│  ┌──────▼──────┐      ┌───────▼──────┐      ┌───────────┐ │
│  │   Stripe    │      │  PostgreSQL  │      │ R2 Storage│ │
│  │  + Connect  │      │   + Views    │      │ (Audio)   │ │
│  └─────────────┘      └──────────────┘      └───────────┘ │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Discord Bot (24/7)                       │  │
│  │  - Daily challenges (9am CET)                        │  │
│  │  - Trending notifications (>10 remixes)              │  │
│  │  - Commands: /trending, /remix, /earnings            │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### 1. Database Migration

```bash
# Run v2 migration
psql -U eu_sound_lab_user -d eu_sound_lab -f migrations/002_v2_social_features.sql

# Verify tables
psql -U eu_sound_lab_user -d eu_sound_lab -c "\dt"
# Should show: license_transactions, voice_models, daily_challenges, reports, invites, etc.
```

### 2. Environment Variables

Add to `.env`:

```bash
# Replicate (for MusicGen inference)
REPLICATE_API_TOKEN=r8_...

# Cloudflare R2 (for audio storage)
R2_ACCESS_KEY=...
R2_SECRET=...
R2_BUCKET=eu-sound-lab-audio
R2_ENDPOINT=https://...r2.cloudflarestorage.com

# Stripe Connect (for payouts)
STRIPE_CONNECT_CLIENT_ID=ca_...

# Discord Bot
DISCORD_BOT_TOKEN=...
DISCORD_TRENDING_CHANNEL=123456789
DISCORD_DAILY_CHALLENGE_CHANNEL=123456789

# Frontend
NEXT_PUBLIC_SITE_URL=https://eu-sound-lab.com
```

### 3. Start Services

```bash
# Backend
cd backend/eu-sound-lab
uvicorn main:app --reload --port 8000

# Discord Bot (separate process)
python discord_bot.py

# Frontend
cd web/eu-sound-lab
npm run dev
```

### 4. Seed Voice Models

```bash
# Upload voice previews to R2
aws s3 cp voices/soprano.mp3 s3://eu-sound-lab-audio/voices/ --endpoint-url=...

# Verify in database
psql -c "SELECT name, license_type FROM voice_models;"
```

---

## 🎵 API Endpoints (v2)

### Explore & Discovery

```bash
GET /api/explore?sort=trending&limit=20&offset=0
# Returns: [{id, prompt, audio_url, waveform_url, creator_username, remix_count, earnings, parent_preview}]

GET /api/generation/{id}
# Returns: Full generation with remix_chain, C2PA manifest
```

### Remix

```bash
POST /api/generation/{id}/remix
{
  "layer_type": "voice",
  "prompt": "add jazz vocals",
  "voice_model_id": "uuid"
}
# Returns: {generation_id, status: "processing"}
```

### Earnings

```bash
GET /api/earnings
# Returns: {total_earned, pending_payout, total_remixes, top_tapes[], recent_transactions[]}

POST /api/payout/request
# Requires: pending_payout >= €20
# Returns: {payout_id, amount, status}
```

### Stripe

```bash
POST /api/stripe/topup
{
  "amount_eur": 10.0
}
# Returns: {session_id, url} (Stripe Checkout)

POST /api/stripe/connect
# Returns: {account_id, onboarding_url}

POST /api/stripe/webhook
# Handles: checkout.session.completed, transfer.created
```

### Leaderboards

```bash
GET /api/leaderboard/earnings
GET /api/leaderboard/remixes
GET /api/leaderboard/streaks
# Returns: [{username, value, rank}] (top 20)
```

### Reporting (DSA)

```bash
POST /api/report
{
  "generation_id": "uuid",
  "reason": "copyright",
  "details": "..."
}
# Returns: {report_id, status: "received"}
```

### Invites

```bash
POST /api/invite/generate
# Returns: {code, invites_remaining}

POST /api/invite/redeem
{
  "code": "ABC12345"
}
# Returns: {status: "activated"}

GET /api/waitlist/status
# Returns: {status, position, message}
```

---

## 💰 Royalty Distribution

### 2-Level Chain (Parent → Child)
```
User B remixes User A's track
├─ User B pays: €0.10
├─ Platform fee: €0.03
└─ User A earns: €0.07
```

### 3-Level Chain (Grandparent → Parent → Child)
```
User C remixes User B's track (which remixed User A's)
├─ User C pays: €0.10
├─ Platform fee: €0.03
├─ User B earns: €0.05
└─ User A earns: €0.02
```

**Implementation**: Stored procedure `distribute_remix_royalties()` in database.

---

## 🎮 Discord Bot Commands

### User Commands

```
/trending
# Shows top 5 trending tapes today

/remix gen_abc123
# Generates a remix in Discord (returns link)

/earnings
# Shows your total earned, pending payout, top tapes

/challenge
# Shows today's daily challenge prompt

/leaderboard [earnings|remixes|streaks]
# Shows top 10 users
```

### Admin Commands (TODO)

```
/announce <message>
# Post announcement to #announcements

/ban <user_id>
# Ban user from platform

/feature <generation_id>
# Feature a tape in #featured
```

---

## 🔄 Background Jobs (Cron)

### Daily (9am CET)
```bash
# Create daily challenge
python -c "from discord_bot import post_daily_challenge; post_daily_challenge()"
```

### Hourly
```bash
# Process pending payouts
psql -c "SELECT process_pending_payouts();"
```

### Every 15 minutes
```bash
# Check for trending tapes (>10 remixes)
# Handled by Discord bot background task
```

### Daily (midnight)
```bash
# Update leaderboards
psql -c "REFRESH MATERIALIZED VIEW leaderboard_earnings;"
psql -c "REFRESH MATERIALIZED VIEW leaderboard_remixes;"
psql -c "REFRESH MATERIALIZED VIEW leaderboard_streaks;"

# Send streak notifications
# TODO: Implement email/push notifications
```

---

## 🚀 Deployment (Fly.io)

### 1. Install Fly CLI

```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### 2. Create Apps

```bash
# Backend API
fly launch --name eu-sound-lab-api --region fra
fly secrets set DATABASE_URL=... STRIPE_SECRET_KEY=... REPLICATE_API_TOKEN=...

# Discord Bot
fly launch --name eu-sound-lab-bot --region fra
fly secrets set DISCORD_BOT_TOKEN=... DATABASE_URL=...

# Frontend
cd web/eu-sound-lab
fly launch --name eu-sound-lab-web --region fra
fly secrets set NEXT_PUBLIC_API_URL=https://eu-sound-lab-api.fly.dev
```

### 3. Deploy

```bash
# Backend
cd backend/eu-sound-lab
fly deploy

# Bot
fly deploy -c fly.bot.toml

# Frontend
cd web/eu-sound-lab
fly deploy
```

### 4. Set Up Cron (Fly Machines)

```toml
# fly.toml
[processes]
  web = "uvicorn main:app --host 0.0.0.0 --port 8000"
  bot = "python discord_bot.py"
  cron = "python cron_jobs.py"
```

---

## 🧪 Testing

### Unit Tests

```bash
pytest tests/test_remix.py -v
pytest tests/test_royalties.py -v
pytest tests/test_stripe.py -v
```

### Integration Tests

```bash
# Test full remix flow
curl -X POST http://localhost:8000/api/generation/gen_123/remix \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"layer_type":"voice","prompt":"add vocals"}'

# Test payout
curl -X POST http://localhost:8000/api/payout/request \
  -H "Authorization: Bearer $TOKEN"
```

### Load Testing

```bash
# 100 concurrent remixes
ab -n 100 -c 10 -H "Authorization: Bearer $TOKEN" \
  -p remix.json \
  http://localhost:8000/api/generation/gen_123/remix
```

---

## 📊 Monitoring

### Key Metrics

- **Remix Rate**: Remixes per day
- **Earnings Distribution**: Gini coefficient
- **Payout Success Rate**: % of successful transfers
- **Generation Time**: p50, p95, p99
- **Discord Engagement**: Commands per day

### Dashboards

```bash
# Grafana queries (PostgreSQL)
SELECT DATE(created_at), COUNT(*) 
FROM license_transactions 
GROUP BY DATE(created_at);

SELECT AVG(generation_time_ms) 
FROM generations 
WHERE created_at > NOW() - INTERVAL '1 hour';
```

---

## 🔒 Security

### Rate Limiting

```python
# 100 remixes per hour per user
@limiter.limit("100/hour")
async def create_remix(...):
    ...
```

### Balance Validation

```sql
-- Prevent negative balances
ALTER TABLE user_balances 
ADD CONSTRAINT balance_non_negative 
CHECK (balance >= 0);
```

### Payout Fraud Prevention

- Minimum €20 payout
- Stripe Connect verification required
- 2-day processing delay
- Manual review for >€100

---

## 📝 Launch Checklist

### Pre-Launch (Week 1)

- [ ] Upload 5 voice models to R2
- [ ] Test Stripe Connect onboarding flow
- [ ] Validate C2PA on 10 test files
- [ ] Set up Discord server with channels
- [ ] Create 100 seed tapes for explore feed
- [ ] Test remix chain with 3+ levels
- [ ] Verify VAT MOSS export includes license fees

### Launch Day

- [ ] Deploy to Fly.io (2 regions: fra, ams)
- [ ] Start Discord bot
- [ ] Enable Stripe webhooks
- [ ] Post launch announcement
- [ ] Monitor error logs
- [ ] Activate waitlist (first 100 users)

### Post-Launch (Week 1)

- [ ] Daily challenge at 9am CET
- [ ] Monitor remix rate
- [ ] Process first payouts
- [ ] Collect user feedback
- [ ] Fix critical bugs
- [ ] Update leaderboards

---

## 🐛 Known Issues

1. **Replicate Latency**: Generation can take 10-15s during peak hours
   - **Fix**: Migrate to RunPod for dedicated GPU
   
2. **C2PA Verification**: Some MP3 players don't display C2PA
   - **Fix**: Add visible watermark in waveform

3. **Discord Rate Limits**: Bot can hit rate limits with >100 commands/min
   - **Fix**: Implement command queue

4. **Payout Delays**: Stripe Connect transfers take 2-7 days
   - **Fix**: Add instant payout option (1% fee)

---

## 📚 References

- [Replicate MusicGen API](https://replicate.com/meta/musicgen)
- [Stripe Connect](https://stripe.com/docs/connect)
- [Discord.py](https://discordpy.readthedocs.io/)
- [Fly.io Deployment](https://fly.io/docs/)
- [C2PA Specification](https://c2pa.org/specifications/)

---

## 🤝 Support

- **Email**: support@eu-sound-lab.com
- **Discord**: https://discord.gg/eu-sound-lab
- **Docs**: https://docs.eu-sound-lab.com

---

**Built with ❤️ in the EU**  
Floor No 8 SRL • Bucharest, Romania • VAT: DK12345678
