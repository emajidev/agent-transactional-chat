from typing import Any, Generic, TypeVar

from sqlalchemy.orm import Session

from src.common.resilience import retry_db_operation

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    model: type[ModelType] | None = None

    def __init__(self, session: Session):
        self.session = session

    def _ensure_model(self) -> type[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        return self.model

    def _build_query(self, filters: dict[str, Any] | None = None):
        model = self._ensure_model()
        query = self.session.query(model)

        # Filtrar automáticamente los registros con deleted_at no nulo (soft delete)
        # El mixin SoftDeleteMixin ya maneja esto, pero mantenemos el filtro explícito por seguridad
        if hasattr(model, "deleted_at"):
            query = query.filter(model.deleted_at.is_(None))

        if filters:
            for key, value in filters.items():
                if hasattr(model, key):
                    query = query.filter(getattr(model, key) == value)

        return query

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def get_all(
        self, skip: int = 0, limit: int = 100, filters: dict[str, Any] | None = None
    ) -> list[ModelType]:
        return self._build_query(filters).offset(skip).limit(limit).all()

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def create(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def update(self, instance: ModelType, data: dict[str, Any]) -> ModelType:
        for key, value in data.items():
            if not hasattr(instance, key):
                raise AttributeError(f"{type(instance).__name__} has no attribute '{key}'")
            setattr(instance, key, value)

        self.session.flush()
        return instance

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def delete(self, entity: ModelType) -> None:
        """
        Elimina una entidad. Si tiene deleted_at, el trigger de PostgreSQL
        interceptará el DELETE y lo convertirá en UPDATE de deleted_at.
        Si no tiene deleted_at, se eliminará físicamente.
        """
        self.session.delete(entity)
        self.session.flush()

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def count(self, filters: dict[str, Any] | None = None) -> int:
        return self._build_query(filters).count()
