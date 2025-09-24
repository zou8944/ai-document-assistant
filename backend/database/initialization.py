"""Database initialization script."""

from config import get_config
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
    conf = get_config()
    db_path = conf.get_app_db_path()
    return db_path.exists()


if __name__ == "__main__":
    # Run initialization when called directly
    initialize_database()
