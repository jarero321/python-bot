#!/bin/bash
# Carlos Command - Desarrollo (con ngrok)

set -e

echo "Carlos Command - Desarrollo"
echo "============================"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Verificar .env
if [ ! -f .env ]; then
    echo -e "${RED}Error: No existe .env${NC}"
    echo "Copia .env.example a .env y configura"
    exit 1
fi

# Cargar variables
export $(grep -v '^#' .env | xargs)

# Verificar configuracion
echo ""
echo "Verificando configuracion..."

check_var() {
    local var_name=$1
    local var_value=$2
    if [ -z "$var_value" ] || [[ "$var_value" == your_* ]]; then
        echo -e "  ${RED}✗ $var_name${NC}"
        return 1
    else
        echo -e "  ${GREEN}✓ $var_name${NC}"
        return 0
    fi
}

errors=0
check_var "TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_TOKEN" || ((errors++))
check_var "TELEGRAM_CHAT_ID" "$TELEGRAM_CHAT_ID" || ((errors++))
check_var "GEMINI_API_KEY" "$GEMINI_API_KEY" || ((errors++))
check_var "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD" || ((errors++))
check_var "NGROK_AUTHTOKEN" "$NGROK_AUTHTOKEN" || ((errors++))

if [ $errors -gt 0 ]; then
    echo -e "\n${RED}Faltan $errors configuraciones${NC}"
    exit 1
fi

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker no instalado${NC}"
    exit 1
fi

# Determinar comando compose
if docker compose version &> /dev/null; then
    COMPOSE="docker compose"
else
    COMPOSE="docker-compose"
fi

# Crear directorios
mkdir -p logs

# Build si es necesario
echo ""
if [ "$1" = "--rebuild" ]; then
    echo "Reconstruyendo..."
    $COMPOSE build --no-cache
else
    echo "Construyendo..."
    $COMPOSE build
fi

# Levantar
echo ""
echo "Iniciando servicios..."
$COMPOSE up -d

# Esperar
echo ""
echo "Esperando servicios..."
sleep 8

# Estado
echo ""
$COMPOSE ps

# Obtener URL ngrok
echo ""
echo "Obteniendo URL ngrok..."
sleep 3

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"https://[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$NGROK_URL" ]; then
    echo -e "${GREEN}Ngrok: $NGROK_URL${NC}"

    WEBHOOK_URL="${NGROK_URL}/telegram/webhook"
    echo ""
    echo "Configurando webhook..."

    RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")

    if echo "$RESPONSE" | grep -q '"ok":true'; then
        echo -e "${GREEN}Webhook: $WEBHOOK_URL${NC}"
    else
        echo -e "${RED}Error webhook: $RESPONSE${NC}"
    fi
else
    echo -e "${YELLOW}No se obtuvo URL ngrok${NC}"
    echo "Revisa http://localhost:4040"
fi

echo ""
echo "============================"
echo -e "${GREEN}Listo!${NC}"
echo ""
echo "Telegram: Envia mensaje a tu bot"
echo "Ngrok:    http://localhost:4040"
echo "Health:   http://localhost:8000/health"
echo "Logs:     $COMPOSE logs -f app"
echo "Parar:    $COMPOSE down"
echo ""
