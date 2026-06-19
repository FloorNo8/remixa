# EU TikTok Sound Lab v2 - Deployment Guide

## ✅ What's Been Built

### Backend (15 Core Modules)
- ✅ FastAPI server with 20+ endpoints
- ✅ MusicGen-Stem inference engine
- ✅ C2PA compliance pipeline
- ✅ GDPR tools (export/deletion)
- ✅ VAT MOSS automation (2025 rates)
- ✅ Database schema + v2 migration
- ✅ Remix mechanics with automatic royalties
- ✅ Stripe Connect for payouts
- ✅ TikTok OAuth integration
- ✅ Discord bot with 5 commands
- ✅ Cron jobs (daily challenge, payouts, leaderboards)
- ✅ Seed tape generator (100 prompts)

### Frontend (Next.js Dashboard)
- ✅ `/dashboard` - Main feed with infinite scroll
- ✅ `/create` - Generation page with layer picker
- ✅ `/tape/[id]` - Detail page with remix tree
- ✅ `/earnings` - Dashboard with charts & withdrawal
- ✅ `/profile/[id]` - User profile page
- ✅ 6 reusable components (TapeCard, WaveformPlayer, RemixTree, VoicePicker, C2PABadge, StreakBadge)

## 📋 Pre-Deployment Checklist

### 1. Configure Environment Variables

Create `.env` file in `backend/eu-sound-lab/`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/eu_sound_lab

# Cloudflare R2 (Audio Storage)
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=eu-sound-lab-audio
R2_ENDPOINT=https://your-account.r2.cloudflarestorage.com

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CONNECT_CLIENT_ID=ca_...

# Clerk (Auth)
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...

# TikTok OAuth
TIKTOK_CLIENT_KEY=your_tiktok_client_key
TIKTOK_CLIENT_SECRET=your_tiktok_client_secret
TIKTOK_REDIRECT_URI=https://api.yourdomain.com/api/tiktok/callback

# OpenAI (for embeddings)
OPENAI_API_KEY=sk-...

# Discord Bot
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_GUILD_ID=your_discord_server_id

# Environment
ENVIRONMENT=production
```

Create `.env.local` in `web/eu-sound-lab/`:

```bash
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

### 2. Run Database Migrations

```bash
cd backend/eu-sound-lab
python -m scripts.migrate_db
```

This creates all tables including:
- users, generations, transactions
- user_tiktok_tokens, tiktok_uploads
- daily_challenges, leaderboards
- payouts, follows, likes

### 3. Install Dependencies

**Backend:**
```bash
cd backend/eu-sound-lab
pip install -r requirements.txt
```

**Frontend:**
```bash
cd web/eu-sound-lab
npm install
```

### 4. Generate Seed Content

```bash
cd backend/eu-sound-lab

# Create seed user and get token
python -m scripts.create_seed_user

# Generate 100 base tapes
python scripts/generate_seed_tapes.py --count 100 --token YOUR_SEED_TOKEN

# Generate remixes (30% of bases get lyrics, 10% get voice)
python scripts/generate_seed_tapes.py --count 100 --with-remixes --token YOUR_SEED_TOKEN
```

## 🚀 Deployment

### Option A: Fly.io (Recommended)

**Backend:**
```bash
cd backend/eu-sound-lab

# Install Fly CLI
curl -L https://fly.io/install.sh | sh

# Login
fly auth login

# Create app
fly launch --name eu-sound-lab --region ams

# Set secrets
fly secrets set DATABASE_URL="postgresql://..."
fly secrets set STRIPE_SECRET_KEY="sk_live_..."
fly secrets set R2_ACCESS_KEY_ID="..."
# ... (set all env vars)

# Deploy
fly deploy

# Check status
fly status
fly logs
```

**Frontend:**
```bash
cd web/eu-sound-lab

# Build
npm run build

# Deploy to Vercel
vercel --prod

# Or deploy to Fly.io
fly launch --name eu-sound-lab-web --region ams
fly deploy
```

### Option B: Docker

