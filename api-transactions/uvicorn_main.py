"""
Wrapper para uvicorn que carga el .env antes de iniciar el servidor
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde .env ANTES de que uvicorn las necesite
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    print(f"✓ Variables de entorno cargadas desde {env_path}")
    
    # Establecer variables de entorno para que uvicorn las lea
    port = os.getenv("PORT", "3000")
    host = os.getenv("HOST", "0.0.0.0")
    
    # Establecer en el entorno para que uvicorn las use
    os.environ["PORT"] = port
    os.environ["HOST"] = host
    
    print(f"✓ Puerto configurado: {port}")
    print(f"✓ Host configurado: {host}")
else:
    print(f"⚠ Archivo .env no encontrado en {env_path}")

# Ahora importar y ejecutar uvicorn
if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "3000"))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("DEBUG", "False").lower() == "true"
    
    print(f"🚀 Iniciando servidor en http://{host}:{port}")
    
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="debug" if reload else "info"
    )




