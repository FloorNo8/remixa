#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default environment
ENV=${1:-staging}

echo -e "${BLUE}🚀 Deploying to ${ENV}...${NC}\n"

# Validate environment
if [[ "$ENV" != "staging" && "$ENV" != "production" ]]; then
    echo -e "${RED}❌ Invalid environment: ${ENV}${NC}"
    echo "Usage: ./deploy.sh [staging|production]"
    exit 1
fi

# Confirm production deployment
if [ "$ENV" = "production" ]; then
    echo -e "${YELLOW}⚠️  WARNING: Deploying to PRODUCTION${NC}"
    read -p "Are you sure? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo -e "${RED}❌ Deployment cancelled${NC}"
        exit 0
    fi
fi

# Run tests
echo -e "${BLUE}🧪 Running tests...${NC}"
cd backend
if ! pytest --tb=short -q; then
    echo -e "${RED}❌ Backend tests failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Backend tests passed${NC}\n"

cd ../frontend
if ! npm run lint; then
    echo -e "${RED}❌ Frontend linting failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend linting passed${NC}\n"

if ! npm run build; then
    echo -e "${RED}❌ Frontend build failed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Frontend build successful${NC}\n"

# Deploy backend
echo -e "${BLUE}🚀 Deploying backend to Fly.io...${NC}"
cd ../backend

if [ "$ENV" = "production" ]; then
    if ! flyctl deploy --app remixa-api --remote-only; then
        echo -e "${RED}❌ Backend deployment failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Backend deployed to production${NC}\n"
else
    if ! flyctl deploy --app remixa-api-staging --config fly.staging.toml --remote-only; then
        echo -e "${RED}❌ Backend deployment failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Backend deployed to staging${NC}\n"
fi

# Run database migrations
echo -e "${BLUE}🔄 Running database migrations...${NC}"
APP_NAME=$([ "$ENV" = "production" ] && echo "remixa-api" || echo "remixa-api-staging")
if ! flyctl ssh console --app "$APP_NAME" -C "python -m alembic upgrade head"; then
    echo -e "${YELLOW}⚠️  Migration failed or not configured${NC}\n"
else
    echo -e "${GREEN}✅ Migrations complete${NC}\n"
fi

# Deploy frontend
echo -e "${BLUE}🚀 Deploying frontend to Vercel...${NC}"
cd ../frontend

if [ "$ENV" = "production" ]; then
    if ! vercel --prod; then
        echo -e "${RED}❌ Frontend deployment failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Frontend deployed to production${NC}\n"
else
    if ! vercel; then
        echo -e "${RED}❌ Frontend deployment failed${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ Frontend deployed to staging${NC}\n"
fi

# Health check
echo -e "${BLUE}🏥 Running health checks...${NC}"
if [ "$ENV" = "production" ]; then
    BACKEND_URL="https://api.remixa.eu"
    FRONTEND_URL="https://remixa.vercel.app"
else
    BACKEND_URL="https://remixa-api-staging.fly.dev"
    FRONTEND_URL="https://remixa-staging.vercel.app"
fi

# Check backend health
if curl -f -s "$BACKEND_URL/health" > /dev/null; then
    echo -e "${GREEN}✅ Backend health check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Backend health check failed${NC}"
fi

# Check frontend
if curl -f -s "$FRONTEND_URL" > /dev/null; then
    echo -e "${GREEN}✅ Frontend health check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Frontend health check failed${NC}"
fi

echo ""
echo -e "${GREEN}✅ Deployment complete!${NC}"
echo ""
echo -e "${BLUE}📍 URLs:${NC}"
echo -e "   Backend:  $BACKEND_URL"
echo -e "   Frontend: $FRONTEND_URL"
echo ""
