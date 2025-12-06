#!/bin/bash
# Script para correr migraciones
# Se ejecuta UNA vez durante el deploy, no en cada restart

set -e

echo "=== Migraciones ==="

# Esperar PostgreSQL
echo "Esperando PostgreSQL..."
until pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -q; do
    sleep 1
done

# Mostrar estado actual
echo "Estado actual:"
alembic current

# Aplicar migraciones pendientes
echo "Aplicando migraciones..."
alembic upgrade head

echo "Migraciones completadas"
alembic current
