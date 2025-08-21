#!/usr/bin/env python3
"""
FastAPI server entry point for AI Document Assistant.
Replaces the stdin/stdout-based main.py with a REST API server.
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn

import config

# Add backend directory to Python path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Initialize configuration first
try:
    conf = config.init_config()
except Exception as e:
    print(f"Failed to initialize configuration: {e}", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, conf.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_server.log'),
        logging.StreamHandler(sys.stderr)
    ]
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Document Assistant API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8888, help="Port to bind to (0 for auto)")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes")
    parser.add_argument("--log-level", default="info", help="Log level")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    args = parser.parse_args()

    # Validate configuration
    try:
        conf.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        logger.warning("Please check your environment variables and try again.")
        sys.exit(1)

    logger.info("Starting AI Document Assistant API server")
    logger.info(f"Host: {args.host}, Port: {args.port}")
    logger.info(f"Workers: {args.workers}, Log level: {args.log_level}")

    try:
        uvicorn.run(
            "api.main:app",
            host=args.host,
            port=args.port,
            workers=args.workers if not args.reload else 1,  # Single worker for reload mode
            log_level=args.log_level,
            reload=args.reload,
            access_log=True
        )
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        sys.exit(1)
