#!/bin/bash
# Carlos Command - Script de inicio

set -e

echo "🚀 Carlos Command - Iniciando..."
echo "================================"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
check_var "NGROK_AUTHTOKEN" "$NGROK_AUTHTOKEN" "false"

if [ $errors -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ Faltan $errors configuraciones requeridas${NC}"
    echo "   Edita el archivo .env y vuelve a intentar"
    exit 1
fi

echo ""
echo "🐳 Iniciando servicios con Docker..."
echo "================================"

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

# Construir y levantar
echo ""

# Verificar si es primera vez o se pide rebuild
if [ "$1" = "--rebuild" ]; then
    echo "📦 Reconstruyendo imagen (--no-cache)..."
    $COMPOSE_CMD build --no-cache
elif [ ! "$(docker images -q carlos-command-app 2> /dev/null)" ]; then
    echo "📦 Primera vez - Construyendo imagen..."
    $COMPOSE_CMD build
else
    echo "📦 Usando imagen existente (usa --rebuild para forzar reconstrucción)"
    echo "   💡 El código se sincroniza automáticamente via volumen (hot reload)"
fi

echo ""
echo "🚀 Levantando servicios..."
$COMPOSE_CMD up -d

# Esperar a que los servicios estén listos
echo ""
echo "⏳ Esperando a que los servicios estén listos..."
sleep 5

# Verificar estado
echo ""
echo "📊 Estado de servicios:"
$COMPOSE_CMD ps

# Obtener URL de ngrok
echo ""
echo "🔗 Obteniendo URL de ngrok..."
sleep 3

NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | grep -o '"public_url":"[^"]*"' | head -1 | cut -d'"' -f4)

if [ -n "$NGROK_URL" ]; then
    echo -e "${GREEN}✅ URL de ngrok: $NGROK_URL${NC}"

    WEBHOOK_URL="${NGROK_URL}/webhook/telegram"
    echo ""
    echo "📡 Configurando webhook de Telegram..."

    # Configurar webhook
    RESPONSE=$(curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}")

    if echo "$RESPONSE" | grep -q '"ok":true'; then
        echo -e "${GREEN}✅ Webhook configurado: $WEBHOOK_URL${NC}"
    else
        echo -e "${RED}❌ Error configurando webhook: $RESPONSE${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No se pudo obtener URL de ngrok${NC}"
    echo "   Verifica en http://localhost:4040"
fi

echo ""
echo "================================"
echo -e "${GREEN}🎉 Carlos Command está corriendo!${NC}"
echo ""
echo "📱 Abre Telegram y envía un mensaje a tu bot"
echo "📊 Dashboard ngrok: http://localhost:4040"
echo "🏥 Health check: http://localhost:8000/health"
echo "📝 Logs: $COMPOSE_CMD logs -f app"
echo ""
echo "Para detener: $COMPOSE_CMD down"
echo "================================"
