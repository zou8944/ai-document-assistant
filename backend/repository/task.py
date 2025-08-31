"""Task and TaskLog repositories."""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from database.connection import session_context
from models.database.task import Task, TaskLog
from models.dto import TaskDTO, TaskLogDTO
from repository.base import BaseRepository


class TaskRepository(BaseRepository[Task, TaskDTO]):
    """Repository for Task operations."""

    def __init__(self):
        super().__init__(Task, TaskDTO)

    def get_by_status(self, status: str) -> list[TaskDTO]:
        with session_context() as session:
            entities = session.scalars(
                select(Task)
                .where(Task.status == status)
                .order_by(Task.created_at.desc())
            )
            return [self.dto_class.from_orm(item) for item in entities]

    def get_by_collection(self, collection_id: str) -> list[TaskDTO]:
        with session_context() as session:
            entities = session.scalars(
                select(Task)
                .where(Task.collection_id == collection_id)
                .order_by(Task.created_at.desc())
            )
            return [self.dto_class.from_orm(item) for item in entities]

    def get_by_type_and_status(self, task_type: str, status: str) -> list[TaskDTO]:
        with session_context() as session:
            entities = session.scalars(
                select(Task).where(
                    Task.type == task_type,
                    Task.status == status
                ).order_by(Task.created_at.desc())
            )
            return [self.dto_class.from_orm(item) for item in entities]

    def update_progress(self, task_id: str, progress: int, stats: Optional[str] = None) -> bool:
        with session_context() as session:
            task = session.get(Task, task_id)
            if not task:
                return False

            task.progress_percentage = progress
            if stats is not None:
                task.stats = stats
            session.flush()
            return True

    def mark_started(self, task_id: str) -> bool:
        with session_context() as session:
            task = session.get(Task, task_id)
            if not task:
                return False

            task.status = "processing"
            task.started_at = datetime.utcnow()
            session.flush()
            return True

    def mark_completed(self, task_id: str, success: bool, error_message: Optional[str] = None) -> bool:
        with session_context() as session:
            task = session.get(Task, task_id)
            if not task:
                return False

            task.status = "success" if success else "failed"
            task.completed_at = datetime.utcnow()
            task.progress_percentage = 100 if success else task.progress_percentage

            if error_message:
                task.error_message = error_message

            session.flush()
            return True

    def mark_cancelled(self, task_id: str) -> bool:
        with session_context() as session:
            task = session.get(Task, task_id)
            if not task:
                return False

            if task.status not in ["pending", "processing"]:
                return False

            task.status = "cancelled"
            session.flush()
            return True

    def get_active_tasks(self) -> list[TaskDTO]:
        with session_context() as session:
            entities = session.scalars(
                select(Task).where(
                    Task.status.in_(["pending", "processing"])
                ).order_by(Task.created_at.desc())
            )
            return [self.dto_class.from_orm(item) for item in entities]

    def list_tasks_with_filters(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        collection_id: Optional[str] = None,
        offset: int = 0,
        limit: int = 50
    ) -> list[TaskDTO]:
        with session_context() as session:
            query = select(Task)

            if status:
                query = query.where(Task.status == status)
            if task_type:
                query = query.where(Task.type == task_type)
            if collection_id:
                query = query.where(Task.collection_id == collection_id)

            query = query.order_by(Task.created_at.desc()).offset(offset).limit(limit)

            return [self.dto_class.from_orm(item) for item in session.scalars(query)]

    def count_tasks_with_filters(
        self,
        status: Optional[str] = None,
        task_type: Optional[str] = None,
        collection_id: Optional[str] = None
    ) -> int:
        with session_context() as session:
            query = select(func.count(Task.id))

            if status:
                query = query.where(Task.status == status)
            if task_type:
                query = query.where(Task.type == task_type)
            if collection_id:
                query = query.where(Task.collection_id == collection_id)

            return session.scalar(query) or 0


class TaskLogRepository(BaseRepository[TaskLog, TaskLogDTO]):
    """Repository for TaskLog operations."""

    def __init__(self):
        super().__init__(TaskLog, TaskLogDTO)

    def list_by_task(
        self,
        task_id: str,
        level: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[TaskLogDTO]:
        with session_context() as session:
            query = select(TaskLog).where(TaskLog.task_id == task_id)

            if level:
                query = query.where(TaskLog.level == level)

            query = query.order_by(TaskLog.timestamp).offset(offset)

            if limit:
                query = query.limit(limit)

            return [self.dto_class.from_orm(item) for item in session.scalars(query)]

    def add_log(
        self,
        task_id: str,
        level: str,
        message: str,
        details: Optional[str] = None
    ) -> TaskLogDTO:
        with session_context() as session:
            log = TaskLog(
                task_id=task_id,
                level=level,
                message=message,
                details=details or "{}"
        )

            session.add(log)
            session.flush()  # To get ID populated
            session.refresh(log)

            return self.dto_class.from_orm(log)

    def count_by_task(self, task_id: str, level: Optional[str] = None) -> int:
        with session_context() as session:
            query = select(func.count(TaskLog.id)).where(TaskLog.task_id == task_id)

            if level:
                query = query.where(TaskLog.level == level)

            return session.scalar(query) or 0

    def delete_old_logs(self, days: int = 30) -> int:
        from datetime import timedelta

        from sqlalchemy import delete

        with session_context() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            stmt = delete(TaskLog).where(TaskLog.timestamp < cutoff_date)
            result = session.execute(stmt)

        return result.rowcount or 0
