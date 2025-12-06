#!/bin/bash
# Script de deploy seguro para produccion
# Uso: ./scripts/deploy.sh

set -e

echo "=========================================="
echo "   Carlos Command - Deploy Produccion"
echo "=========================================="

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Verificar .env
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env no existe${NC}"
    echo "Copia .env.example y configura las variables"
    exit 1
fi

# Verificar variables criticas
source .env
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}Error: POSTGRES_PASSWORD no configurado${NC}"
    exit 1
fi

if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
    echo -e "${RED}Error: TELEGRAM_BOT_TOKEN no configurado${NC}"
    exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}Error: GEMINI_API_KEY no configurado${NC}"
    exit 1
fi

echo -e "${GREEN}Variables de entorno OK${NC}"

# Paso 1: Build
echo ""
echo -e "${YELLOW}[1/5] Building images...${NC}"
docker-compose -f docker-compose.prod.yml build

# Paso 2: Iniciar PostgreSQL
echo ""
echo -e "${YELLOW}[2/5] Iniciando PostgreSQL...${NC}"
docker-compose -f docker-compose.prod.yml up -d postgres

# Esperar a que PostgreSQL este healthy
echo "Esperando PostgreSQL..."
timeout=60
counter=0
until docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U ${POSTGRES_USER:-carlos} -q 2>/dev/null; do
    counter=$((counter + 1))
    if [ $counter -gt $timeout ]; then
        echo -e "${RED}Error: PostgreSQL no responde despues de ${timeout}s${NC}"
        exit 1
    fi
    sleep 1
done
echo -e "${GREEN}PostgreSQL listo${NC}"

# Paso 3: Ejecutar migraciones (one-shot)
echo ""
echo -e "${YELLOW}[3/5] Ejecutando migraciones...${NC}"
docker-compose -f docker-compose.prod.yml run --rm migrations

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Migraciones completadas${NC}"
else
    echo -e "${RED}Error en migraciones${NC}"
    exit 1
fi

# Paso 4: Iniciar app
echo ""
echo -e "${YELLOW}[4/5] Iniciando aplicacion...${NC}"
docker-compose -f docker-compose.prod.yml up -d app

# Esperar health check
echo "Esperando health check..."
timeout=90
counter=0
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
    counter=$((counter + 1))
    if [ $counter -gt $timeout ]; then
        echo -e "${RED}Error: App no responde despues de ${timeout}s${NC}"
        docker-compose -f docker-compose.prod.yml logs app
        exit 1
    fi
    sleep 1
done
echo -e "${GREEN}App lista${NC}"

# Paso 5: Configurar webhook
echo ""
echo -e "${YELLOW}[5/5] Configurando webhook Telegram...${NC}"
if [ -n "$TELEGRAM_WEBHOOK_URL" ]; then
    WEBHOOK_RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${TELEGRAM_WEBHOOK_URL}/telegram/webhook")

    if echo "$WEBHOOK_RESPONSE" | grep -q '"ok":true'; then
        echo -e "${GREEN}Webhook configurado: ${TELEGRAM_WEBHOOK_URL}/telegram/webhook${NC}"
    else
        echo -e "${YELLOW}Warning: No se pudo configurar webhook${NC}"
        echo "$WEBHOOK_RESPONSE"
    fi
else
    echo -e "${YELLOW}Warning: TELEGRAM_WEBHOOK_URL no configurado${NC}"
fi

# Resumen
echo ""
echo "=========================================="
echo -e "${GREEN}Deploy completado!${NC}"
echo "=========================================="
echo ""
echo "Servicios:"
docker-compose -f docker-compose.prod.yml ps
echo ""
echo "Comandos utiles:"
echo "  Ver logs:     docker-compose -f docker-compose.prod.yml logs -f app"
echo "  Restart:      docker-compose -f docker-compose.prod.yml restart app"
echo "  Stop:         docker-compose -f docker-compose.prod.yml down"
echo "  Backup DB:    docker exec carlos-postgres pg_dump -U carlos carlos_brain > backup.sql"
echo ""
