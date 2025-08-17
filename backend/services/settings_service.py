"""
Settings management service.
"""

import logging
from typing import Any

from database.connection import get_db_session_context
from models.responses import SettingsResponse
from repository.settings import SettingsRepository

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing system settings"""

    def __init__(self, config=None):
        """Initialize settings service"""
        from config import get_config

        self.config = config or get_config()
        logger.info("SettingsService initialized successfully")

    def _format_settings_for_api(self, masked_settings: dict[str, dict[str, Any]]) -> SettingsResponse:
        """Format settings dictionary for API response"""

        # Extract settings by category with defaults
        llm_settings = masked_settings.get("llm", {})
        embedding_settings = masked_settings.get("embedding", {})
        paths_settings = masked_settings.get("paths", {})
        crawler_settings = masked_settings.get("crawler", {})
        text_settings = masked_settings.get("text", {}) or masked_settings.get("general", {})

        # Format LLM settings
        llm = {}
        for key, setting in llm_settings.items():
            if key.startswith("llm."):
                field_name = key.replace("llm.", "")
                if setting.get("is_sensitive") and setting.get("api_key_masked"):
                    llm[f"{field_name}_masked"] = True
                else:
                    llm[field_name] = setting.get("value", "")

        # Format embedding settings
        embedding = {}
        for key, setting in embedding_settings.items():
            if key.startswith("embedding."):
                field_name = key.replace("embedding.", "")
                if setting.get("is_sensitive") and setting.get("api_key_masked"):
                    embedding[f"{field_name}_masked"] = True
                else:
                    embedding[field_name] = setting.get("value", "")

        # Get data location (could be in paths category)
        data_location = ""
        for key, setting in paths_settings.items():
            if key == "paths.data_location":
                data_location = setting.get("value", "./data")
                break

        # Format other settings categories
        paths = {key.replace("paths.", ""): setting.get("value", "")
                for key, setting in paths_settings.items()
                if key.startswith("paths.") and key != "paths.data_location"}

        crawler = {key.replace("crawler.", ""): setting.get("value", "")
                  for key, setting in crawler_settings.items()
                  if key.startswith("crawler.")}

        text = {key.replace("text.", ""): setting.get("value", "")
               for key, setting in text_settings.items()
               if key.startswith("text.")}

        return SettingsResponse(
            llm=llm,
            embedding=embedding,
            data_location=data_location,
            paths=paths,
            crawler=crawler,
            text=text
        )

    async def get_settings(self) -> SettingsResponse:
        """Get all settings with sensitive values masked"""
        try:
            with get_db_session_context() as session:
                repo = SettingsRepository(session)
                masked_settings = repo.get_masked_settings()

                return self._format_settings_for_api(masked_settings)

        except Exception as e:
            logger.error(f"Failed to get settings: {e}")
            # Return default settings on error
            return SettingsResponse(
                llm={},
                embedding={},
                data_location="./data",
                paths={},
                crawler={},
                text={}
            )

    async def update_settings(self, updates: dict[str, Any]) -> SettingsResponse:
        """Update settings with new values"""
        try:
            with get_db_session_context() as session:
                repo = SettingsRepository(session)

                # Flatten updates to match database keys
                flattened_updates = {}

                for category, settings in updates.items():
                    if category == "data_location":
                        # Special handling for data_location
                        flattened_updates["paths.data_location"] = settings
                    elif isinstance(settings, dict):
                        # Category-based settings
                        for key, value in settings.items():
                            flattened_updates[f"{category}.{key}"] = value
                    else:
                        # Direct settings
                        flattened_updates[category] = settings

                # Update settings in database
                repo.update_multiple(flattened_updates)

                # Get updated settings
                masked_settings = repo.get_masked_settings()

                # Update global config if available
                self._update_global_config(flattened_updates)

                logger.info(f"Updated {len(flattened_updates)} settings")

                return self._format_settings_for_api(masked_settings)

        except Exception as e:
            logger.error(f"Failed to update settings: {e}")
            raise

    def _update_global_config(self, updates: dict[str, Any]) -> None:
        """Update global config object with new settings"""
        try:
            # This would update the global config instance
            # Implementation depends on how config is structured
            logger.info("Global config update would be implemented here")
        except Exception as e:
            logger.warning(f"Failed to update global config: {e}")

    async def get_setting_value(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value"""
        try:
            with get_db_session_context() as session:
                repo = SettingsRepository(session)
                return repo.get_value(key, default)

        except Exception as e:
            logger.error(f"Failed to get setting '{key}': {e}")
            return default

    async def set_setting_value(self, key: str, value: Any, value_type: str = "string") -> bool:
        """Set a specific setting value"""
        try:
            with get_db_session_context() as session:
                repo = SettingsRepository(session)
                repo.set_value(key, value, value_type)
                logger.info(f"Set setting '{key}' = '{value}'")
                return True

        except Exception as e:
            logger.error(f"Failed to set setting '{key}': {e}")
            return False

    def close(self):
        """Close connections and cleanup resources"""
        logger.info("SettingsService resources closed")
