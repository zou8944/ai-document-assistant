"""
Settings management routes.

Supports both legacy TOML-based configuration and the new DB-backed settings.
"""

import asyncio
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


# ---------------------------------------------------------------------------
# Model connection test
# ---------------------------------------------------------------------------

class ConnectionTestRequest(BaseModel):
    service: str  # "crawl" | "embedding" | "agent"
    api_key: str
    base_url: str = ""
    model: str = ""


@router.post("/test-connection")
async def test_connection(req: ConnectionTestRequest) -> dict[str, Any]:
    """Test connectivity to an LLM / embedding service.

    Sends a minimal request to verify that the API key, base URL and model
    are all correct.  Returns ``{"success": true/false, "message": "..."}``.
    """
    try:
        if req.service == "crawl":
            return await _test_openai_chat(req.api_key, req.base_url, req.model)
        elif req.service == "embedding":
            return await _test_openai_embedding(req.api_key, req.base_url, req.model)
        elif req.service == "agent":
            return await _test_anthropic(req.api_key, req.base_url, req.model)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown service: {req.service}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Connection test failed for %s: %s", req.service, e)
        return {"success": False, "message": str(e)}


async def _test_openai_chat(api_key: str, base_url: str, model: str) -> dict[str, Any]:
    """Test an OpenAI-compatible chat endpoint with a minimal request."""
    from langchain_openai import ChatOpenAI

    if not api_key:
        return {"success": False, "message": "API Key 不能为空"}
    if not model:
        return {"success": False, "message": "Model 不能为空"}

    llm = ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url or None,
        max_tokens=16,
        timeout=30,
    )
    await asyncio.wait_for(llm.ainvoke("Hi"), timeout=30)
    # If we get here, the call succeeded
    return {"success": True, "message": f"连接成功，模型 {model} 可用"}


async def _test_openai_embedding(api_key: str, base_url: str, model: str) -> dict[str, Any]:
    """Test an OpenAI-compatible embedding endpoint."""
    from langchain_openai import OpenAIEmbeddings

    if not api_key:
        return {"success": False, "message": "API Key 不能为空"}
    if not model:
        return {"success": False, "message": "Model 不能为空"}

    embeddings = OpenAIEmbeddings(
        model=model,
        api_key=api_key,
        base_url=base_url or None,
    )
    await asyncio.wait_for(embeddings.aembed_query("test"), timeout=30)
    return {"success": True, "message": f"连接成功，模型 {model} 可用"}


async def _test_anthropic(api_key: str, base_url: str, model: str) -> dict[str, Any]:
    """Test an Anthropic endpoint with a minimal messages.create call."""
    from anthropic import AsyncAnthropic

    if not api_key:
        return {"success": False, "message": "API Key 不能为空"}
    if not model:
        return {"success": False, "message": "Model 不能为空"}

    client = AsyncAnthropic(api_key=api_key, base_url=base_url or None)
    await asyncio.wait_for(
        client.messages.create(
            model=model,
            max_tokens=16,
            messages=[{"role": "user", "content": "Hi"}],
        ),
        timeout=30,
    )
    return {"success": True, "message": f"连接成功，模型 {model} 可用"}
