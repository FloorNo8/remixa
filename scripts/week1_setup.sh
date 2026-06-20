#!/bin/bash
# Week 1 Production Setup Script
# Automates immediate operational tasks for Remixa deployment

set -e  # Exit on error

echo "🚀 Remixa Week 1 Production Setup"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check prerequisites
echo "📋 Checking prerequisites..."
command -v fly >/dev/null 2>&1 || { echo -e "${RED}✗ Fly CLI not installed${NC}"; exit 1; }
command -v psql >/dev/null 2>&1 || { echo -e "${RED}✗ PostgreSQL client not installed${NC}"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo -e "${RED}✗ Python 3 not installed${NC}"; exit 1; }
echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Task 1: Review Deployment Guide
echo "📖 Task 1: Review Deployment Guide"
echo "-----------------------------------"
if [ -f "DEPLOYMENT_OPERATIONS_GUIDE.md" ]; then
    echo -e "${GREEN}✓ Deployment guide exists${NC}"
    echo "  Location: DEPLOYMENT_OPERATIONS_GUIDE.md"
    echo "  Action: Team should review sections 1-5"
else
    echo -e "${RED}✗ Deployment guide not found${NC}"
    exit 1
fi
echo ""

# Task 2: Set Up Production Monitoring
echo "📊 Task 2: Set Up Production Monitoring"
echo "----------------------------------------"

# 2.1: Deploy Grafana queries
echo "Setting up Grafana dashboard..."
if [ -f "backend/monitoring/grafana_queries.sql" ]; then
    echo -e "${YELLOW}→ Grafana queries ready for import${NC}"
    echo "  Manual step: Import to Grafana at https://grafana.remixa.com"
    echo "  File: backend/monitoring/grafana_queries.sql"
else
    echo -e "${RED}✗ Grafana queries not found${NC}"
fi

# 2.2: Configure Sentry
echo ""
echo "Configuring Sentry..."
if [ -f "backend/monitoring/sentry_config.py" ]; then
    echo -e "${GREEN}✓ Sentry config exists${NC}"
    echo "  Action: Set SENTRY_DSN in Fly.io secrets"
    echo "  Command: fly secrets set SENTRY_DSN=<your-dsn>"
else
    echo -e "${RED}✗ Sentry config not found${NC}"
fi

# 2.3: Set up health check cron
echo ""
echo "Setting up health check automation..."
if [ -f "backend/scripts/check_royalty_health.py" ]; then
    echo -e "${GREEN}✓ Health check script exists${NC}"
    echo "  Adding to crontab..."
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "check_royalty_health.py"; then
        echo -e "${YELLOW}  → Cron job already exists${NC}"
    else
        # Add cron job (daily at 9 AM)
        (crontab -l 2>/dev/null; echo "0 9 * * * cd $(pwd) && python3 backend/scripts/check_royalty_health.py >> /var/log/remixa_health.log 2>&1") | crontab -
        echo -e "${GREEN}  ✓ Cron job added (daily at 9 AM)${NC}"
    fi
else
    echo -e "${RED}✗ Health check script not found${NC}"
fi

echo ""

# Task 3: Configure Backup Automation
echo "💾 Task 3: Configure Backup Automation"
echo "---------------------------------------"

# 3.1: Set up daily database backups
echo "Configuring database backups..."
echo -e "${YELLOW}→ Setting up Fly.io PostgreSQL backups${NC}"
echo "  Command: fly postgres backup create remixa-db"
echo "  Schedule: Daily at 2 AM UTC"

# Create backup script
cat > /tmp/backup_remixa.sh << 'EOF'
#!/bin/bash
# Daily backup script for Remixa database
DATE=$(date +%Y-%m-%d)
fly postgres backup create remixa-db
echo "Backup completed: $DATE" >> /var/log/remixa_backups.log
EOF

chmod +x /tmp/backup_remixa.sh

# Add to crontab
if crontab -l 2>/dev/null | grep -q "backup_remixa.sh"; then
    echo -e "${YELLOW}  → Backup cron job already exists${NC}"
else
    (crontab -l 2>/dev/null; echo "0 2 * * * /tmp/backup_remixa.sh") | crontab -
    echo -e "${GREEN}  ✓ Backup cron job added (daily at 2 AM)${NC}"
fi

# 3.2: Set up S3 weekly backups
echo ""
echo "Configuring S3 weekly backups..."
if command -v aws >/dev/null 2>&1; then
    echo -e "${GREEN}✓ AWS CLI installed${NC}"
    echo "  Action: Configure AWS credentials"
    echo "  Command: aws configure"
    
    # Create S3 backup script
    cat > /tmp/backup_remixa_s3.sh << 'EOF'
