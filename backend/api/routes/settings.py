"""
Settings management routes.

Supports both legacy TOML-based configuration and the new DB-backed settings.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.state import AppState
from config import load_config_from_db, update_config
from models.config import AppConfig
from settings_util import (
    delete_setting,
    is_config_complete,
    list_settings,
    set_setting,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Legacy TOML-based endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------


@router.get("/")
async def get_settings() -> dict[str, Any]:
    """Get current application settings with sensitive information masked."""
    return AppConfig().to_dict()


@router.put("/")
async def update_settings(settings_data: dict[str, Any]) -> dict[str, Any]:
    """Update application settings with new values."""
    try:
        new_config = AppConfig.from_dict(settings_data)
        new_config.validate()
        update_config(new_config)

        AppState.recreate_with_new_config(new_config)

        logger.info("Settings updated successfully")

        return new_config.to_dict()

    except ValueError as e:
        logger.error(f"Invalid settings data: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e


# ---------------------------------------------------------------------------
# New DB-backed settings endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def settings_status() -> dict[str, Any]:
    """Check whether critical configuration is complete.

    Frontend should call this on startup; if ``complete`` is ``false`` the
    setup wizard must be shown.
    """
    complete, missing = is_config_complete()
    return {
        "complete": complete,
        "missing_keys": missing,
    }


class SettingItem(BaseModel):
    key: str
    value: str
    category: Optional[str] = "general"
    value_type: Optional[str] = "string"
    description: Optional[str] = ""
    is_sensitive: Optional[bool] = False


@router.get("/items")
async def list_setting_items(category: Optional[str] = None) -> list[dict[str, Any]]:
    """List all settings, optionally filtered by category.

    Sensitive values are masked.
    """
    return list_settings(category)


@router.get("/items/{key}")
async def get_setting_item(key: str) -> dict[str, Any]:
    """Get a single setting by key.

    Sensitive values are masked for display.
    """
    items = list_settings()
    for item in items:
        if item["key"] == key:
            return item
    raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")


@router.put("/items")
async def upsert_setting_item(item: SettingItem) -> dict[str, Any]:
    """Create or update a single setting."""
    set_setting(
        item.key,
        item.value,
        category=item.category or "general",
        value_type=item.value_type or "string",
        description=item.description or "",
        is_sensitive=item.is_sensitive or False,
    )

    # Reload services with new config
    try:
        new_config = load_config_from_db()
        AppState.recreate_with_new_config(new_config)
    except Exception as e:
        logger.warning(f"Failed to reload config after setting change: {e}")

    return {"key": item.key, "status": "ok"}


class SettingsBatch(BaseModel):
    items: list[SettingItem]


@router.put("/items/batch")
async def upsert_settings_batch(batch: SettingsBatch) -> dict[str, Any]:
    """Batch update multiple settings at once (used by setup wizard)."""
    for item in batch.items:
        set_setting(
            item.key,
            item.value,
            category=item.category or "general",
            value_type=item.value_type or "string",
            description=item.description or "",
            is_sensitive=item.is_sensitive or False,
        )

    # Reload services with new config
    try:
        new_config = load_config_from_db()
        AppState.recreate_with_new_config(new_config)
    except Exception as e:
        logger.warning(f"Failed to reload config after batch update: {e}")

    complete, missing = is_config_complete()
    return {
        "status": "ok",
        "complete": complete,
        "missing_keys": missing,
    }


@router.delete("/items/{key}")
async def delete_setting_item(key: str) -> dict[str, Any]:
    """Delete a setting by key."""
    if not delete_setting(key):
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return {"key": key, "status": "deleted"}
