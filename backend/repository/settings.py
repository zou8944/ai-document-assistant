"""Settings repository for system configuration."""

import json
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.database.settings import Settings

from .base import BaseRepository


class SettingsRepository(BaseRepository[Settings]):
    """Repository for Settings operations."""

    def __init__(self, session: Session):
        super().__init__(Settings, session)

    def exists(self, entity_id: str) -> bool:
        """
        Check if setting exists by key.

        Args:
            key: Setting key

        Returns:
            True if exists, False otherwise
        """
        from sqlalchemy import func, select
        query = select(func.count(Settings.key)).where(Settings.key == entity_id)
        return (self.session.scalar(query) or 0) > 0

    def get_by_category(self, category: str) -> list[Settings]:
        """
        Get settings by category.

        Args:
            category: Settings category

        Returns:
            list of settings in the category
        """
        return list(self.session.scalars(
            select(Settings)
            .where(Settings.category == category)
            .order_by(Settings.key)
        ))

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get setting value by key.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
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

    def set_value(self, key: str, value: Any, value_type: str = "string") -> Settings:
        """
        Set setting value by key.

        Args:
            key: Setting key
            value: Setting value
            value_type: Value type (string, json, number, boolean)

        Returns:
            Updated or created setting
        """
        # Convert value to string
        if value_type == "json":
            str_value = json.dumps(value)
        elif value_type == "boolean":
            str_value = "true" if value else "false"
        else:
            str_value = str(value)

        # Get existing setting or create new one
        setting = self.get_by_id(key)
        if setting:
            setting.value = str_value
            setting.value_type = value_type
            self.session.commit()
            self.session.refresh(setting)
        else:
            setting = Settings(
                key=key,
                value=str_value,
                value_type=value_type
            )
            self.session.add(setting)
            self.session.commit()
            self.session.refresh(setting)

        return setting

    def get_sensitive_settings(self) -> list[Settings]:
        """
        Get all sensitive settings.

        Returns:
            list of sensitive settings
        """
        return list(self.session.scalars(
            select(Settings).where(Settings.is_sensitive == True)
        ))

    def get_masked_settings(self) -> dict[str, dict[str, Any]]:
        """
        Get all settings with sensitive values masked.

        Returns:
            Dictionary of categorized settings with masked sensitive values
        """
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

    def update_multiple(self, updates: dict[str, Any]) -> list[Settings]:
        """
        Update multiple settings at once.

        Args:
            updates: Dictionary of key-value pairs to update

        Returns:
            list of updated settings
        """
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
        """
        Initialize default settings if they don't exist.

        Args:
            default_settings: list of default setting dictionaries
        """
        for setting_data in default_settings:
            key = setting_data["key"]

            # Only create if not exists
            if not self.exists(key):
                setting = Settings(**setting_data)
                self.session.add(setting)

        self.session.commit()

    def get_config_dict(self, category: Optional[str] = None) -> dict[str, Any]:
        """
        Get settings as a simple key-value dictionary.

        Args:
            category: Optional category filter

        Returns:
            Dictionary of setting key-value pairs
        """
        if category:
            settings = self.get_by_category(category)
        else:
            settings = self.get_all()

        return {setting.key: self.get_value(setting.key) for setting in settings}
