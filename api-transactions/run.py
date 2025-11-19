#!/usr/bin/env python3
"""
Script para ejecutar la aplicación con uvicorn cargando las variables de entorno del .env
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import uvicorn

# Cargar variables de entorno desde .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✓ Variables de entorno cargadas desde {env_path}")
else:
    print(f"⚠ Archivo .env no encontrado en {env_path}")

# Obtener configuración de variables de entorno
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "3000"))
debug = os.getenv("DEBUG", "False").lower() == "true"
reload = debug

print(f"🚀 Iniciando servidor en http://{host}:{port}")
print(f"   Debug: {debug}, Reload: {reload}")
print(f"   Puerto desde .env: {port}")

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if debug else "info"
    )

