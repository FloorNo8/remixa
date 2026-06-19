# Phase 4: Infrastructure - Complete ✅

Production-grade infrastructure with CI/CD, backups, staging, and security hardening.

## 📦 Deliverables

### ✅ CI/CD Pipeline

**Files Created:**
- `.github/workflows/test.yml` - Automated testing on every push
- `.github/workflows/deploy.yml` - Automated deployment to production/staging

**Features:**
- Backend tests with PostgreSQL service
- Frontend linting and build verification
- Security scanning with Trivy
- Code coverage reporting to Codecov
- Automatic deployment on main branch merge
- Manual deployment workflow for staging

**Status:** Ready to use (requires GitHub secrets configuration)

---

### ✅ Database Backups

**Files Created:**
- `backend/scripts/backup_db.py` - Daily backup script
- `backend/scripts/restore_db.py` - Restore utility

**Features:**
- Automated daily backups to Cloudflare R2
- 30-day retention policy
- Compressed PostgreSQL dumps
- Automatic cleanup of old backups
- Restore with confirmation prompt
- List available backups

**Usage:**
```bash
# Manual backup
python backend/scripts/backup_db.py

# List backups
python backend/scripts/restore_db.py list

# Restore from backup
python backend/scripts/restore_db.py db/20260619-020000.sql.gz
```

**Status:** Scripts ready (requires R2 bucket setup and cron configuration)

---

### ✅ Staging Environment

**Files Created:**
- `backend/fly.staging.toml` - Staging configuration

**Configuration:**
- Separate app: `remixa-api-staging`
- Debug logging enabled
- Mirrors production setup
- Auto-scaling enabled

**Status:** Configuration ready (requires Fly.io app creation)

---

### ✅ Security Hardening

**Files Created:**
- `backend/rbac.py` - Role-based access control
- `backend/auth_rate_limit.py` - Rate limiting module
- `backend/RBAC_USAGE.md` - RBAC documentation
- `backend/SECRETS_ROTATION.md` - Security procedures
- `frontend/next.config.js` - Updated with CSP headers

**Features:**

#### RBAC (Role-Based Access Control)
- 4 roles: USER, CREATOR, MODERATOR, ADMIN
- Role hierarchy with permission inheritance
- Decorators: `@require_role()`, `@require_any_role()`, `@require_owner_or_role()`
- Applied to sensitive endpoints

#### Rate Limiting
- Authentication endpoints: 5 requests/minute
- API endpoints: 100 requests/minute
- Generation endpoints: 10 requests/minute
- Upload endpoints: 20 requests/minute
- Automatic 429 responses with retry-after

#### Security Headers
- Content Security Policy (CSP)
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection
- Referrer-Policy
- Permissions-Policy

**Status:** Implemented and documented

---

### ✅ Deployment Automation

**Files Created:**
- `scripts/deploy.sh` - Unified deployment script

**Features:**
- Runs tests before deployment
- Deploys backend to Fly.io
- Deploys frontend to Vercel
- Runs database migrations
- Health checks after deployment
- Supports staging and production

**Usage:**
```bash
# Deploy to staging
./scripts/deploy.sh staging

# Deploy to production
./scripts/deploy.sh production
```

**Status:** Ready to use (requires Fly.io and Vercel CLI setup)

---

## 🚀 Next Steps (User Actions Required)

### 1. Configure GitHub Secrets

Go to: `Settings > Secrets and variables > Actions`

Add the following secrets:

```bash
# Fly.io
FLY_API_TOKEN=<your_fly_token>

# Vercel
VERCEL_TOKEN=<your_vercel_token>
VERCEL_ORG_ID=<your_org_id>
VERCEL_PROJECT_ID=<your_project_id>

# Codecov (optional)
CODECOV_TOKEN=<your_codecov_token>

# Clerk (for frontend build)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=<your_clerk_key>
```

**Get tokens:**
```bash
# Fly.io token
flyctl auth token

# Vercel token
# Go to: https://vercel.com/account/tokens

# Vercel IDs
vercel link
cat .vercel/project.json
```

---

### 2. Set Up Staging Environment

```bash
# Create staging app
flyctl apps create remixa-api-staging

# Create staging database
flyctl postgres create --name remixa-db-staging

# Attach database
flyctl postgres attach remixa-db-staging -a remixa-api-staging

# Set secrets
flyctl secrets set -a remixa-api-staging \
  STRIPE_SECRET_KEY="sk_test_..." \
  CLERK_SECRET_KEY="..." \
  R2_BUCKET="remixa-staging" \
  R2_ENDPOINT="..." \
  R2_ACCESS_KEY="..." \
  R2_SECRET_KEY="..." \
  JWT_SECRET="$(openssl rand -hex 32)" \
  WEBHOOK_SECRET="$(openssl rand -hex 32)"

# Deploy
cd backend
flyctl deploy --app remixa-api-staging --config fly.staging.toml
```

