#!/usr/bin/env python3
"""
Script to add missing properties to the Notion database.
"""

from src.config import Config
from src.logger import setup_logger
from notion_client import Client

logger = setup_logger()

def add_properties_to_database():
    """Add missing properties to the Notion database."""

    Config.validate()
    Config.setup_directories()

    client = Client(auth=Config.NOTION_API_KEY)
    database_id = Config.NOTION_DATABASE_ID

    logger.info("Adding missing properties to Notion database...")
    logger.info(f"Database ID: {database_id}")

    # Define the properties to add
    new_properties = {
        "Avoma ID": {
            "rich_text": {}
        },
        "Duration": {
            "number": {
                "format": "number"
            }
        },
        "Participants": {
            "multi_select": {
                "options": []
            }
        },
        "Host": {
            "select": {
                "options": []
            }
        }
    }

    try:
        # Update the database with new properties
        logger.info("Updating database schema...")
        response = client.databases.update(
            database_id=database_id,
            properties=new_properties
        )

        logger.info("✓ Successfully added properties:")
        for prop_name in new_properties.keys():
            logger.info(f"  • {prop_name}")

        logger.info("")
        logger.info("Database is now ready for Avoma import!")

        return True

    except Exception as e:
        logger.error(f"Failed to add properties: {e}")
        logger.error("")
        logger.error("You may need to add these properties manually in Notion:")
        for prop_name, prop_config in new_properties.items():
            prop_type = list(prop_config.keys())[0]
            logger.error(f"  • {prop_name} (type: {prop_type})")

        return False

if __name__ == "__main__":
    add_properties_to_database()
