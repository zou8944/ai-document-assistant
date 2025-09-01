"""
Settings management routes.
"""

import logging

from fastapi import APIRouter, Request

from api.state import get_app_state
from exception import HTTPBadRequestException, HTTPInternalServerErrorException
from models.requests import UpdateSettingsRequest

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/settings")
async def get_settings(request: Request):
    """
    Get system settings with sensitive values masked

    Returns:
        Settings object with masked sensitive information
    """
    app_state = get_app_state(request)

    settings_service = app_state.settings_service

    return await settings_service.get_settings()


@router.patch("/settings")
async def update_settings(
    request_data: UpdateSettingsRequest,
    request: Request
):
    """
    Update system settings

    Args:
        request_data: Settings update data

    Returns:
        Updated settings object
    """
    app_state = get_app_state(request)

    settings_service = app_state.settings_service

    # Convert request data to dict, excluding None values
    updates = {}
    for field, value in request_data.dict(exclude_none=True).items():
        if value is not None:
            updates[field] = value

    # Validate at least one field is provided
    if not updates:
        raise HTTPBadRequestException("At least one setting field must be provided")

    return await settings_service.update_settings(updates)


@router.get("/settings/{category}")
async def get_settings_by_category(category: str, request: Request):
    """
    Get settings for a specific category

    Args:
        category: Settings category (llm, embedding, paths, crawler, text)

    Returns:
        Settings for the specified category
    """
    app_state = get_app_state(request)

    settings_service = app_state.settings_service

    # Get all settings first
    all_settings = await settings_service.get_settings()

    # Extract category-specific settings
    category_settings = {}
    if hasattr(all_settings, category):
        category_settings = getattr(all_settings, category)
    elif category == "general":
        # General category might map to text settings
        category_settings = all_settings.text
    else:
        category_settings = {}

    return category_settings


@router.get("/settings/value/{key}")
async def get_setting_value(key: str, request: Request):
    """
    Get a specific setting value by key

    Args:
        key: Setting key (e.g., 'llm.api_key', 'embedding.model')

    Returns:
        Setting value
    """
    app_state = get_app_state(request)

    settings_service = app_state.settings_service

    value = await settings_service.get_setting_value(key)

    if value is None:
        return {"key": key, "value": None, "exists": False}

    return {"key": key, "value": value, "exists": True}


@router.put("/settings/value/{key}")
async def set_setting_value(
    key: str,
    request: Request,
    value: str,
    value_type: str = "string"
):
    """
    Set a specific setting value by key
    Args:
        key: Setting key
        value: Setting value
        value_type: Value type (string, json, number, boolean)

    Returns:
        Success status
    """
    app_state = get_app_state(request)

    settings_service = app_state.settings_service

    success = await settings_service.set_setting_value(key, value, value_type)

    if not success:
        raise HTTPInternalServerErrorException(f"Failed to set setting '{key}'")

    return {"key": key, "value": value, "updated": True}
