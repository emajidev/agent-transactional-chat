"""
Módulo de circuit breaker para prevenir llamadas a servicios que están fallando.
Usa pybreaker para implementar el patrón circuit breaker.
"""
import logging
from functools import wraps
from typing import Callable, TypeVar, Any
from pybreaker import CircuitBreaker, CircuitBreakerError
from sqlalchemy.exc import OperationalError, DisconnectionError, TimeoutError
from psycopg2 import OperationalError as Psycopg2OperationalError

logger = logging.getLogger(__name__)

T = TypeVar("T")

DB_CIRCUIT_BREAKER_EXCEPTIONS = (
    OperationalError,
    DisconnectionError,
    TimeoutError,
    Psycopg2OperationalError,
    ConnectionError,
)

_db_circuit_breaker = CircuitBreaker(
    fail_max=5,  # Abre el circuito después de 5 fallos consecutivos
    timeout_duration=60,  # Mantiene abierto por 60 segundos
    expected_exception=DB_CIRCUIT_BREAKER_EXCEPTIONS,
    name="DatabaseCircuitBreaker",
)


def get_db_circuit_breaker() -> CircuitBreaker:
    return _db_circuit_breaker


def circuit_breaker(
    breaker: CircuitBreaker,
    fallback_func: Callable[[Exception], Any] = None,
):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            try:
                return breaker.call(func, *args, **kwargs)
            except CircuitBreakerError as e:
                logger.warning(
                    f"Circuit breaker abierto para {func.__name__}: {e}"
                )
                if fallback_func:
                    return fallback_func(e)
                raise
            except Exception as e:
                logger.error(
                    f"Error en {func.__name__}: {e}",
                    exc_info=True,
                )
                raise
        
        return wrapper
    return decorator


def db_circuit_breaker(
    fallback_func: Callable[[Exception], Any] = None,
):
    
    return circuit_breaker(_db_circuit_breaker, fallback_func)

