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
echo -e "${YELLOW}[1/6] Pulling latest changes...${NC}"
git fetch origin main
git reset --hard origin/main

# 2. Stop gracefully
echo -e "${YELLOW}[2/6] Stopping current container...${NC}"
docker-compose -f docker-compose.prod.yml down --remove-orphans 2>/dev/null || true

# 3. Remove if stuck
echo -e "${YELLOW}[3/6] Cleaning up old container...${NC}"
docker rm -f carlos-command-app 2>/dev/null || true

# 4. Build
echo -e "${YELLOW}[4/6] Building new image...${NC}"
docker-compose -f docker-compose.prod.yml build --no-cache

# 5. Start
echo -e "${YELLOW}[5/6] Starting container...${NC}"
docker-compose -f docker-compose.prod.yml up -d

# 6. Health check with retry
echo -e "${YELLOW}[6/6] Health check...${NC}"
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
