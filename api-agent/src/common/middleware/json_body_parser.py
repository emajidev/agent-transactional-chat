"""Middleware para parsear el body JSON cuando viene como string."""
import json
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import Message

logger = logging.getLogger("uvicorn.error")


class JSONBodyParserMiddleware(BaseHTTPMiddleware):
    """Middleware que parsea el body JSON cuando viene como string."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Solo procesar métodos que pueden tener body
        if request.method in ("POST", "PUT", "PATCH"):
            # Leer el body
            body = await request.body()
            
            if body:
                try:
                    # Intentar parsear como JSON si es un string
                    body_str = body.decode("utf-8")
                    
                    # Si el body es un string que parece JSON, parsearlo y reemplazarlo
                    if body_str.strip().startswith("{") or body_str.strip().startswith("["):
                        try:
                            # Intentar parsear el JSON
                            parsed_body = json.loads(body_str)
                            
                            # Crear un nuevo body con el JSON parseado (sin espacios extra)
                            new_body = json.dumps(parsed_body, separators=(",", ":")).encode("utf-8")
                            
                            # Reemplazar el método _receive para devolver el nuevo body
                            original_receive = request._receive
                            
                            async def receive() -> Message:
                                if hasattr(request, "_body_parsed"):
                                    return await original_receive()
                                request._body_parsed = True
                                return {
                                    "type": "http.request",
                                    "body": new_body,
                                }
                            
                            request._receive = receive
                            
                            # Asegurar que el Content-Type sea application/json
                            if "content-type" not in request.headers:
                                request.headers.__dict__["_list"].append(
                                    (b"content-type", b"application/json")
                                )
                            elif "application/json" not in request.headers.get("content-type", "").lower():
                                # Agregar o reemplazar Content-Type
                                new_headers = list(request.headers.raw)
                                # Remover el header content-type existente si existe
                                new_headers = [
                                    (k, v) for k, v in new_headers 
                                    if k.lower() != b"content-type"
                                ]
                                new_headers.append((b"content-type", b"application/json"))
                                request.scope["headers"] = new_headers
                                
                        except (json.JSONDecodeError, ValueError) as e:
                            # Si no se puede parsear, dejar el body como está
                            logger.debug(f"No se pudo parsear el body como JSON: {e}")
                            pass
                            
                except (UnicodeDecodeError, AttributeError) as e:
                    # Si hay error al decodificar, dejar el body como está
                    logger.debug(f"Error al decodificar el body: {e}")
                    pass

        response = await call_next(request)
        return response

