#!/bin/bash
set -e

echo "Esperando a que la base de datos esté lista..."
# Esperar un poco para asegurar que la base de datos esté completamente lista
sleep 2

echo "Ejecutando migraciones de base de datos..."
alembic upgrade head

echo "Migraciones completadas. Iniciando aplicación..."
exec python -m src.main



