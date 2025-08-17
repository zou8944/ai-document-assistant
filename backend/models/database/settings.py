"""Settings model for system configuration."""

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from database.base import Base


class Settings(Base):
    """Settings model for system configuration."""

    __tablename__ = "settings"

    # Primary key
    key: Mapped[str] = mapped_column(
        String(100),
        primary_key=True,
        doc="Setting key name"
    )

    # Value and type
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Setting value (JSON or string)"
    )
    value_type: Mapped[str] = mapped_column(
        String(20),
        default="string",
        server_default="'string'",
        doc="Value type (string, json, number, boolean)"
    )

    # Categorization
    category: Mapped[str] = mapped_column(
        String(50),
        default="general",
        server_default="'general'",
        doc="Setting category"
    )
    description: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default="''",
        doc="Setting description"
    )

    # Security
    is_sensitive: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        doc="Whether this is sensitive information"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        doc="Creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        doc="Last update timestamp"
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "value_type IN ('string', 'json', 'number', 'boolean')",
            name="chk_settings_value_type"
        ),
        CheckConstraint(
            "category IN ('general', 'llm', 'embedding', 'paths', 'crawler')",
            name="chk_settings_category"
        ),
        Index("idx_settings_category", "category"),
        Index("idx_settings_sensitive", "is_sensitive"),
    )

    def __repr__(self) -> str:
        return f"<Settings(key='{self.key}', category='{self.category}')>"
