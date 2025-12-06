FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema (incluye postgresql-client para pg_isready)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primero (cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copiar codigo
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY scripts/entrypoint.sh ./entrypoint.sh
COPY scripts/migrate.sh ./scripts/migrate.sh
RUN chmod +x ./entrypoint.sh ./scripts/migrate.sh

# Crear directorio para logs
RUN mkdir -p /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint para la app (migraciones se corren por separado)
ENTRYPOINT ["./entrypoint.sh"]
