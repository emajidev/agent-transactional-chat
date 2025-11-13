from typing import Generic, TypeVar, Type, List, Optional, Dict, Any, TYPE_CHECKING, Union
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker, Query
from sqlalchemy.orm.query import Query as QueryType
from src.configuration.config import settings

if TYPE_CHECKING:
    from src.common.dtos.filter_pagination import FilterPaginationQuery, StandardPageDto

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            echo=settings.DEBUG
        )
    return _engine

_Session = None

def get_session():
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _Session()

Base = declarative_base()

ModelType = TypeVar("ModelType")

session_context_var: ContextVar[Optional[Session]] = ContextVar("db_session", default=None)


def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()


class TransactionalMetaclass(type):
    
    def __new__(cls, name: str, bases: tuple, attrs: Dict[str, Any]) -> Type:
        cls.apply_transactional_wrapper(attrs)
        new_class = super().__new__(cls, name, bases, attrs)
        cls.set_model_attribute(new_class, bases)
        return new_class
    
    @classmethod
    def apply_transactional_wrapper(cls, attrs: Dict[str, Any]) -> None:
        transactional_prefixes = (
            "find",
            "create",
            "delete",
        )
        
        for attr_name, attr_value in attrs.items():
            if callable(attr_value) and any(
                attr_name.startswith(prefix) for prefix in transactional_prefixes
            ):
                attrs[attr_name] = cls.add_transactional(attr_value)
    
    @staticmethod
    def add_transactional(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with transaction():
                return func(*args, **kwargs)
        return wrapper
    
    @staticmethod
    def set_model_attribute(new_class: Type, bases: tuple) -> None:
        for base in bases:
            if hasattr(base, 'model') and base.model is not None:
                if not hasattr(new_class, 'model') or new_class.model is None:
                    new_class.model = base.model
                break


@contextmanager
def transaction():
    session = session_context_var.get()
    if session is None:
        session = get_session()
        session_context_var.set(session)
    
    is_nested = session.in_transaction()
    
    try:
        if is_nested:
            savepoint = session.begin_nested()
            yield savepoint
        else:
            session.begin()
            yield session
        
        if is_nested:
            savepoint.commit()
        else:
            session.commit()
            session.close()
    except Exception as e:
        if is_nested:
            savepoint.rollback()
        else:
            session.rollback()
            session.close()
        raise
    finally:
        if not is_nested:
            session_context_var.set(None)


def transactional(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        with transaction():
            return func(*args, **kwargs)
    return wrapper


class BaseRepository(Generic[ModelType], metaclass=TransactionalMetaclass):
    
    model: Optional[Type[ModelType]] = None
    
    @property
    def session(self) -> Session:
        session = session_context_var.get()
        if session is None:
            raise RuntimeError("There is no session available in the context. Use the context manager 'transaction()' or the decorator '@transactional'.")
        return session
    
    def get_by_id(self, id: int) -> Optional[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        id_column = getattr(self.model, 'id', None)
        if id_column is None:
            raise AttributeError(f"Model {self.model.__name__} does not have an 'id' attribute")
        return self.session.query(self.model).filter(id_column == id).first()
    
    def get_all(
        self, 
        skip: int = 0, 
        limit: int = 100,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        query = self.session.query(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.offset(skip).limit(limit).all()
    
    def create(self, obj: ModelType) -> ModelType:
        self.session.add(obj)
        self.session.flush()
        self.session.refresh(obj)
        return obj
    
    def update(self, instance: ModelType, data: Dict[str, Any]) -> ModelType:
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
            else:
                raise AttributeError(f"{type(instance).__name__} has no attribute '{key}'")
        
        self.session.flush()
        return instance
    
    def delete(self, obj: ModelType) -> None:
        self.session.delete(obj)
        self.session.flush()
    
    def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        query = self.session.query(self.model)
        
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.count()
    
    def exists(self, id: int) -> bool:
        return self.get_by_id(id) is not None


class BasePostgresRepository(BaseRepository[ModelType]):
    
    def __init__(self):
        if self.model is None:
            raise RuntimeError("Model must be set in subclass")
        super().__init__()
    
    def create(self, data: Union[ModelType, Dict[str, Any]]) -> ModelType:
        if isinstance(data, dict):
            if self.model is None:
                raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
            entity = self.model(**data)
        else:
            entity = data
        
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity
    
    def find_one(self, filter: Union[str, Dict[str, Any], None] = None) -> Optional[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        
        where = self._parse_filter_to_where(filter)
        query = self.session.query(self.model)
        
        for key, value in where.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        return query.first()
    
    def find_one_and_update(
        self,
        filter: Union[str, Dict[str, Any]],
        data: Dict[str, Any]
    ) -> Optional[ModelType]:
        entity = self.find_one(filter)
        if not entity:
            return None
        
        return self.update(entity, data)
    
    def find_by_id_and_update(self, id: int, data: Dict[str, Any]) -> ModelType:
        entity = self.get_by_id(id)
        if not entity:
            raise ValueError("Entity not found")
        
        return self.update(entity, data)
    
    def find_by_id(self, id: int) -> Optional[ModelType]:
        return self.get_by_id(id)
    
    def find_by_id_and_remove(self, id: int) -> Optional[ModelType]:
        entity = self.get_by_id(id)
        if not entity:
            return None
        
        if hasattr(entity, 'deleted_at'):
            setattr(entity, 'deleted_at', None)
        elif hasattr(entity, 'is_deleted'):
            setattr(entity, 'is_deleted', True)
        else:
            self.delete(entity)
            return entity
        
        self.session.flush()
        return entity
    
    def soft_delete(self, id: int) -> Optional[ModelType]:
        return self.find_by_id_and_remove(id)
    
    def hard_delete(self, id: int) -> Optional[ModelType]:
        entity = self.get_by_id(id)
        if not entity:
            return None
        
        return self.soft_delete(id)
    
    def find(self, filter: Optional[Dict[str, Any]] = None) -> List[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        
        query = self.session.query(self.model)
        
        if filter:
            for key, value in filter.items():
                if hasattr(self.model, key):
                    query = query.filter(getattr(self.model, key) == value)
        
        return query.all()
    
    def paginate(self, filter_paginate: Union['FilterPaginationQuery', Any]) -> List[ModelType]:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        
        where = self._parse_filter_to_where(filter_paginate.filter)
        order = self._parse_sort_to_order(filter_paginate.sort)
        
        skip = (filter_paginate.page - 1) * filter_paginate.limit
        take = filter_paginate.limit
        
        query = self.session.query(self.model)
        
        for key, value in where.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        
        for key, direction in order.items():
            if hasattr(self.model, key):
                if direction == 'ASC':
                    query = query.order_by(getattr(self.model, key).asc())
                else:
                    query = query.order_by(getattr(self.model, key).desc())
        
        if filter_paginate.fields:
            fields = self._parse_fields_to_select(filter_paginate.fields)
            for field in order.keys():
                if field not in fields:
                    fields.append(field)
        
        return query.offset(skip).limit(take).all()
    
    def find_all_paginate(self, filter: Union['FilterPaginationQuery', Any]) -> Union['StandardPageDto', Any]:
        from src.common.dtos.filter_pagination import StandardPageDto
        
        data = self.paginate(filter)
        total = self.count(self._parse_filter_to_where(filter.filter))
        
        return StandardPageDto(data, filter.limit, filter.page, total)
    
    def create_query_builder(self, alias: Optional[str] = None) -> QueryType:
        if self.model is None:
            raise RuntimeError("Model not set. Subclasses must define the 'model' attribute.")
        
        query = self.session.query(self.model)
        return query
    
    def _parse_filter_to_where(self, filter: Union[str, Dict[str, Any], None] = None) -> Dict[str, Any]:
        if filter is None:
            return {}
        
        if isinstance(filter, str):
            try:
                import json
                return json.loads(filter) if filter else {}
            except json.JSONDecodeError:
                raise ValueError("Invalid filter format")
        elif isinstance(filter, dict):
            if 'where' in filter:
                return filter['where']
            else:
                return filter
        
        return {}
    
    def _parse_sort_to_order(self, sort: Optional[Dict[str, int]] = None) -> Dict[str, str]:
        if not sort:
            return {}
        
        order: Dict[str, str] = {}
        for key, value in sort.items():
            order[key] = 'ASC' if value == 1 else 'DESC'
        
        return order
    
    def _parse_fields_to_select(self, fields: str) -> List[str]:
        return [field.strip() for field in fields.split(',') if field.strip()]
