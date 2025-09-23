"""
Settings management routes for TOML-based configuration.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from api.state import AppState
from config import get_config, update_config
from models.config import AppConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/")
async def get_settings() -> dict[str, Any]:
    """Get current application settings with sensitive information masked."""
    return get_config().to_dict()


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
