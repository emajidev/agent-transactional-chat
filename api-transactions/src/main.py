import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.configuration.config import settings
from src.common.mixins.soft_delete_mixin import setup_soft_delete_listeners
from src.modules.transactions.controller import router
from src.modules.transactions.services.transfer_consumer_service import TransferConsumerService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)
    if "PORT" not in os.environ:
        port_from_env = os.getenv("PORT")
        if port_from_env:
            os.environ["PORT"] = port_from_env
    if "HOST" not in os.environ:
        host_from_env = os.getenv("HOST")
        if host_from_env:
            os.environ["HOST"] = host_from_env 

# Metadata configuration for OpenAPI/Swagger
description = """
## Transactions API

API REST for the management of financial transactions.

### Features

* **Full CRUD** of transactions
* **Pagination** in lists
* **Data validation** with Pydantic
* **Interactive documentation** with Swagger UI

### Endpoints

* **Transaccions**: Full management of transactions (create, list, obtain, update, delete)
* **Health**: Health endpoints to verify that the service is working.
"""

tags_metadata = [
    {
        "name": "transactions",
        "description": "Operations to manage financial transactions. Allows creating, listing, obtaining, updating and deleting transactions.",
    },
    {
        "name": "health",
        "description": "Health endpoints to verify that the service is working.",
    },
]

# Crear instancia de FastAPI
logger = logging.getLogger("uvicorn.error")


# Instancia global del servicio de consumidor
transfer_consumer_service = TransferConsumerService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar listeners de SQLAlchemy para soft delete
    setup_soft_delete_listeners()
    logger.info("Soft delete de SQLAlchemy configurado correctamente")
    
    # Iniciar consumidor de RabbitMQ
    try:
        transfer_consumer_service.start()
        logger.info("Consumidor de RabbitMQ iniciado")
    except Exception as e:
        logger.error(f"Error al iniciar consumidor de RabbitMQ: {str(e)}", exc_info=True)
    
    docs_path = app.docs_url or "/docs"
    swagger_url = f"http://{settings.HOST}:{settings.PORT}{docs_path}"
    logger.info("Swagger UI disponible en %s", swagger_url)
    yield
    
    # Detener consumidor al cerrar la aplicación
    try:
        transfer_consumer_service.stop()
        logger.info("Consumidor de RabbitMQ detenido")
    except Exception as e:
        logger.error(f"Error al detener consumidor de RabbitMQ: {str(e)}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=description,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    tags_metadata=tags_metadata,
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
)

# Cords conf middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers of modules
app.include_router(
    router,
    prefix="/api/v1",
    tags=["transactions"]
)


@app.get("/", tags=["health"])
def root():
    """Health endpoint to verify that the service is working."""
    return {
        "message": f"{settings.APP_NAME} está funcionando",
        "version": settings.APP_VERSION
    }


@app.get("/health", tags=["health"])
def health_check():
    """Health endpoint to verify that the service is working."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    # Usar variables de entorno o los valores de settings
    host = os.getenv("HOST", settings.HOST)
    port = int(os.getenv("PORT", settings.PORT))
    
    uvicorn.run(
        "src.main:app",
        host=host,
        port=port,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )

