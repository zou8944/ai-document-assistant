"""Base repository class with common CRUD operations."""

from typing import Any, Generic, Optional, TypeVar

from sqlalchemy import delete, func, select, update

from database.base import Base
from database.connection import session_context

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository class with common CRUD operations."""

    def __init__(self, model: type[T]):
        self.model = model

    def create_by_field(self, **kwargs) -> T:
        entity = self.model(**kwargs)
        with session_context() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)
        return entity

    def create_by_model(self, entity: T) -> T:
        with session_context() as session:
            session.add(entity)
            session.flush()
            return entity

    def get_by_id(self, entity_id: Any) -> Optional[T]:
        with session_context() as session:
            return session.get(self.model, entity_id)

    def get_all(self, offset: int = 0, limit: Optional[int] = None, order_by: Optional[str] = None) -> list[T]:
        with session_context() as session:
            query = select(self.model).offset(offset)

            if limit is not None:
                query = query.limit(limit)

            if order_by:
                if hasattr(self.model, order_by):
                    query = query.order_by(getattr(self.model, order_by))

            return list(session.scalars(query))

    def update(self, entity_id: Any, **kwargs) -> Optional[T]:
        with session_context() as session:
            stmt = update(self.model).where(self.model.id == entity_id).values(**kwargs) # type: ignore
            result = session.execute(stmt)

        if result.rowcount == 0:
            return None

        return self.get_by_id(entity_id)

    def update_by_model(self, entity: T) -> Optional[T]:
        # 获取主键值
        entity_id = getattr(entity, "id", None)
        if entity_id is None:
            return None

        # 将实体转为字典，排除主键
        update_data = {}
        for column in self.model.__table__.columns:
            if column.name != "id":  # 排除主键
                value = getattr(entity, column.name, None)
                if value is not None:
                    update_data[column.name] = value

        return self.update(entity_id, **update_data)

    def delete(self, entity_id: Any) -> bool:
        with session_context() as session:
            stmt = delete(self.model).where(self.model.id == entity_id)  # type: ignore
            result = session.execute(stmt)

        if result.rowcount == 0:
            return False

        return True

    def count(self, **filters) -> int:
        with session_context() as session:
            query = select(func.count(self.model.id))  # type: ignore

            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

            return session.scalar(query) or 0

    def exists(self, entity_id: Any) -> bool:
        with session_context() as session:
            query = select(func.count(self.model.id)).where(self.model.id == entity_id)  # type: ignore
            return (session.scalar(query) or 0) > 0

    def find_by(self, **filters) -> list[T]:
        with session_context() as session:
            query = select(self.model)

            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

        return list(session.scalars(query))

    def find_one_by(self, **filters) -> Optional[T]:
        with session_context() as session:
            query = select(self.model)

            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

        return session.scalar(query)
