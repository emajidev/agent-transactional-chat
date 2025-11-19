"""
Configuración para uvicorn que lee las variables de entorno del .env
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

# Configuración para uvicorn
host = os.getenv("HOST", "0.0.0.0")
port = int(os.getenv("PORT", "3000"))
reload = os.getenv("DEBUG", "False").lower() == "true"



