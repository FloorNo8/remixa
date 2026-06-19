# Secrets Rotation Guide

## Overview

This guide covers rotating all secrets used in the Remixa application for security best practices.

## Secrets Inventory

### Backend (Fly.io)
- `DATABASE_URL` - PostgreSQL connection string
- `JWT_SECRET` - JWT token signing key
- `WEBHOOK_SECRET` - Webhook verification secret
- `STRIPE_SECRET_KEY` - Stripe API key
- `CLERK_SECRET_KEY` - Clerk authentication key
- `R2_ACCESS_KEY` - Cloudflare R2 access key
- `R2_SECRET_KEY` - Cloudflare R2 secret key
- `SENTRY_DSN` - Sentry error tracking DSN

### Frontend (Vercel)
- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` - Clerk public key
- `NEXT_PUBLIC_API_URL` - Backend API URL

### GitHub Actions
- `FLY_API_TOKEN` - Fly.io deployment token
- `VERCEL_TOKEN` - Vercel deployment token
- `VERCEL_ORG_ID` - Vercel organization ID
- `VERCEL_PROJECT_ID` - Vercel project ID
- `CODECOV_TOKEN` - Codecov upload token

## Rotation Schedule

| Secret Type | Rotation Frequency | Priority |
|-------------|-------------------|----------|
| JWT_SECRET | Every 90 days | High |
| WEBHOOK_SECRET | Every 90 days | High |
| API Keys (Stripe, Clerk) | When compromised | Critical |
| Database credentials | Every 180 days | Medium |
| Deployment tokens | Every 180 days | Medium |
| R2 credentials | Every 180 days | Medium |

## Rotation Procedures

### 1. JWT Secret Rotation

```bash
# Generate new secret
NEW_JWT_SECRET=$(openssl rand -hex 32)

# Update Fly.io
flyctl secrets set -a remixa-api JWT_SECRET="$NEW_JWT_SECRET"
flyctl secrets set -a remixa-api-staging JWT_SECRET="$NEW_JWT_SECRET"

# Update Vercel
vercel env add JWT_SECRET production
vercel env add JWT_SECRET preview

# Verify deployment
flyctl status -a remixa-api
```

**Important:** JWT rotation will invalidate all existing tokens. Plan for user re-authentication.

### 2. Webhook Secret Rotation

```bash
# Generate new secret
NEW_WEBHOOK_SECRET=$(openssl rand -hex 32)

# Update Fly.io
flyctl secrets set -a remixa-api WEBHOOK_SECRET="$NEW_WEBHOOK_SECRET"

# Update webhook providers (Stripe, Clerk, etc.)
# - Go to provider dashboard
# - Update webhook secret
# - Test webhook delivery
```

### 3. Stripe API Key Rotation

```bash
# 1. Generate new key in Stripe Dashboard
# 2. Update secrets
flyctl secrets set -a remixa-api STRIPE_SECRET_KEY="sk_live_..."
flyctl secrets set -a remixa-api-staging STRIPE_SECRET_KEY="sk_test_..."

# 3. Verify payment processing
curl -X POST https://api.remixa.eu/api/v1/billing/calculate-vat \
  -H "Content-Type: application/json" \
  -d '{"amount_eur": 10, "country_code": "DE"}'
```

### 4. Clerk Secret Key Rotation

```bash
# 1. Generate new key in Clerk Dashboard
# 2. Update secrets
flyctl secrets set -a remixa-api CLERK_SECRET_KEY="sk_..."

# Update frontend
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production

# 3. Test authentication
# - Login to app
# - Verify JWT validation
# - Check user session
```

### 5. Database Credentials Rotation

```bash
# For managed PostgreSQL (Neon/Supabase):
# 1. Create new database user
# 2. Grant permissions
# 3. Update connection string
flyctl secrets set -a remixa-api DATABASE_URL="postgresql://..."

# 4. Verify connectivity
flyctl ssh console -a remixa-api -C "python -c 'import psycopg2; psycopg2.connect(\"$DATABASE_URL\")'"

# 5. Remove old user after verification
```

### 6. R2 Credentials Rotation

```bash
# 1. Generate new R2 API token in Cloudflare Dashboard
# 2. Update secrets
flyctl secrets set -a remixa-api \
  R2_ACCESS_KEY="new_access_key" \
  R2_SECRET_KEY="new_secret_key"

