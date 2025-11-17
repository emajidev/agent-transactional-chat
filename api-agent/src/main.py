import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.common.mixins.soft_delete_mixin import setup_soft_delete_listeners
from src.configuration.config import settings
from src.modules.auth.controller import router as auth_router
from src.modules.conversations.controller import router as conversations_router

# Metadata configuration for OpenAPI/Swagger
description = """
## Agent API

API REST for the management of conversations and chat.

### Features

* **Full CRUD** of conversations
* **Chat endpoint** for messaging
* **Pagination** in lists
* **Data validation** with Pydantic
* **Interactive documentation** with Swagger UI

### Endpoints

* **Conversations**: Full management of conversations (create, list, obtain, update, delete)
* **Chat**: Endpoint for chat messaging
* **Health**: Health endpoints to verify that the service is working.
"""

tags_metadata = [
    {
        "name": "auth",
        "description": "Authentication endpoints. Register, login and get current user info.",
    },
    {
        "name": "conversations",
        "description": "Operations to manage conversations. Allows creating, listing, obtaining, updating and deleting conversations.",
    },
    {
        "name": "chat",
        "description": "Chat endpoint for messaging.",
    },
    {
        "name": "health",
        "description": "Health endpoints to verify that the service is working.",
    },
]

# Crear instancia de FastAPI
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializar listeners de SQLAlchemy para soft delete
    setup_soft_delete_listeners()
    logger.info("Soft delete de SQLAlchemy configurado correctamente")

    docs_path = app.docs_url or "/docs"
    swagger_url = f"http://{settings.HOST}:{settings.PORT}{docs_path}"
    logger.info("Swagger UI disponible en %s", swagger_url)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=description,
    debug=settings.DEBUG,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    servers=[
        {
            "url": f"http://localhost:{settings.PORT}",
            "description": "Servidor local (localhost)",
        },
        {
            "url": f"http://127.0.0.1:{settings.PORT}",
            "description": "Servidor local (127.0.0.1)",
        },
    ],
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
app.include_router(auth_router, prefix="/api/v1", tags=["auth"])
app.include_router(conversations_router, prefix="/api/v1", tags=["conversations"])


@app.get("/", tags=["health"])
def root():
    """Health endpoint to verify that the service is working."""
    return {"message": f"{settings.APP_NAME} está funcionando", "version": settings.APP_VERSION}


@app.get("/health", tags=["health"])
def health_check():
    """Health endpoint to verify that the service is working."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
    )
