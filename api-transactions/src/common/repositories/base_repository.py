from typing import Generic, TypeVar, Type, List, Optional, Dict, Any
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    model: Optional[Type[ModelType]] = None
    
    def __init__(self, session: Session):
        self.session = session
    
    def _ensure_model(self) -> Type[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        return self.model
    
    def _build_query(self, filters: Optional[Dict[str, Any]] = None):
        model = self._ensure_model()
        query = self.session.query(model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(model, key):
                    query = query.filter(getattr(model, key) == value)
        
        return query
    
    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        return self._build_query(filters).offset(skip).limit(limit).all()
    
    def create(self, entity: ModelType) -> ModelType:
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity
    
    def update(self, instance: ModelType, data: Dict[str, Any]) -> ModelType:
        for key, value in data.items():
            if not hasattr(instance, key):
                raise AttributeError(f"{type(instance).__name__} has no attribute '{key}'")
            setattr(instance, key, value)
        
        self.session.flush()
        return instance
    
    def delete(self, entity: ModelType) -> None:
        self.session.delete(entity)
        self.session.flush()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        return self._build_query(filters).count()
    
    
