"""Task and TaskLog repositories."""

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models.database.task import Task, TaskLog

from .base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    """Repository for Task operations."""

    def __init__(self, session: Session):
        super().__init__(Task, session)

    def get_by_status(self, status: str) -> list[Task]:
        """
        Get tasks by status.

        Args:
            status: Task status

        Returns:
            list of tasks with given status
        """
        return list(self.session.scalars(
            select(Task)
            .where(Task.status == status)
            .order_by(Task.created_at.desc())
        ))

    def get_by_collection(self, collection_id: str) -> list[Task]:
        """
        Get tasks by collection ID.

        Args:
            collection_id: Collection ID

        Returns:
            list of tasks for the collection
        """
        return list(self.session.scalars(
            select(Task)
            .where(Task.collection_id == collection_id)
            .order_by(Task.created_at.desc())
        ))

    def get_by_type_and_status(self, task_type: str, status: str) -> list[Task]:
        """
        Get tasks by type and status.

        Args:
            task_type: Task type
            status: Task status

        Returns:
            list of matching tasks
        """
        return list(self.session.scalars(
            select(Task).where(
                Task.type == task_type,
                Task.status == status
            ).order_by(Task.created_at.desc())
        ))

    def update_progress(self, task_id: str, progress: int, stats: Optional[str] = None) -> bool:
        """
        Update task progress.

        Args:
            task_id: Task ID
            progress: Progress percentage (0-100)
            stats: Optional stats JSON string

        Returns:
            True if updated, False if task not found
        """
        task = self.get_by_id(task_id)
        if not task:
            return False

        task.progress_percentage = progress
        if stats is not None:
            task.stats = stats

        self.session.commit()
        return True

    def mark_started(self, task_id: str) -> bool:
        """
        Mark task as started.

        Args:
            task_id: Task ID

        Returns:
            True if updated, False if task not found
        """
        task = self.get_by_id(task_id)
        if not task:
            return False

        task.status = "processing"
        task.started_at = datetime.utcnow()

        self.session.commit()
        return True

    def mark_completed(self, task_id: str, success: bool, error_message: Optional[str] = None) -> bool:
        """
        Mark task as completed.

        Args:
            task_id: Task ID
            success: Whether task succeeded
            error_message: Error message if failed

        Returns:
            True if updated, False if task not found
        """
        task = self.get_by_id(task_id)
        if not task:
            return False

        task.status = "success" if success else "failed"
        task.completed_at = datetime.utcnow()
        task.progress_percentage = 100 if success else task.progress_percentage

        if error_message:
            task.error_message = error_message

        self.session.commit()
        return True

    def get_active_tasks(self) -> list[Task]:
        """
        Get all active (pending/processing) tasks.

        Returns:
            list of active tasks
        """
        return list(self.session.scalars(
            select(Task).where(
                Task.status.in_(["pending", "processing"])
            ).order_by(Task.created_at.desc())
        ))


class TaskLogRepository(BaseRepository[TaskLog]):
    """Repository for TaskLog operations."""

    def __init__(self, session: Session):
        super().__init__(TaskLog, session)

    def get_by_task(
        self,
        task_id: str,
        level: Optional[str] = None,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> list[TaskLog]:
        """
        Get logs by task ID.

        Args:
            task_id: Task ID
            level: Optional log level filter
            offset: Offset for pagination
            limit: Limit for pagination

        Returns:
            list of task logs
        """
        query = select(TaskLog).where(TaskLog.task_id == task_id)

        if level:
            query = query.where(TaskLog.level == level)

        query = query.order_by(TaskLog.timestamp.desc()).offset(offset)

        if limit:
            query = query.limit(limit)

        return list(self.session.scalars(query))

    def add_log(
        self,
        task_id: str,
        level: str,
        message: str,
        details: Optional[str] = None
    ) -> TaskLog:
        """
        Add a log entry.

        Args:
            task_id: Task ID
            level: Log level
            message: Log message
            details: Optional details JSON

        Returns:
            Created task log
        """
        log = TaskLog(
            task_id=task_id,
            level=level,
            message=message,
            details=details or "{}"
        )

        self.session.add(log)
        self.session.commit()
        self.session.refresh(log)

        return log

    def count_by_task(self, task_id: str, level: Optional[str] = None) -> int:
        """
        Count logs by task.

        Args:
            task_id: Task ID
            level: Optional log level filter

        Returns:
            Log count
        """
        query = select(func.count(TaskLog.id)).where(TaskLog.task_id == task_id)

        if level:
            query = query.where(TaskLog.level == level)

        return self.session.scalar(query) or 0

    def delete_old_logs(self, days: int = 30) -> int:
        """
        Delete logs older than specified days.

        Args:
            days: Number of days to keep logs

        Returns:
            Number of deleted logs
        """
        from datetime import timedelta

        from sqlalchemy import delete

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = delete(TaskLog).where(TaskLog.timestamp < cutoff_date)
        result = self.session.execute(stmt)
        self.session.commit()

        return result.rowcount or 0
