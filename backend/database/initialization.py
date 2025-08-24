"""Database initialization script."""

import os

from database.connection import create_tables
from database.init_data import initialize_default_settings


def initialize_database(force_recreate: bool = False) -> None:
    """
    Initialize the database with tables and default data.

    Args:
        force_recreate: Whether to recreate all tables
    """
    if force_recreate:
        from database.connection import drop_tables
        drop_tables()

    # Create all tables
    create_tables()

    # Initialize default settings
    initialize_default_settings()

    print("Database initialized successfully!")


def check_database_exists() -> bool:
    """
    Check if the database file exists.

    Returns:
        True if database exists, False otherwise
    """
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")
    if database_url.startswith("sqlite:///"):
        db_path = database_url[10:]  # Remove sqlite:///
        return os.path.exists(db_path)
    return True  # For non-SQLite databases, assume they exist


if __name__ == "__main__":
    # Run initialization when called directly
    initialize_database()
