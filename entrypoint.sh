#!/bin/sh
set -e

echo "Verificando base de datos..."
# Reintentar migracion por hasta 30 segundos si Postgres esta iniciando
MAX_TRIES=30
COUNT=0
until python manage.py migrate --noinput || [ $COUNT -eq $MAX_TRIES ]; do
    echo "Esperando que la base de datos este lista ($COUNT/$MAX_TRIES)..."
    sleep 1
    COUNT=$((COUNT+1))
done

echo "Poblando personajes y superusuario..."
python poblar_personajes.py || true

echo "Iniciando servidor Django en 0.0.0.0:8000..."
exec python manage.py runserver 0.0.0.0:8000
