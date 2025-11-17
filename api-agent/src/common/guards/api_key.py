from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from src.configuration.config import settings

# Configurar el header donde se espera la API key
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Dependencia para verificar la API key en las peticiones.

    Args:
        api_key: API key extraída del header X-API-Key

    Returns:
        str: La API key si es válida

    Raises:
        HTTPException: Si la API key no es válida o no se proporciona
    """
    if not settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API Key no configurada en el servidor",
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key requerida. Proporciona la API key en el header 'X-API-Key'",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API Key inválida",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key


