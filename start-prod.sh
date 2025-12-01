#!/bin/bash
# Carlos Command - Script de inicio para PRODUCCIÓN (Cloudflare Tunnel)

set -e

echo "🚀 Carlos Command - Iniciando en PRODUCCIÓN..."
echo "================================================"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verificar que existe .env
if [ ! -f .env ]; then
    echo -e "${RED}❌ Error: No existe archivo .env${NC}"
    echo "   Copia .env.example a .env y configura tus tokens"
    exit 1
fi

# Cargar variables de .env
export $(grep -v '^#' .env | xargs)

# Verificar tokens requeridos
echo ""
echo "📋 Verificando configuración..."

check_var() {
    local var_name=$1
    local var_value=$2
    local is_required=$3

    if [ -z "$var_value" ] || [ "$var_value" = "your_"* ]; then
        if [ "$is_required" = "true" ]; then
            echo -e "   ${RED}❌ $var_name: No configurado${NC}"
            return 1
        else
            echo -e "   ${YELLOW}⚠️  $var_name: No configurado (opcional)${NC}"
            return 0
        fi
    else
        echo -e "   ${GREEN}✅ $var_name: Configurado${NC}"
        return 0
    fi
}

errors=0
check_var "TELEGRAM_BOT_TOKEN" "$TELEGRAM_BOT_TOKEN" "true" || ((errors++))
check_var "TELEGRAM_CHAT_ID" "$TELEGRAM_CHAT_ID" "true" || ((errors++))
check_var "GEMINI_API_KEY" "$GEMINI_API_KEY" "true" || ((errors++))
check_var "NOTION_API_KEY" "$NOTION_API_KEY" "true" || ((errors++))
check_var "CLOUDFLARE_TUNNEL_TOKEN" "$CLOUDFLARE_TUNNEL_TOKEN" "true" || ((errors++))
check_var "TELEGRAM_WEBHOOK_URL" "$TELEGRAM_WEBHOOK_URL" "true" || ((errors++))

if [ $errors -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Faltan $errors configuraciones requeridas${NC}"
    echo "   Edita el archivo .env y vuelve a intentar"
    echo ""
    echo -e "${BLUE}📖 Para configurar Cloudflare Tunnel:${NC}"
    echo "   1. Ve a https://one.dash.cloudflare.com/"
    echo "   2. Zero Trust -> Networks -> Tunnels"
    echo "   3. Crea un tunnel y copia el token"
    echo "   4. Configura el Public Hostname apuntando a http://app:8000"
    exit 1
fi

echo ""
echo "🐳 Iniciando servicios con Docker (Producción)..."
echo "================================================"

# Verificar Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker no está instalado${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose no está instalado${NC}"
    exit 1
fi

# Crear directorios necesarios
mkdir -p data logs

# Determinar comando de docker-compose
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

# Usar archivo de producción
COMPOSE_FILE="-f docker-compose.prod.yml"

# Construir y levantar
echo ""

# Verificar si es primera vez o se pide rebuild
if [ "$1" = "--rebuild" ]; then
    echo "📦 Reconstruyendo imagen (--no-cache)..."
    $COMPOSE_CMD $COMPOSE_FILE build --no-cache
elif [ ! "$(docker images -q carlos-command-app 2> /dev/null)" ]; then
    echo "📦 Primera vez - Construyendo imagen..."
    $COMPOSE_CMD $COMPOSE_FILE build
else
    echo "📦 Usando imagen existente (usa --rebuild para forzar reconstrucción)"
fi

echo ""
echo "🚀 Levantando servicios..."
$COMPOSE_CMD $COMPOSE_FILE up -d

# Esperar a que los servicios estén listos
echo ""
echo "⏳ Esperando a que los servicios estén listos..."
sleep 8

# Verificar estado
echo ""
echo "📊 Estado de servicios:"
$COMPOSE_CMD $COMPOSE_FILE ps

# Configurar webhook de Telegram
echo ""
echo "📡 Configurando webhook de Telegram..."

WEBHOOK_URL="${TELEGRAM_WEBHOOK_URL}"

# Verificar que la URL no termine en / antes de añadir el path
WEBHOOK_URL="${WEBHOOK_URL%/}"
if [[ ! "$WEBHOOK_URL" == */webhook/telegram ]]; then
    WEBHOOK_URL="${WEBHOOK_URL}/webhook/telegram"
fi

RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")

if echo "$RESPONSE" | grep -q '"ok":true'; then
    echo -e "${GREEN}✅ Webhook configurado: $WEBHOOK_URL${NC}"
else
    echo -e "${RED}❌ Error configurando webhook: $RESPONSE${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Verifica que tu dominio en Cloudflare esté configurado correctamente${NC}"
fi

# Verificar información del webhook
echo ""
echo "📋 Info del webhook actual:"
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo" | python3 -m json.tool 2>/dev/null || \
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"

echo ""
echo "================================================"
echo -e "${GREEN}🎉 Carlos Command está corriendo en PRODUCCIÓN!${NC}"
echo ""
echo "📱 Abre Telegram y envía un mensaje a tu bot"
echo "🏥 Health check: http://localhost:8000/health"
echo "🌐 URL pública: ${TELEGRAM_WEBHOOK_URL%/webhook/telegram}"
echo "📝 Logs: $COMPOSE_CMD $COMPOSE_FILE logs -f app"
echo "📝 Logs Cloudflare: $COMPOSE_CMD $COMPOSE_FILE logs -f cloudflared"
echo ""
echo "Para detener: $COMPOSE_CMD $COMPOSE_FILE down"
echo "================================================"
