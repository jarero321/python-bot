#!/bin/bash
# ===========================================
# Carlos Command - Deploy Script
# ===========================================
# Uso: ./deploy.sh [dominio]
# Ejemplo: ./deploy.sh mibot.ejemplo.com

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DOMAIN=${1:-""}
APP_DIR="/opt/carlos-command"

echo -e "${GREEN}=== Carlos Command - Deploy Script ===${NC}"

# Verificar que estamos en la VPS como root o sudo
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Por favor ejecuta como root o con sudo${NC}"
    exit 1
fi

# ===========================================
# 1. Instalar dependencias del sistema
# ===========================================
echo -e "${YELLOW}[1/7] Instalando dependencias del sistema...${NC}"
apt-get update
apt-get install -y docker.io docker-compose nginx certbot python3-certbot-nginx curl git

# Iniciar Docker
systemctl start docker
systemctl enable docker

# ===========================================
# 2. Clonar/Actualizar repositorio
# ===========================================
echo -e "${YELLOW}[2/7] Configurando repositorio...${NC}"
if [ -d "$APP_DIR" ]; then
    echo "Actualizando repositorio existente..."
    cd $APP_DIR
    git pull origin main
else
    echo "Clonando repositorio..."
    git clone https://github.com/jarero321/python-bot.git $APP_DIR
    cd $APP_DIR
fi

# ===========================================
# 3. Verificar archivo .env
# ===========================================
echo -e "${YELLOW}[3/7] Verificando configuración...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    echo -e "${RED}ERROR: No existe archivo .env${NC}"
    echo "Copia .env.example a .env y configura las variables:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Crear directorios necesarios
mkdir -p $APP_DIR/data
mkdir -p $APP_DIR/logs

# ===========================================
# 4. Configurar Nginx
# ===========================================
echo -e "${YELLOW}[4/7] Configurando Nginx...${NC}"
if [ -z "$DOMAIN" ]; then
    echo -e "${RED}ERROR: Debes especificar el dominio${NC}"
    echo "Uso: ./deploy.sh tu-dominio.com"
    exit 1
fi

# Copiar y configurar nginx
cp $APP_DIR/nginx/carlos-command.conf /etc/nginx/sites-available/carlos-command
sed -i "s/TU_DOMINIO.com/$DOMAIN/g" /etc/nginx/sites-available/carlos-command

# Habilitar sitio
ln -sf /etc/nginx/sites-available/carlos-command /etc/nginx/sites-enabled/

# Crear directorio para certbot
mkdir -p /var/www/certbot

# Validar configuración de nginx
nginx -t

# ===========================================
# 5. Obtener certificado SSL
# ===========================================
echo -e "${YELLOW}[5/7] Configurando SSL con Let's Encrypt...${NC}"

# Primero iniciar nginx sin SSL para validar dominio
# Crear config temporal sin SSL
cat > /etc/nginx/sites-available/carlos-command-temp << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 200 'OK';
        add_header Content-Type text/plain;
    }
}
EOF

ln -sf /etc/nginx/sites-available/carlos-command-temp /etc/nginx/sites-enabled/carlos-command
systemctl reload nginx

# Obtener certificado
certbot certonly --webroot -w /var/www/certbot -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
    echo -e "${YELLOW}Intentando con --nginx...${NC}"
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN
}

# Restaurar config completa
ln -sf /etc/nginx/sites-available/carlos-command /etc/nginx/sites-enabled/carlos-command
rm -f /etc/nginx/sites-available/carlos-command-temp
systemctl reload nginx

# ===========================================
# 6. Construir y ejecutar Docker
# ===========================================
echo -e "${YELLOW}[6/7] Construyendo y ejecutando contenedor...${NC}"
cd $APP_DIR

# Detener contenedor existente si hay
docker-compose -f docker-compose.prod.yml down 2>/dev/null || true

# Construir imagen
docker-compose -f docker-compose.prod.yml build

# Ejecutar
docker-compose -f docker-compose.prod.yml up -d

# Esperar a que inicie
echo "Esperando a que la aplicación inicie..."
sleep 10

# ===========================================
# 7. Verificar despliegue
# ===========================================
echo -e "${YELLOW}[7/7] Verificando despliegue...${NC}"

# Health check
if curl -sf https://$DOMAIN/health > /dev/null; then
    echo -e "${GREEN}✓ Health check exitoso${NC}"
else
    echo -e "${RED}✗ Health check falló${NC}"
    echo "Revisa los logs: docker-compose -f docker-compose.prod.yml logs"
    exit 1
fi

# ===========================================
# Resumen
# ===========================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    DESPLIEGUE COMPLETADO EXITOSAMENTE     ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "URL: ${GREEN}https://$DOMAIN${NC}"
echo -e "Health: ${GREEN}https://$DOMAIN/health${NC}"
echo -e "Webhook: ${GREEN}https://$DOMAIN/webhook/telegram${NC}"
echo ""
echo -e "${YELLOW}IMPORTANTE: Configura el webhook de Telegram:${NC}"
echo "curl -X POST \"https://api.telegram.org/bot\$TELEGRAM_BOT_TOKEN/setWebhook?url=https://$DOMAIN/webhook/telegram\""
echo ""
echo -e "${YELLOW}Comandos útiles:${NC}"
echo "  Ver logs:     docker-compose -f docker-compose.prod.yml logs -f"
echo "  Reiniciar:    docker-compose -f docker-compose.prod.yml restart"
echo "  Detener:      docker-compose -f docker-compose.prod.yml down"
echo ""
