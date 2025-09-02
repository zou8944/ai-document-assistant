"""Base repository class with common CRUD operations."""

from typing import Any, Generic, Optional, TypeVar

from sqlalchemy import delete, func, select, update

from database.base import Base
from database.connection import session_context
from models.dto import DTOConvertible

T = TypeVar("T", bound=Base)
D = TypeVar("D", bound=DTOConvertible)


class BaseRepository(Generic[T, D]):
    """Base repository class with common CRUD operations."""

    def __init__(self, model: type[T], dto_class: type[D]):
        self.model = model
        self.dto_class = dto_class

    def create_by_field(self, **kwargs) -> D:
        entity = self.model(**kwargs)

        with session_context() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)

            return self.dto_class.from_orm(entity)

    def create_by_model(self, dto: D) -> D:
        entity = dto.to_orm(self.model)

        with session_context() as session:
            session.add(entity)
            session.flush()
            session.refresh(entity)

            return self.dto_class.from_orm(entity)

    def get_by_id(self, entity_id: Any) -> Optional[D]:
        with session_context() as session:
            entity = session.get(self.model, entity_id)
            if entity is None:
                return None
            return self.dto_class.from_orm(entity)

    def get_all(
        self, offset: int = 0, limit: Optional[int] = None, order_by: Optional[str] = None
    ) -> list[D]:
        with session_context() as session:
            query = select(self.model).offset(offset)

            if limit is not None:
                query = query.limit(limit)

            if order_by:
                if hasattr(self.model, order_by):
                    query = query.order_by(getattr(self.model, order_by))

            return [self.dto_class.from_orm(item) for item in session.scalars(query)]

    def update(self, entity_id: Any, **kwargs) -> Optional[D]:
        with session_context() as session:
            stmt = update(self.model).where(self.model.id == entity_id).values(**kwargs)  # type: ignore
            result = session.execute(stmt)

        if result.rowcount == 0:
            return None

        return self.get_by_id(entity_id)

    def update_by_model(self, entity: D) -> Optional[D]:
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

    def find_by(self, **filters) -> list[D]:
        with session_context() as session:
            query = select(self.model)

            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

            return [self.dto_class.from_orm(item) for item in session.scalars(query)]

    def find_one_by(self, **filters) -> Optional[D]:
        with session_context() as session:
            query = select(self.model)

            for field, value in filters.items():
                if hasattr(self.model, field):
                    query = query.where(getattr(self.model, field) == value)

            entity = session.scalar(query)
            if entity is None:
                return None
            return self.dto_class.from_orm(entity)