**Frontend staging:**
```bash
cd frontend
vercel --prod --scope=floorno8 --name=remixa-staging
```

---

### 3. Configure Database Backups

**Option A: Fly.io Scheduled Machine**
```bash
# Create scheduled backup machine
flyctl machine run \
  --schedule "0 2 * * *" \
  --app remixa-api \
  python scripts/backup_db.py
```

**Option B: GitHub Actions (Recommended)**

Create `.github/workflows/backup.yml`:
```yaml
name: Database Backup
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: |
          flyctl ssh console -a remixa-api -C "python scripts/backup_db.py"
        env:
          FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
```

---

### 4. Test Backup/Restore

```bash
# Run manual backup
python backend/scripts/backup_db.py

# List backups
python backend/scripts/restore_db.py list

# Test restore (use staging database!)
python backend/scripts/restore_db.py db/YYYYMMDD-HHMMSS.sql.gz
```

---

### 5. Rotate Secrets

Follow the guide in `backend/SECRETS_ROTATION.md`:

```bash
# Generate new secrets
NEW_JWT_SECRET=$(openssl rand -hex 32)
NEW_WEBHOOK_SECRET=$(openssl rand -hex 32)

# Update production
flyctl secrets set -a remixa-api \
  JWT_SECRET="$NEW_JWT_SECRET" \
  WEBHOOK_SECRET="$NEW_WEBHOOK_SECRET"

# Update staging
flyctl secrets set -a remixa-api-staging \
  JWT_SECRET="$NEW_JWT_SECRET" \
  WEBHOOK_SECRET="$NEW_WEBHOOK_SECRET"
```

**Schedule rotation reminders:**
- JWT/Webhook secrets: Every 90 days
- Database credentials: Every 180 days
- API keys: When compromised

---

### 6. Verify CI/CD Pipeline

```bash
# Push to trigger CI
git add .
git commit -m "feat: add Phase 4 infrastructure"
git push origin main

# Check GitHub Actions
# Go to: https://github.com/your-repo/actions

# Verify:
# ✅ Tests pass
# ✅ Security scan completes
# ✅ Deployment succeeds
# ✅ Health checks pass
```

---

## 📊 Acceptance Criteria

### ✅ Completed
- [x] CI/CD workflows created
- [x] Backup scripts implemented
- [x] Restore procedure documented
- [x] Staging configuration ready
- [x] RBAC system implemented
- [x] Rate limiting added
- [x] CSP headers configured
- [x] Deployment script created
- [x] Documentation complete

### ⏳ Requires User Action
- [ ] GitHub secrets configured
- [ ] Staging environment deployed
- [ ] Backup cron job scheduled
- [ ] Backup/restore tested
- [ ] Production secrets rotated
- [ ] CI/CD pipeline verified

---

## 🔒 Security Checklist

- [x] RBAC implemented with role hierarchy
- [x] Rate limiting on all endpoints
- [x] CSP headers prevent XSS
- [x] Secrets rotation procedures documented
- [x] No secrets in code
- [ ] All secrets moved to Fly.io/Vercel (user action)
- [ ] Secrets rotated (user action)
- [ ] 2FA enabled on all accounts (user action)

---

## 📚 Documentation

- `backend/RBAC_USAGE.md` - How to use RBAC decorators
- `backend/SECRETS_ROTATION.md` - Secret rotation procedures
- `backend/DEPLOYMENT_GUIDE.md` - Deployment instructions
- `backend/HARDENING_CHECKLIST.md` - Security hardening guide

---

## 🎯 Quick Start

### Deploy to Production
```bash
# 1. Configure secrets (see step 1 above)
# 2. Run deployment
./scripts/deploy.sh production
```

### Deploy to Staging
```bash
# 1. Set up staging environment (see step 2 above)
# 2. Run deployment
./scripts/deploy.sh staging
```

### Run Backup
```bash
python backend/scripts/backup_db.py
```

### Restore from Backup
```bash
python backend/scripts/restore_db.py list
python backend/scripts/restore_db.py db/20260619-020000.sql.gz
```

---

## 🐛 Troubleshooting

### CI/CD fails
- Check GitHub secrets are set correctly
- Verify Fly.io and Vercel tokens are valid
- Check logs in GitHub Actions tab

### Backup fails
- Verify R2 credentials are set
- Check R2 bucket exists
- Ensure `pg_dump` is installed

### Deployment fails
- Run tests locally first: `cd backend && pytest`
- Check Fly.io app status: `flyctl status -a remixa-api`
- Verify secrets are set: `flyctl secrets list -a remixa-api`

### Rate limiting too strict
- Adjust limits in `backend/auth_rate_limit.py`
- Redeploy: `flyctl deploy -a remixa-api`

---

## 📞 Support

- Documentation: See files in `backend/` directory
- Issues: GitHub Issues
- Security: security@remixa.eu

---

**Phase 4 Complete! 🎉**

All infrastructure code is ready. Follow the "Next Steps" section to complete the setup.
