"""Unified settings access via database settings table.

All business configuration is stored in the `settings` table.
Sensitive values (API keys) are encrypted at rest using AES (Fernet).
"""

import base64
import hashlib
import logging
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from database.connection import session_context
from database.models.settings import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

# Root key derived from a fixed application secret.
# In production, override via SETTINGS_ROOT_KEY env var for better security.
_APP_SECRET = "ai-document-assistant-settings-v1"


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the application secret."""
    key = hashlib.sha256(_APP_SECRET.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt_value(plain: str) -> str:
    """Encrypt a plaintext string for storage."""
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a previously encrypted string."""
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        # Value was stored in plaintext (legacy), return as-is
        return token


# ---------------------------------------------------------------------------
# Core accessors
# ---------------------------------------------------------------------------

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Read a setting value from the database.

    Sensitive fields are automatically decrypted.
    Returns *default* when the key does not exist.
    """
    with session_context() as session:
        row = session.get(Settings, key)
        if row is None:
            return default
        if row.is_sensitive and row.value:
            return decrypt_value(row.value)
        return row.value


def get_setting_typed(key: str, default: Any = None) -> Any:
    """Read a setting and convert to its declared Python type."""
    with session_context() as session:
        row = session.get(Settings, key)
        if row is None:
            return default

        raw = row.value
        if row.is_sensitive and raw:
            raw = decrypt_value(raw)

        if row.value_type == "number":
            try:
                return int(raw) if "." not in raw else float(raw)
            except (ValueError, TypeError):
                return default
        if row.value_type == "boolean":
            return raw.lower() in ("true", "1", "yes")
        return raw


def set_setting(
    key: str,
    value: str,
    *,
    category: str = "general",
    value_type: str = "string",
    description: str = "",
    is_sensitive: bool = False,
) -> None:
    """Insert or update a setting in the database.

    Sensitive values are encrypted before writing (empty values are stored as-is).
    """
    stored_value = encrypt_value(value) if (is_sensitive and value) else value

    with session_context() as session:
        row = session.get(Settings, key)
        if row is None:
            row = Settings(
                key=key,
                value=stored_value,
                value_type=value_type,
                category=category,
                description=description,
                is_sensitive=is_sensitive,
            )
            session.add(row)
        else:
            row.value = stored_value
            if value_type != "string":
                row.value_type = value_type
            if category != "general":
                row.category = category
            if description:
                row.description = description
            row.is_sensitive = is_sensitive
        session.flush()


def delete_setting(key: str) -> bool:
    """Delete a setting. Returns True if it existed."""
    with session_context() as session:
        row = session.get(Settings, key)
        if row is None:
            return False
        session.delete(row)
        session.flush()
        return True


def list_settings(category: Optional[str] = None) -> list[dict[str, Any]]:
    """List all settings, optionally filtered by category.

    Sensitive values are decrypted and returned in plaintext.
    """
    with session_context() as session:
        query = select(Settings)
        if category:
            query = query.where(Settings.category == category)
        query = query.order_by(Settings.category, Settings.key)

        results = []
        for row in session.scalars(query):
            value = row.value
            if row.is_sensitive and value:
                value = decrypt_value(value)
            results.append({
                "key": row.key,
                "value": value or "",
                "value_type": row.value_type,
                "category": row.category,
                "description": row.description,
                "is_sensitive": row.is_sensitive,
                "has_value": bool(row.value),
            })
        return results




# ---------------------------------------------------------------------------
# Default settings & seeding
# ---------------------------------------------------------------------------

# (key, default_value, value_type, category, description, is_sensitive)
DEFAULT_SETTINGS: list[tuple[str, str, str, str, str, bool]] = [
    # ── Crawl LLM（文档爬取/分类/README 生成） ──
    ("CRAWL_PROVIDER", "openai", "string", "crawl",
     "Crawl 服务提供商，目前支持 openai", False),
    ("CRAWL_API_KEY", "", "string", "crawl",
     "Crawl 服务的 API 密钥", True),
    ("CRAWL_BASE_URL", "", "string", "crawl",
     "Crawl 服务的 API 地址", False),
    ("CRAWL_MODEL", "", "string", "crawl",
     "Crawl 使用的 AI 模型名称", False),

    # ── Embedding（文档向量化） ──
    ("EMBEDDING_PROVIDER", "openai", "string", "embedding",
     "Embedding 服务提供商，目前支持 openai 风格", False),
    ("EMBEDDING_API_KEY", "", "string", "embedding",
     "Embedding 服务的 API 密钥，留空则使用 Crawl 的 Key", True),
    ("EMBEDDING_BASE_URL", "", "string", "embedding",
     "Embedding 服务的 API 地址", False),
    ("EMBEDDING_MODEL", "", "string", "embedding",
     "Embedding 使用的向量化模型名称", False),

    # ── Agent（AI 对话） ──
    ("AGENT_PROVIDER", "anthropic", "string", "agent",
     "Agent 服务提供商，目前支持 anthropic", False),
    ("AGENT_API_KEY", "", "string", "agent",
     "Agent 服务的 API 密钥", True),
    ("AGENT_BASE_URL", "", "string", "agent",
     "Agent 服务的 API 地址，留空使用默认地址", False),
    ("AGENT_MODEL", "", "string", "agent",
     "Agent 使用的 AI 模型名称", False),

    # ── 业务参数 ──
    ("CHUNK_SIZE", "500", "number", "business",
     "文档切分时每段最大字符数", False),
    ("CHUNK_OVERLAP", "50", "number", "business",
     "相邻文本块之间的重叠字符数", False),
    ("CRAWLER_MAX_DEPTH", "3", "number", "business",
     "从初始 URL 开始递归抓取网页的最大深度", False),
    ("RAG_TOP_K", "5", "number", "business",
     "回答问题时从知识库检索的最相似文档片段数量", False),
    ("AGENT_TEMPERATURE", "0.7", "number", "business",
     "AI 回复的随机程度，值越低越稳定，越高越有创造性", False),

    # ── 系统参数 ──
    ("SERVER_PORT", "8000", "number", "system",
     "后端服务监听的端口", False),
    ("LOG_LEVEL", "info", "string", "system",
     "服务端日志输出级别：DEBUG / INFO / WARNING / ERROR", False),
]


def ensure_defaults() -> None:
    """Seed default settings if they don't already exist."""
    for key, default_val, vtype, cat, desc, sensitive in DEFAULT_SETTINGS:
        with session_context() as session:
            existing = session.get(Settings, key)
            if existing is not None:
                continue
        # Row does not exist – insert it
        set_setting(
            key,
            default_val,
            category=cat,
            value_type=vtype,
            description=desc,
            is_sensitive=sensitive,
        )
    logger.info("Default settings ensured")


# Keys that must be non-empty for the app to function
_CRITICAL_KEYS = [
    "CRAWL_API_KEY", "CRAWL_BASE_URL", "CRAWL_MODEL",
    "EMBEDDING_BASE_URL", "EMBEDDING_MODEL",
    "AGENT_API_KEY", "AGENT_MODEL",
]


def is_config_complete() -> tuple[bool, list[str]]:
    """Check whether all critical settings have been filled in.

    Returns (is_complete, missing_keys).
    """
    missing: list[str] = []
    for key in _CRITICAL_KEYS:
        val = get_setting(key)
        if not val:
            missing.append(key)
    return len(missing) == 0, missing
