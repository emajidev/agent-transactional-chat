#!/bin/bash
# Script para iniciar la aplicación con uvicorn usando el puerto del .env
cd "$(dirname "$0")"

# Cargar variables de entorno del .env
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✓ Variables de entorno cargadas desde .env"
    echo "✓ Puerto: ${PORT:-3000}"
    echo "✓ Host: ${HOST:-0.0.0.0}"
else
    echo "⚠ Archivo .env no encontrado"
fi

# Ejecutar uvicorn con el puerto del .env
uvicorn src.main:app --reload --host "${HOST:-0.0.0.0}" --port "${PORT:-3000}"
