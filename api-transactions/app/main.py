from fastapi import FastAPI
from configuration.config import settings
from modules.transactions.transactions.controller import router as transactions_router

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

# Incluir routers
app.include_router(transactions_router, prefix="/api/v1")


@app.get("/")
def root():
    """Endpoint raíz de la API."""
    return {
        "message": "Bienvenido a la API de Transacciones",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Endpoint de verificación de salud."""
    return {"status": "healthy"}
