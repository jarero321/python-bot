#!/bin/bash
# Entrypoint: solo inicia la app
# Las migraciones se corren por separado via deploy.sh

set -e

echo "=== Carlos Command ==="

# Esperar a que PostgreSQL este listo
echo "Esperando PostgreSQL..."
until pg_isready -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -q; do
    sleep 1
done
echo "PostgreSQL listo"

# Iniciar aplicacion
echo "Iniciando app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