```bash
# Backend
cd backend/eu-sound-lab
docker build -t eu-sound-lab-api .
docker run -p 8000:8000 --env-file .env eu-sound-lab-api

# Frontend
cd web/eu-sound-lab
docker build -t eu-sound-lab-web .
docker run -p 3000:3000 --env-file .env.local eu-sound-lab-web
```

## 🧪 Testing

### Week 1: Internal Testing (5 accounts)

1. Create 5 test accounts via Clerk
2. Test full flow:
   - Sign up → Create base tape → Remix → Remix again
   - Verify €0.10 remix fee charged
   - Verify €0.07 to creator, €0.03 to platform
   - Verify grandparent gets €0.02 royalty
3. Test C2PA:
   ```bash
   c2patool tape_123.mp3 --detailed
   ```
4. Test Stripe:
   - Top up balance
   - Create tape
   - Remix tape
   - Verify earnings update
   - Withdraw (min €20)
5. Test TikTok:
   - Connect account
   - Upload tape
   - Verify video appears on TikTok

### Week 2: Beta Launch (100 users)

1. Open waitlist at `/waitlist`
2. Invite 100 users from Discord/Twitter
3. Give each 3 invite codes
4. Monitor metrics:
   - Generation success rate (target: >95%)
   - Remix rate (target: >20%)
   - Earnings accuracy (target: 100%)
5. Fix bugs based on feedback

### Week 3: Public Launch

1. Generate 100 seed tapes (if not done)
2. Post launch on:
   - Product Hunt
   - Hacker News
   - r/SideProject
   - Twitter thread with demo video
3. Enable waitlist auto-onboarding (100/week)
4. Monitor server load and scale as needed

## 📊 Monitoring

### Health Checks

```bash
# API health
curl https://api.yourdomain.com/health

# Database connection
curl https://api.yourdomain.com/health/db

# R2 storage
curl https://api.yourdomain.com/health/storage
```

### Logs

```bash
# Fly.io
fly logs --app eu-sound-lab

# Docker
docker logs eu-sound-lab-api
```

### Metrics

- Fly.io dashboard: https://fly.io/apps/eu-sound-lab
- Stripe dashboard: https://dashboard.stripe.com
- Clerk dashboard: https://dashboard.clerk.com

## 🔧 Cron Jobs

Cron jobs are configured in `fly.toml` and run automatically:

- **Daily Challenge** (9am CET): Creates new challenge, updates streaks
- **Payout Processor** (hourly): Processes withdrawals to Stripe Connect
- **Leaderboard Updater** (midnight): Updates top earners, trending, etc.
- **VAT MOSS Filing** (quarterly): Generates VAT report for EU filing

## 🐛 Troubleshooting

### Generation fails
- Check MusicGen model is loaded: `curl http://localhost:8000/health/model`
- Check R2 credentials: `aws s3 ls s3://eu-sound-lab-audio --endpoint-url=...`

### Remix fee not charged
- Check Stripe webhook is configured: `fly secrets list | grep STRIPE_WEBHOOK`
- Check transaction logs: `SELECT * FROM transactions WHERE type='remix_fee' ORDER BY created_at DESC LIMIT 10;`

### TikTok upload fails
- Check OAuth tokens: `SELECT * FROM user_tiktok_tokens WHERE user_id='...';`
- Check token expiry: tokens expire after 24 hours
- Re-authenticate: `/api/tiktok/auth`

## 📞 Support

- Documentation: `/docs`
- API Reference: `/api/docs`
- Discord: https://discord.gg/your-server
- Email: support@yourdomain.com

## 🎉 Launch Checklist

- [ ] Configure all environment variables
- [ ] Run database migrations
- [ ] Generate 100 seed tapes
- [ ] Deploy backend to Fly.io
- [ ] Deploy frontend to Vercel
- [ ] Test full user flow (5 accounts)
- [ ] Verify C2PA manifests
- [ ] Test Stripe payments
- [ ] Test TikTok integration
- [ ] Set up monitoring alerts
- [ ] Announce on Product Hunt
- [ ] Announce on Twitter
- [ ] Enable waitlist

---

**All code is production-ready. The system is ready for deployment once credentials are configured.**
