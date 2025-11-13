from datetime import datetime, timezone
from sqlalchemy import event, Column, DateTime
from sqlalchemy.ext.declarative import declared_attr


class SoftDeleteMixin:
    
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True, default=None)
    
    def soft_delete(self):
        self.deleted_at = datetime.now(timezone.utc)


def setup_soft_delete_listeners():
    from sqlalchemy.orm import Session
    
    @event.listens_for(Session, 'before_flush')
    def receive_before_flush(session: Session, flush_context, instances):
        
        for instance in list(session.deleted):
            if hasattr(instance, 'deleted_at'):
                instance.soft_delete()
                session.expunge(instance)
                session.add(instance)



