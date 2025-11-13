import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.configuration.config import settings
from src.modules.transactions.controller import router 

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


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    
    uvicorn.run(
        "src.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )

