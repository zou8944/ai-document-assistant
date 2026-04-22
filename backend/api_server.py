#!/usr/bin/env python3
"""
FastAPI server entry point for AI Document Assistant.
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

# Load .env before any config/env reads; no-op if file doesn't exist
load_dotenv(".env")

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

import config  # noqa: E402

# Initialize configuration first
conf = config.get_config()

# 导入统一的日志配置
from logging_config import configure_logging

# 初始配置日志
configure_logging(conf)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Parse command line arguments (for frontend integration)
    parser = argparse.ArgumentParser(description="AI Document Assistant API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to")

    args = parser.parse_args()

    logger.info("Starting AI Document Assistant API server")
    logger.info(f"Host: {args.host}, Port: {args.port}")
    logger.info(f"Log level: {conf.system.log_level}")

    try:
        uvicorn.run(
            "api.main:app",
            host=args.host,
            port=args.port,
            log_level=conf.system.log_level,
            access_log=True,
        )
    except Exception as e:
        logger.error(f"Failed to start API server: {e}", exc_info=True)
        sys.exit(1)
