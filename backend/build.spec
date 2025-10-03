# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for AI Document Assistant Backend
This configuration creates a single executable file containing the entire backend.
"""

import sys
from pathlib import Path

# Get the backend directory
backend_dir = Path().absolute()

# Add all Python packages to the analysis
a = Analysis(
    ['api_server.py'],
    pathex=[str(backend_dir)],
    binaries=[],
    datas=[
        # Include configuration files and templates
    ],
    hiddenimports=[
        # Core application modules
        'api',
        'api.main',
        'api.routes',
        'api.routes.document',
        'api.routes.chat',
        'api.routes.system',
        'config',
        'models',
        'models.document',
        'models.chat',
        'services',
        'services.document_service',
        'services.chat_service',
        'services.llm_service',
        'crawler',
        'crawler.web_crawler',
        'data_processing',
        'data_processing.text_processor',
        'rag',
        'rag.rag_chain',
        'vector_store',
        'vector_store.chroma_store',

        'chromadb.telemetry.product.posthog',
        'chromadb.api.rust',

        # FastAPI and dependencies
        'fastapi',
        'uvicorn',
        'uvicorn.main',
        'uvicorn.server',
        'uvicorn.config',
        'starlette',
        'pydantic',
        'pydantic.types',
        'pydantic.validators',

        # LangChain and AI libraries
        'langchain',
        'langchain_core',
        'langchain_text_splitters',
        'langchain_openai',
        'openai',

        # Vector database
        'chromadb',
        'chromadb.api',
        'chromadb.config',

        # Document processing
        'pypdf',
        'docx',
        'python_docx',
        'chardet',
        'magic',

        # Web scraping
        'scrapy',
        'scrapy.crawler',
        'scrapy.utils',
        'bs4',
        'beautifulsoup4',
        'lxml',
        'lxml.etree',
        'lxml.html',
        'markdownify',

        # Database
        'sqlalchemy',
        'sqlalchemy.ext',
        'sqlalchemy.ext.declarative',
        'alembic',

        # HTTP and async
        'httpx',
        'aiofiles',
        'sse_starlette',

        # Utilities
        'loguru',
        'toml',
        'markdown_it',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test packages
        'pytest',
        'test',
        'tests',
        # Exclude development tools
        'black',
        'ruff',
        'mypy',
        # Exclude unused GUI frameworks
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        # Exclude jupyter/notebook
        'jupyter',
        'notebook',
        'IPython',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Filter out problematic or unnecessary modules
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ai-document-assistant-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Enable UPX compression to reduce file size
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Keep console for logging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)