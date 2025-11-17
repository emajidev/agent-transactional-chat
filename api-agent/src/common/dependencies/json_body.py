"""Dependency para parsear el body JSON cuando viene como string."""
import json
from typing import Any

from fastapi import Request, HTTPException, status


async def parse_json_body(request: Request) -> dict[str, Any]:
    """Parsea el body JSON, incluso si viene como string."""
    body = await request.body()
    
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Body vacío"
        )
    
    try:
        # Intentar decodificar como string
        body_str = body.decode("utf-8")
        
        # Si el body es un string que parece JSON, parsearlo
        if isinstance(body_str, str) and (body_str.strip().startswith("{") or body_str.strip().startswith("[")):
            try:
                return json.loads(body_str)
            except json.JSONDecodeError:
                # Si falla, intentar parsear el string como si fuera el JSON directamente
                # Esto maneja el caso donde el body es un string JSON
                try:
                    # Remover comillas externas si existen
                    cleaned = body_str.strip()
                    if cleaned.startswith('"') and cleaned.endswith('"'):
                        cleaned = cleaned[1:-1]
                        # Escapar comillas internas
                        cleaned = cleaned.replace('\\"', '"').replace('\\n', '\n').replace('\\r', '\r')
                    return json.loads(cleaned)
                except (json.JSONDecodeError, ValueError):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="El body no es un JSON válido"
                    )
        
        # Si no es un string JSON, intentar parsear directamente
        return json.loads(body_str)
        
    except (UnicodeDecodeError, AttributeError):
        # Si no se puede decodificar, intentar parsear como bytes
        try:
            return json.loads(body)
        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El body no es un JSON válido"
            )