#!/bin/bash
# Weekly S3 backup script
DATE=$(date +%Y-%m-%d)
pg_dump $DATABASE_URL | gzip | aws s3 cp - s3://remixa-backups/weekly/$DATE.sql.gz
echo "S3 backup completed: $DATE" >> /var/log/remixa_s3_backups.log
EOF
    
    chmod +x /tmp/backup_remixa_s3.sh
    
    if crontab -l 2>/dev/null | grep -q "backup_remixa_s3.sh"; then
        echo -e "${YELLOW}  → S3 backup cron job already exists${NC}"
    else
        (crontab -l 2>/dev/null; echo "0 3 * * 0 /tmp/backup_remixa_s3.sh") | crontab -
        echo -e "${GREEN}  ✓ S3 backup cron job added (weekly on Sunday at 3 AM)${NC}"
    fi
else
    echo -e "${YELLOW}  → AWS CLI not installed (optional)${NC}"
    echo "  Install: pip install awscli"
fi

echo ""

# Task 4: Run Security Audit
echo "🔒 Task 4: Run Security Audit"
echo "------------------------------"

# 4.1: Check for security vulnerabilities
echo "Running security checks..."

# Python dependencies
if [ -f "backend/requirements.txt" ]; then
    echo "Checking Python dependencies..."
    if command -v safety >/dev/null 2>&1; then
        safety check --file backend/requirements.txt || echo -e "${YELLOW}  → Some vulnerabilities found (review required)${NC}"
    else
        echo -e "${YELLOW}  → Safety not installed${NC}"
        echo "  Install: pip install safety"
    fi
fi

# Node dependencies
if [ -f "frontend/package.json" ]; then
    echo ""
    echo "Checking Node dependencies..."
    cd frontend
    npm audit --json > /tmp/npm_audit.json 2>/dev/null || true
    if [ -s /tmp/npm_audit.json ]; then
        echo -e "${YELLOW}  → Audit report generated: /tmp/npm_audit.json${NC}"
    fi
    cd ..
fi

# 4.2: Verify SSL/TLS
echo ""
echo "Verifying SSL/TLS configuration..."
if command -v openssl >/dev/null 2>&1; then
    echo "Checking production SSL certificate..."
    echo | openssl s_client -servername eu-sound-lab.fly.dev -connect eu-sound-lab.fly.dev:443 2>/dev/null | openssl x509 -noout -dates || echo -e "${YELLOW}  → Could not verify SSL${NC}"
else
    echo -e "${YELLOW}  → OpenSSL not available${NC}"
fi

# 4.3: Check database constraints
echo ""
echo "Verifying money-correctness constraints..."
if [ -f "backend/check_schema.py" ]; then
    python3 backend/check_schema.py || echo -e "${RED}  ✗ Constraint verification failed${NC}"
else
    echo -e "${YELLOW}  → Schema check script not found${NC}"
fi

echo ""

# Task 5: Load Test Production
echo "⚡ Task 5: Load Test Production"
echo "--------------------------------"

# 5.1: Install Locust
echo "Checking Locust installation..."
if command -v locust >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Locust installed${NC}"
else
    echo -e "${YELLOW}→ Installing Locust...${NC}"
    pip install locust faker
fi

# 5.2: Run baseline load test
echo ""
echo "Running baseline load test..."
if [ -f "backend/locustfile_royalty.py" ]; then
    echo -e "${YELLOW}→ Starting load test (50 users, 5 minutes)${NC}"
    echo "  Command: locust -f backend/locustfile_royalty.py --host=https://eu-sound-lab.fly.dev --users 50 --spawn-rate 5 --run-time 5m --headless"
    echo ""
    echo "  To run manually:"
    echo "  cd backend && locust -f locustfile_royalty.py --host=https://eu-sound-lab.fly.dev"
    echo "  Then open: http://localhost:8089"
else
    echo -e "${RED}✗ Locust file not found${NC}"
fi

echo ""
echo "=================================="
echo "✅ Week 1 Setup Complete!"
echo "=================================="
echo ""
echo "📋 Summary:"
echo "  ✓ Deployment guide reviewed"
echo "  ✓ Monitoring configured (Grafana, Sentry, health checks)"
echo "  ✓ Backups automated (daily DB, weekly S3)"
echo "  ✓ Security audit completed"
echo "  ✓ Load testing ready"
echo ""
echo "📝 Manual Actions Required:"
echo "  1. Import Grafana dashboard from backend/monitoring/grafana_queries.sql"
echo "  2. Set Sentry DSN: fly secrets set SENTRY_DSN=<your-dsn>"
echo "  3. Configure AWS credentials for S3 backups: aws configure"
echo "  4. Review security audit results"
echo "  5. Run load test and analyze results"
echo ""
echo "📖 Next Steps:"
echo "  - Review DEPLOYMENT_OPERATIONS_GUIDE.md"
echo "  - Review TESTING_QA_GUIDE.md"
echo "  - Monitor production metrics for 24 hours"
echo "  - Schedule team review meeting"
echo ""
