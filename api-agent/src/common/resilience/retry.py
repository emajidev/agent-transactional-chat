"""
Módulo de retry para operaciones que pueden fallar temporalmente.
Usa tenacity para implementar estrategias de reintento con backoff exponencial.
"""
import logging
from collections.abc import Callable
from typing import TypeVar

from psycopg2 import OperationalError as Psycopg2OperationalError
from sqlalchemy.exc import DisconnectionError, OperationalError, TimeoutError
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Excepciones de base de datos que deben ser reintentadas
DB_RETRY_EXCEPTIONS = (
    OperationalError,
    DisconnectionError,
    TimeoutError,
    Psycopg2OperationalError,
    ConnectionError,
)


def retry_db_operation(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
):
    """
    Decorador para reintentar operaciones de base de datos que pueden fallar.

    Args:
        max_attempts: Número máximo de intentos (default: 3)
        initial_wait: Tiempo de espera inicial en segundos (default: 1.0)
        max_wait: Tiempo máximo de espera en segundos (default: 10.0)
        multiplier: Multiplicador para backoff exponencial (default: 2.0)

    Returns:
        Decorador que envuelve la función con lógica de retry
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=multiplier,
            min=initial_wait,
            max=max_wait,
        ),
        retry=retry_if_exception_type(DB_RETRY_EXCEPTIONS),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.ERROR),
        reraise=True,
    )


def retry_with_backoff(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 10.0,
    multiplier: float = 2.0,
    retry_exceptions: tuple = Exception,
):
    """
    Decorador genérico para reintentar cualquier operación con backoff exponencial.

    Args:
        max_attempts: Número máximo de intentos (default: 3)
        initial_wait: Tiempo de espera inicial en segundos (default: 1.0)
        max_wait: Tiempo máximo de espera en segundos (default: 10.0)
        multiplier: Multiplicador para backoff exponencial (default: 2.0)
        retry_exceptions: Tupla de excepciones que deben ser reintentadas

    Returns:
        Decorador que envuelve la función con lógica de retry
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(
            multiplier=multiplier,
            min=initial_wait,
            max=max_wait,
        ),
        retry=retry_if_exception_type(retry_exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        after=after_log(logger, logging.ERROR),
        reraise=True,
    )


def retry_on_failure(
    func: Callable[..., T],
    max_attempts: int = 3,
    exceptions: tuple = Exception,
) -> T:
    """
    Función helper para ejecutar una función con retry.

    Args:
        func: Función a ejecutar
        max_attempts: Número máximo de intentos
        exceptions: Excepciones que deben ser reintentadas

    Returns:
        Resultado de la función

    Raises:
        La última excepción si todos los intentos fallan
    """
    decorated = retry_with_backoff(
        max_attempts=max_attempts,
        retry_exceptions=exceptions,
    )(func)
    return decorated()


