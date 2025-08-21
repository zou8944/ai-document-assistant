"""Base repository class with common CRUD operations."""

from typing import Any, Generic, Optional, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from database.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository class with common CRUD operations."""

    def __init__(self, model: type[T], session: Session):
        """
        Initialize repository.

        Args:
            model: SQLAlchemy model class
            session: Database session
        """
        self.model = model
        self.session = session

    def create_by_field(self, **kwargs) -> T:
        """
        Create a new entity.

        Args:
            **kwargs: Entity attributes

        Returns:
            Created entity
        """
        entity = self.model(**kwargs)
        self.session.add(entity)
        self.session.flush()
        return entity


    def create_by_model(self, entity: T) -> T:
        """
        Create a new entity by model instance.

        Args:
            entity: Entity instance

        Returns:
            Created entity
        """
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_by_id(self, entity_id: Any) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            Entity or None if not found
        """
        return self.session.get(self.model, entity_id)

    def get_all(
        self,
        offset: int = 0,
        limit: Optional[int] = None,
        order_by: Optional[str] = None
    ) -> list[T]:
        """
        Get all entities with pagination.

        Args:
            offset: Offset for pagination
            limit: Limit for pagination
            order_by: Order by field name

        Returns:
            list of entities
        """
        query = select(self.model).offset(offset)

        if limit is not None:
            query = query.limit(limit)

        if order_by:
            if hasattr(self.model, order_by):
                query = query.order_by(getattr(self.model, order_by))

        return list(self.session.scalars(query))

    def update(self, entity_id: Any, **kwargs) -> Optional[T]:
        """
        Update entity by ID.

        Args:
            entity_id: Entity ID
            **kwargs: Updated attributes

        Returns:
            Updated entity or None if not found
        """
        stmt = (
            update(self.model)
            .where(self.model.id == entity_id)
            .values(**kwargs)
        )
        result = self.session.execute(stmt)

        if result.rowcount == 0:
            return None

        return self.get_by_id(entity_id)

    def update_by_model(self, entity: T) -> Optional[T]:
        """
        Update entity by model instance.

        Args:
            entity: Entity instance with updated values

        Returns:
            Updated entity or None if not found
        """
        # 获取主键值
        entity_id = getattr(entity, 'id', None)
        if entity_id is None:
            return None

        # 将实体转为字典，排除主键
        update_data = {}
        for column in self.model.__table__.columns:
            if column.name != 'id':  # 排除主键
                value = getattr(entity, column.name, None)
                if value is not None:
                    update_data[column.name] = value

        return self.update(entity_id, **update_data)

    def delete(self, entity_id: Any) -> bool:
        """
        Delete entity by ID.

        Args:
            entity_id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        stmt = delete(self.model).where(self.model.id == entity_id)
        result = self.session.execute(stmt)

        if result.rowcount == 0:
            return False

        return True

    def count(self, **filters) -> int:
        """
        Count entities with optional filters.

        Args:
            **filters: Filter conditions

        Returns:
            Entity count
        """
        query = select(func.count(self.model.id))

        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        return self.session.scalar(query) or 0

    def exists(self, entity_id: Any) -> bool:
        """
        Check if entity exists by ID.

        Args:
            entity_id: Entity ID

        Returns:
            True if exists, False otherwise
        """
        query = select(func.count(self.model.id)).where(self.model.id == entity_id)
        return (self.session.scalar(query) or 0) > 0

    def find_by(self, **filters) -> list[T]:
        """
        Find entities by filters.

        Args:
            **filters: Filter conditions

        Returns:
            list of matching entities
        """
        query = select(self.model)

        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        return list(self.session.scalars(query))

    def find_one_by(self, **filters) -> Optional[T]:
        """
        Find one entity by filters.

        Args:
            **filters: Filter conditions

        Returns:
            First matching entity or None
        """
        query = select(self.model)

        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)

        return self.session.scalar(query)
