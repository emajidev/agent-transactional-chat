from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, event
from sqlalchemy.ext.declarative import declared_attr


class SoftDeleteMixin:
    @declared_attr
    def deleted_at(cls):
        return Column(DateTime(timezone=True), nullable=True, default=None)

    def soft_delete(self):
        self.deleted_at = datetime.now(UTC)


def setup_soft_delete_listeners():
    from sqlalchemy.orm import Session

    @event.listens_for(Session, "before_flush")
    def receive_before_flush(session: Session, _flush_context, _instances):
        for instance in list(session.deleted):
            if hasattr(instance, "deleted_at"):
                instance.soft_delete()
                session.expunge(instance)
                session.add(instance)
