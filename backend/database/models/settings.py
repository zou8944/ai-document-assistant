"""Settings model for application configuration stored in database."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base


class Settings(Base):
    """Application settings model."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(
        String(20),
        default="string",
        server_default="'string'",
    )
    category: Mapped[str] = mapped_column(
        String(50),
        default="general",
        server_default="'general'",
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="''")
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'json', 'number', 'boolean')",
            name="chk_settings_value_type",
        ),
        CheckConstraint(
            "category IN ('general', 'llm', 'embedding', 'paths', 'crawler', "
            "'credentials', 'business', 'system', 'crawl', 'agent')",
            name="chk_settings_category",
        ),
        Index("idx_settings_category", "category"),
        Index("idx_settings_sensitive", "is_sensitive"),
    )

    def __repr__(self) -> str:
        return f"<Settings(key='{self.key}', category='{self.category}')>"
