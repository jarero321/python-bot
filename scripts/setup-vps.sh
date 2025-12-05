#!/bin/bash
# ===========================================
# Setup VPS para CI/CD - Carlos Command
# ===========================================
# Ejecutar como root en la VPS de Hostinger
# curl -sSL https://raw.githubusercontent.com/tu-repo/main/scripts/setup-vps.sh | bash

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

APP_DIR="/opt/carlos-command"
DEPLOY_USER="deploy"

echo -e "${GREEN}=== Setup VPS para CI/CD ===${NC}"

# Verificar root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Ejecuta como root${NC}"
    exit 1
fi

# ===========================================
# 1. Instalar dependencias
# ===========================================
echo -e "${YELLOW}[1/6] Instalando dependencias...${NC}"
apt-get update
apt-get install -y docker.io docker-compose nginx certbot python3-certbot-nginx curl git

systemctl start docker
systemctl enable docker

# ===========================================
# 2. Crear usuario deploy
# ===========================================
echo -e "${YELLOW}[2/6] Creando usuario deploy...${NC}"
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash $DEPLOY_USER
    usermod -aG docker $DEPLOY_USER
    usermod -aG sudo $DEPLOY_USER
    echo -e "${GREEN}Usuario $DEPLOY_USER creado${NC}"
else
    echo "Usuario $DEPLOY_USER ya existe"
fi

# ===========================================
# 3. Configurar SSH keys
# ===========================================
echo -e "${YELLOW}[3/6] Configurando SSH keys...${NC}"
DEPLOY_HOME="/home/$DEPLOY_USER"
SSH_DIR="$DEPLOY_HOME/.ssh"

mkdir -p $SSH_DIR
chmod 700 $SSH_DIR

# Generar key para GitHub Actions
if [ ! -f "$SSH_DIR/github_actions" ]; then
    ssh-keygen -t ed25519 -C "github-actions-deploy" -f "$SSH_DIR/github_actions" -N ""
    cat "$SSH_DIR/github_actions.pub" >> "$SSH_DIR/authorized_keys"
    chmod 600 "$SSH_DIR/authorized_keys"
    chown -R $DEPLOY_USER:$DEPLOY_USER $SSH_DIR
fi

# ===========================================
# 4. Clonar repositorio
# ===========================================
echo -e "${YELLOW}[4/6] Clonando repositorio...${NC}"
if [ ! -d "$APP_DIR" ]; then
    read -p "URL del repositorio GitHub: " REPO_URL
    git clone $REPO_URL $APP_DIR
    chown -R $DEPLOY_USER:$DEPLOY_USER $APP_DIR
else
    echo "Repositorio ya existe en $APP_DIR"
fi

# Crear directorios
mkdir -p $APP_DIR/data $APP_DIR/logs
chown -R $DEPLOY_USER:$DEPLOY_USER $APP_DIR

# ===========================================
# 5. Configurar .env
# ===========================================
echo -e "${YELLOW}[5/6] Configurando variables de entorno...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.example" ]; then
        cp $APP_DIR/.env.example $APP_DIR/.env
        echo -e "${YELLOW}Edita el archivo .env con tus credenciales:${NC}"
        echo "  nano $APP_DIR/.env"
    else
        echo -e "${RED}No se encontro .env.example${NC}"
    fi
fi

# ===========================================
# 6. Resumen
# ===========================================
echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}    SETUP COMPLETADO                       ${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo -e "${YELLOW}SSH Key PRIVADA para GitHub Secrets:${NC}"
echo "--------------------------------------------"
cat $SSH_DIR/github_actions
echo "--------------------------------------------"
echo ""
echo -e "${YELLOW}Configura estos GitHub Secrets:${NC}"
echo "  VPS_HOST     = $(curl -s ifconfig.me)"
echo "  VPS_USER     = $DEPLOY_USER"
echo "  VPS_SSH_KEY  = (contenido de arriba)"
echo "  VPS_PORT     = 22"
echo ""
echo -e "${YELLOW}Siguiente paso:${NC}"
echo "1. Configura .env: nano $APP_DIR/.env"
echo "2. Ejecuta deploy inicial: cd $APP_DIR && ./deploy.sh tu-dominio.com"
echo ""