# 3. Test upload
python backend/scripts/backup_db.py

# 4. Revoke old credentials in Cloudflare
```

### 7. Deployment Token Rotation

#### Fly.io Token

```bash
# 1. Generate new token
flyctl auth token

# 2. Update GitHub secret
# Go to: Settings > Secrets and variables > Actions
# Update: FLY_API_TOKEN

# 3. Test deployment
git commit --allow-empty -m "Test deployment"
git push origin main
```

#### Vercel Token

```bash
# 1. Generate new token in Vercel Dashboard
# Settings > Tokens > Create Token

# 2. Update GitHub secrets
# Update: VERCEL_TOKEN

# 3. Test deployment
vercel --token=$VERCEL_TOKEN
```

## Emergency Rotation (Compromised Secret)

If a secret is compromised, follow this procedure immediately:

### 1. Assess Impact
- Identify which secret was compromised
- Determine potential exposure scope
- Check logs for unauthorized access

### 2. Immediate Actions
```bash
# Rotate the compromised secret immediately
flyctl secrets set -a remixa-api SECRET_NAME="new_value"

# For critical secrets (database, API keys):
# - Revoke old credentials at provider
# - Monitor for suspicious activity
# - Review access logs
```

### 3. Post-Incident
- Document the incident
- Update rotation schedule
- Review security practices
- Notify affected users if necessary

## Verification Checklist

After rotating secrets, verify:

- [ ] Application starts successfully
- [ ] Database connections work
- [ ] Authentication flows work
- [ ] Payment processing works
- [ ] File uploads work (R2)
- [ ] Webhooks are received
- [ ] CI/CD pipelines pass
- [ ] Monitoring/logging works

## Automation

### Automated Rotation Script

```bash
#!/bin/bash
# scripts/rotate_secrets.sh

set -e

SECRET_TYPE=$1
ENVIRONMENT=${2:-production}

case $SECRET_TYPE in
  jwt)
    NEW_SECRET=$(openssl rand -hex 32)
    flyctl secrets set -a remixa-api JWT_SECRET="$NEW_SECRET"
    echo "✅ JWT secret rotated"
    ;;
  webhook)
    NEW_SECRET=$(openssl rand -hex 32)
    flyctl secrets set -a remixa-api WEBHOOK_SECRET="$NEW_SECRET"
    echo "✅ Webhook secret rotated"
    echo "⚠️  Update webhook providers manually"
    ;;
  *)
    echo "Usage: ./rotate_secrets.sh [jwt|webhook|stripe|clerk|database|r2] [production|staging]"
    exit 1
    ;;
esac
```

### Rotation Reminders

Set up calendar reminders:

```bash
# Add to crontab for monthly check
0 9 1 * * echo "🔐 Monthly secrets rotation check" | mail -s "Security Reminder" admin@remixa.eu
```

## Best Practices

1. **Never commit secrets to git**
   - Use `.env.example` for templates
   - Add `.env` to `.gitignore`

2. **Use secret management tools**
   - Fly.io secrets for backend
   - Vercel environment variables for frontend
   - GitHub secrets for CI/CD

3. **Principle of least privilege**
   - Create separate keys for different environments
   - Use read-only keys where possible

4. **Monitor secret usage**
   - Enable audit logs
   - Set up alerts for unusual access patterns

5. **Document everything**
   - Keep this guide updated
   - Document rotation dates
   - Track who has access

## Troubleshooting

### Secret not updating
```bash
# Force restart after secret update
flyctl apps restart remixa-api
```

### Database connection fails after rotation
```bash
# Check connection string format
flyctl ssh console -a remixa-api -C "env | grep DATABASE_URL"

# Test connection
flyctl ssh console -a remixa-api -C "python -c 'import psycopg2; psycopg2.connect(\"$DATABASE_URL\")'"
```

### Deployment fails after token rotation
```bash
# Verify token is set correctly
gh secret list

# Test token manually
flyctl auth token
vercel whoami --token=$VERCEL_TOKEN
```

## Contact

For security incidents or questions:
- Email: security@remixa.eu
- Slack: #security-alerts
- On-call: PagerDuty rotation
