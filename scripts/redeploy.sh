#!/bin/bash
# ===========================================
# Redeploy Script - Carlos Command
# ===========================================
# Uso: ./scripts/redeploy.sh
# Para usar en VPS manualmente

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_DIR="/opt/carlos-command"
cd $APP_DIR

echo -e "${GREEN}=== Carlos Command - Redeploy ===${NC}"

# 1. Pull changes
echo -e "${YELLOW}[1/7] Pulling latest changes...${NC}"
git fetch origin main
git reset --hard origin/main

# 2. Stop app gracefully (keep postgres running)
echo -e "${YELLOW}[2/7] Stopping app container...${NC}"
docker-compose -f docker-compose.prod.yml stop app 2>/dev/null || true
docker rm -f carlos-command-app 2>/dev/null || true

# 3. Build
echo -e "${YELLOW}[3/7] Building new image...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache app

# 4. Ensure PostgreSQL is running
echo -e "${YELLOW}[4/7] Ensuring PostgreSQL is running...${NC}"
docker-compose -f docker-compose.prod.yml up -d postgres
sleep 3

# 5. Run migrations
echo -e "${YELLOW}[5/7] Running migrations...${NC}"
docker-compose -f docker-compose.prod.yml run --rm migrations
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Migrations completed${NC}"
else
    echo -e "${RED}Migration failed!${NC}"
    exit 1
fi

# 6. Start app
echo -e "${YELLOW}[6/7] Starting app container...${NC}"
docker-compose -f docker-compose.prod.yml up -d app

# 7. Health check with retry
echo -e "${YELLOW}[7/7] Health check...${NC}"
for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}Health check passed!${NC}"
        break
    fi
    echo "Attempt $i/30 - waiting..."
    sleep 2
done

# Final check
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}    DEPLOY EXITOSO                         ${NC}"
    echo -e "${GREEN}============================================${NC}"
    docker ps | grep carlos
else
    echo -e "${RED}Deploy failed! Logs:${NC}"
    docker-compose -f docker-compose.prod.yml logs --tail=50
    exit 1
fi

# Cleanup (solo imagenes huerfanas, NO volumenes)
echo -e "${YELLOW}Cleaning orphan images...${NC}"
docker image prune -f
