import json
import logging
from typing import Any

import redis
from redis.exceptions import ConnectionError, RedisError

from src.configuration.config import settings

logger = logging.getLogger(__name__)


class RedisService:
    """Servicio para interactuar con Redis"""

    def __init__(self):
        self.client: redis.Redis | None = None
        self._connect()

    def _connect(self):
        """Establece conexión con Redis"""
        try:
            self.client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
                db=settings.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Verificar conexión
            self.client.ping()
            logger.info("Conexión a Redis establecida exitosamente")
        except ConnectionError as e:
            logger.warning(f"No se pudo conectar a Redis: {str(e)}. Continuando sin caché.")
            self.client = None
        except Exception as e:
            logger.warning(f"Error inesperado al conectar con Redis: {str(e)}. Continuando sin caché.")
            self.client = None

    def _ensure_connection(self):
        """Asegura que la conexión esté activa"""
        if self.client is None:
            self._connect()
        elif not self._is_connected():
            self._connect()

    def _is_connected(self) -> bool:
        """Verifica si la conexión está activa"""
        if self.client is None:
            return False
        try:
            self.client.ping()
            return True
        except (ConnectionError, RedisError):
            return False

    def get(self, key: str) -> dict[str, Any] | None:
        """Obtiene un valor del caché"""
        try:
            self._ensure_connection()
            if self.client is None:
                return None

            value = self.client.get(key)
            if value is None:
                return None

            return json.loads(value)
        except (ConnectionError, RedisError, json.JSONDecodeError) as e:
            logger.warning(f"Error al obtener de Redis (key={key}): {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al obtener de Redis (key={key}): {str(e)}")
            return None

    def set(self, key: str, value: dict[str, Any], ttl: int | None = None) -> bool:
        """Guarda un valor en el caché"""
        try:
            self._ensure_connection()
            if self.client is None:
                return False

            json_value = json.dumps(value, ensure_ascii=False)
            ttl = ttl or settings.REDIS_TTL
            self.client.setex(key, ttl, json_value)
            return True
        except (ConnectionError, RedisError) as e:
            logger.warning(f"Error al guardar en Redis (key={key}): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al guardar en Redis (key={key}): {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """Elimina un valor del caché"""
        try:
            self._ensure_connection()
            if self.client is None:
                return False

            self.client.delete(key)
            return True
        except (ConnectionError, RedisError) as e:
            logger.warning(f"Error al eliminar de Redis (key={key}): {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado al eliminar de Redis (key={key}): {str(e)}")
            return False

    def exists(self, key: str) -> bool:
        """Verifica si una clave existe"""
        try:
            self._ensure_connection()
            if self.client is None:
                return False

            return bool(self.client.exists(key))
        except (ConnectionError, RedisError):
            return False

    def close(self):
        """Cierra la conexión con Redis"""
        if self.client is not None:
            try:
                self.client.close()
                logger.info("Conexión con Redis cerrada")
            except Exception as e:
                logger.error(f"Error al cerrar conexión con Redis: {str(e)}")


# Instancia global del servicio
_redis_service: RedisService | None = None


def get_redis_service() -> RedisService:
    """Obtiene la instancia global del servicio Redis"""
    global _redis_service
    if _redis_service is None:
        _redis_service = RedisService()
    return _redis_service

