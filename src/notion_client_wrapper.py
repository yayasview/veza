"""Notion API client wrapper for importing meeting data."""

import time
from typing import Dict, List, Optional, Any
from notion_client import Client as NotionClient
from notion_client.errors import APIResponseError

from .config import Config
from .logger import setup_logger

logger = setup_logger()


class NotionAPIError(Exception):
    """Exception raised for Notion API errors."""
    pass


class NotionClientWrapper:
    """Wrapper for the Notion API client with additional functionality."""

    def __init__(self, api_key: Optional[str] = None, database_id: Optional[str] = None):
        """
        Initialize the Notion client wrapper.

        Args:
            api_key: Notion integration token (defaults to Config.NOTION_API_KEY)
            database_id: Notion database ID (defaults to Config.NOTION_DATABASE_ID)
        """
        self.api_key = api_key or Config.NOTION_API_KEY
        self.database_id = database_id or Config.NOTION_DATABASE_ID
        self.rate_limit = 1.0 / Config.NOTION_RATE_LIMIT  # seconds between requests

        if not self.api_key:
            raise ValueError("Notion API key is required")

        if not self.database_id:
            raise ValueError("Notion database ID is required")

        self.client = NotionClient(auth=self.api_key)

    def test_connection(self) -> bool:
        """
        Test the Notion API connection and database access.

        Returns:
            True if connection is successful

        Raises:
            NotionAPIError: If connection fails
        """
        try:
            logger.info("Testing Notion API connection...")
            database = self.client.databases.retrieve(database_id=self.database_id)
            logger.info(f"✓ Connected to database: {database.get('title', [{}])[0].get('plain_text', 'Unknown')}")
            return True
        except APIResponseError as e:
            logger.error(f"✗ Notion API connection failed: {e}")
            raise NotionAPIError(f"Failed to connect to Notion: {e}")

    def get_database_schema(self) -> Dict[str, Any]:
        """
        Get the database schema/properties.

        Returns:
            Database properties
        """
        try:
            logger.info("Fetching database schema...")
            database = self.client.databases.retrieve(database_id=self.database_id)

            # Handle new data_sources structure (API version 2025-09-03+)
            properties = database.get("properties", {})

            if not properties:
                # Try data sources approach
                data_sources = database.get("data_sources", [])
                if data_sources:
                    data_source_id = data_sources[0]["data_source_id"]
                    data_source = self.client.request(
                        method="GET", path=f"data-sources/{data_source_id}"
                    )
                    properties = data_source.get("properties", {})

            logger.info(f"Found {len(properties)} properties in database")
            for prop_name, prop_config in properties.items():
                logger.debug(f"  - {prop_name}: {prop_config.get('type')}")

            return properties

        except APIResponseError as e:
            logger.error(f"Failed to retrieve database schema: {e}")
            raise NotionAPIError(f"Failed to retrieve database schema: {e}")

    def create_page(
        self, properties: Dict[str, Any], children: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Create a new page in the database.

        Args:
            properties: Page properties
            children: Page content blocks

        Returns:
            Created page data

        Raises:
            NotionAPIError: If page creation fails
        """
        try:
            page_data = {
                "parent": {"database_id": self.database_id},
                "properties": properties,
            }

            if children:
                page_data["children"] = children

            # Rate limiting
            time.sleep(self.rate_limit)

            page = self.client.pages.create(**page_data)
            return page

        except APIResponseError as e:
            logger.error(f"Failed to create page: {e}")
            raise NotionAPIError(f"Failed to create page: {e}")

    def import_meetings(
        self, transformed_meetings: List[Dict[str, Any]], dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Import meetings into Notion database.

        Args:
            transformed_meetings: List of transformed meeting data
            dry_run: If True, don't actually create pages

        Returns:
            Import summary with success/failure counts
        """
        total = len(transformed_meetings)
        successful = 0
        failed = []

        logger.info(f"{'[DRY RUN] ' if dry_run else ''}Importing {total} meetings to Notion...")

        for i, meeting_data in enumerate(transformed_meetings, 1):
            # Get meeting title for logging
            title = "Unknown"
            try:
                title_prop = meeting_data.get("properties", {}).get("Title", {})
                if title_prop.get("title"):
                    title = title_prop["title"][0]["text"]["content"]
            except (KeyError, IndexError):
                pass

            try:
                if not dry_run:
                    page = self.create_page(
                        properties=meeting_data["properties"],
                        children=meeting_data.get("children", []),
                    )
                    logger.debug(f"Created page for: {title}")
                else:
                    logger.debug(f"[DRY RUN] Would create page for: {title}")

                successful += 1

                # Progress update
                if i % 10 == 0 or i == total:
                    logger.info(f"Progress: {i}/{total} meetings processed")

            except Exception as e:
                logger.error(f"Failed to import meeting '{title}': {e}")
                failed.append({
                    "index": i - 1,
                    "title": title,
                    "error": str(e),
                    "properties": meeting_data.get("properties", {}),
                })

        # Summary
        summary = {
            "total": total,
            "successful": successful,
            "failed": len(failed),
            "failed_details": failed,
            "dry_run": dry_run,
        }

        logger.info("")
        logger.info("=" * 50)
        logger.info("IMPORT SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total meetings: {total}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {len(failed)}")
        logger.info(f"Success rate: {(successful/total*100):.1f}%")

        if dry_run:
            logger.info("\n[DRY RUN] No pages were actually created")

        return summary

    def verify_property_types(
        self, required_properties: Dict[str, str]
    ) -> Dict[str, List[str]]:
        """
        Verify that required properties exist in the database with correct types.

        Args:
            required_properties: Dict of property_name -> expected_type

        Returns:
            Dict with 'missing' and 'mismatched' property lists
        """
        schema = self.get_database_schema()

        missing = []
        mismatched = []

        for prop_name, expected_type in required_properties.items():
            if prop_name not in schema:
                missing.append(prop_name)
            elif schema[prop_name].get("type") != expected_type:
                actual_type = schema[prop_name].get("type")
                mismatched.append(f"{prop_name} (expected: {expected_type}, actual: {actual_type})")

        if missing:
            logger.warning(f"Missing properties: {', '.join(missing)}")

        if mismatched:
            logger.warning(f"Mismatched property types: {', '.join(mismatched)}")

        return {"missing": missing, "mismatched": mismatched}

    def get_property_type(self, property_name: str) -> Optional[str]:
        """
        Get the type of a specific property in the database.

        Args:
            property_name: Name of the property

        Returns:
            Property type or None if not found
        """
        schema = self.get_database_schema()
        return schema.get(property_name, {}).get("type")
