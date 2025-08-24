"""Settings repository for system configuration."""

import json
from typing import Any, Optional

from sqlalchemy import select

from database.connection import session_context
from models.database.settings import Settings
from models.dto import SettingsDTO
from repository.base import BaseRepository


class SettingsRepository(BaseRepository[Settings, SettingsDTO]):
    """Repository for Settings operations."""

    def __init__(self):
        super().__init__(Settings, SettingsDTO)

    def exists(self, entity_id: str) -> bool:
        from sqlalchemy import func, select
        with session_context() as session:
            query = select(func.count(Settings.key)).where(Settings.key == entity_id)
            return (session.scalar(query) or 0) > 0

    def get_by_category(self, category: str) -> list[SettingsDTO]:
        with session_context() as session:
            entities = session.scalars(
                select(Settings)
                .where(Settings.category == category)
                .order_by(Settings.key)
            )
            return [self.dto_class.from_orm(item) for item in entities]

    def get_value(self, key: str, default: Any = None) -> Any:
        setting = self.get_by_id(key)
        if not setting:
            return default

        # Convert value based on type
        if setting.value_type == "json":
            try:
                return json.loads(setting.value)
            except json.JSONDecodeError:
                return default
        elif setting.value_type == "number":
            try:
                return float(setting.value) if "." in setting.value else int(setting.value)
            except ValueError:
                return default
        elif setting.value_type == "boolean":
            return setting.value.lower() in ("true", "1", "yes", "on")
        else:
            return setting.value

    def set_value(self, key: str, value: Any, value_type: str = "string") -> SettingsDTO:
        # Convert value to string
        if value_type == "json":
            str_value = json.dumps(value)
        elif value_type == "boolean":
            str_value = "true" if value else "false"
        else:
            str_value = str(value)

        with session_context() as session:
            # Get existing setting or create new one
            setting = session.get(self.model, key)
            if setting:
                setting.value = str_value
                setting.value_type = value_type
                session.flush()
                session.refresh(setting)
            else:
                setting = Settings(
                    key=key,
                    value=str_value,
                    value_type=value_type
                )
                session.add(setting)
                session.flush()
                session.refresh(setting)

        return self.dto_class.from_orm(setting)

    def get_sensitive_settings(self) -> list[SettingsDTO]:
        with session_context() as session:
            sql = select(Settings).where(Settings.is_sensitive == True)
            return [self.dto_class.from_orm(item) for item in session.scalars(sql)]

    def get_masked_settings(self) -> dict[str, dict[str, Any]]:
        all_settings = self.get_all()
        result = {}

        for setting in all_settings:
            if setting.category not in result:
                result[setting.category] = {}

            # Mask sensitive values
            if setting.is_sensitive and setting.value:
                masked_value = "***MASKED***"
                result[setting.category][setting.key] = {
                    "value": masked_value,
                    "type": setting.value_type,
                    "description": setting.description,
                    "is_sensitive": setting.is_sensitive,
                    "api_key_masked": True
                }
            else:
                # Get actual value
                actual_value = self.get_value(setting.key)
                result[setting.category][setting.key] = {
                    "value": actual_value,
                    "type": setting.value_type,
                    "description": setting.description,
                    "is_sensitive": setting.is_sensitive,
                    "api_key_masked": False
                }

        return result

    def update_multiple(self, updates: dict[str, Any]) -> list[SettingsDTO]:
        updated_settings = []

        for key, value in updates.items():
            # Determine value type
            if isinstance(value, bool):
                value_type = "boolean"
            elif isinstance(value, (int, float)):
                value_type = "number"
            elif isinstance(value, (dict, list)):
                value_type = "json"
            else:
                value_type = "string"

            setting = self.set_value(key, value, value_type)
            updated_settings.append(setting)

        return updated_settings

    def initialize_defaults(self, default_settings: list[dict[str, Any]]) -> None:
        with session_context() as session:
            for setting_data in default_settings:
                key = setting_data["key"]

                # Only create if not exists
                if not self.exists(key):
                    setting = Settings(**setting_data)
                    session.add(setting)

    def get_config_dict(self, category: Optional[str] = None) -> dict[str, Any]:
        if category:
            settings = self.get_by_category(category)
        else:
            settings = self.get_all()

        return {setting.key: self.get_value(setting.key) for setting in settings}
