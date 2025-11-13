"""
Mixin para agregar funcionalidad de soft delete a modelos SQLAlchemy.
Usa eventos de SQLAlchemy para interceptar DELETE y convertirlos en UPDATE de deleted_at.
"""
from datetime import datetime, timezone
from sqlalchemy import event, Column, DateTime
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import declared_attr


class SoftDeleteMixin:
    """
    Mixin que agrega soft delete a un modelo SQLAlchemy.
    
    Uso:
        class MyModel(Base, SoftDeleteMixin):
            __tablename__ = 'my_table'
            # ... otros campos
    """
    
    @declared_attr
    def deleted_at(cls):
        """Campo deleted_at para soft delete"""
        return Column(DateTime(timezone=True), nullable=True, default=None)
    
    def soft_delete(self):
        """Marca el registro como eliminado"""
        self.deleted_at = datetime.now(timezone.utc)
    
    def restore(self):
        """Restaura un registro eliminado"""
        self.deleted_at = None
    
    @property
    def is_deleted(self) -> bool:
        """Verifica si el registro está eliminado"""
        return self.deleted_at is not None


def setup_soft_delete_listeners():
    """
    Configura los event listeners de SQLAlchemy para manejar soft delete.
    Debe llamarse una vez al inicio de la aplicación.
    """
    from sqlalchemy.orm import Session
    
    @event.listens_for(Session, 'before_flush')
    def receive_before_flush(session: Session, flush_context, instances):
        """
        Intercepta los DELETE antes de que se ejecuten y los convierte en UPDATE.
        """
        # Convertir DELETE en UPDATE para soft delete
        for instance in list(session.deleted):
            # Verificar si el modelo tiene deleted_at (usa SoftDeleteMixin)
            if hasattr(instance, 'deleted_at'):
                # Marcar como eliminado
                instance.soft_delete()
                # Remover de la lista de eliminados
                session.expunge(instance)
                # Agregar a la sesión como modificado (para que se haga UPDATE)
                session.add(instance)



