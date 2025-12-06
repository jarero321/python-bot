#!/bin/bash
# Restaurar backup de PostgreSQL
# Uso: ./scripts/restore.sh /path/to/backup.sql.gz

set -e

if [ -z "$1" ]; then
    echo "Uso: ./scripts/restore.sh <archivo_backup.sql.gz>"
    echo ""
    echo "Backups disponibles:"
    ls -lh /opt/backups/carlos-command/*.sql.gz 2>/dev/null || echo "No hay backups en /opt/backups/carlos-command/"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Archivo no encontrado: $BACKUP_FILE"
    exit 1
fi

echo "=== Restaurar PostgreSQL ==="
echo "Archivo: $BACKUP_FILE"
echo ""
echo "ADVERTENCIA: Esto reemplazara TODOS los datos actuales!"
read -p "Continuar? (escribe 'SI' para confirmar): " confirm

if [ "$confirm" != "SI" ]; then
    echo "Cancelado"
    exit 0
fi

echo ""
echo "Restaurando..."

# Descomprimir y restaurar
gunzip -c "$BACKUP_FILE" | docker exec -i carlos-postgres psql -U carlos carlos_brain

if [ $? -eq 0 ]; then
    echo ""
    echo "Restauracion completada"
else
    echo ""
    echo "Error en restauracion"
    exit 1
fi
