#!/bin/bash
# Backup automatico de PostgreSQL
# Uso: ./scripts/backup.sh
# Cron: 0 3 * * * /opt/carlos-command/scripts/backup.sh

set -e

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/carlos-command}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/carlos_brain_$DATE.sql.gz"

# Crear directorio si no existe
mkdir -p "$BACKUP_DIR"

echo "=== Backup PostgreSQL ==="
echo "Fecha: $DATE"

# Hacer dump comprimido
docker exec carlos-postgres pg_dump -U carlos carlos_brain | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "Backup creado: $BACKUP_FILE ($SIZE)"
else
    echo "Error creando backup"
    exit 1
fi

# Limpiar backups viejos
echo "Limpiando backups mayores a $RETENTION_DAYS dias..."
find "$BACKUP_DIR" -name "carlos_brain_*.sql.gz" -mtime +$RETENTION_DAYS -delete

# Listar backups actuales
echo ""
echo "Backups disponibles:"
ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null || echo "No hay backups"

echo ""
echo "Backup completado"
