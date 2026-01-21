#!/usr/bin/env python3
"""
Avoma to Notion Export Tool

Main script to export all meetings from Avoma and import them into Notion.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import Config
from src.logger import setup_logger
from src.avoma_client import AvomaClient, AvomaAPIError
from src.notion_client_wrapper import NotionClientWrapper, NotionAPIError
from src.transformer import MeetingTransformer

logger = setup_logger()


def save_json(data, filename: str):
    """Save data to JSON file in exports directory."""
    filepath = Path(Config.EXPORTS_DIR) / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved data to: {filepath}")
    return filepath


def load_json(filename: str):
    """Load data from JSON file."""
    filepath = Path(Config.EXPORTS_DIR) / filename
    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def step_fetch_meetings(avoma_client: AvomaClient, force: bool = False) -> list:
    """
    Step 1: Fetch all meetings from Avoma.

    Args:
        avoma_client: Avoma API client
        force: Force refetch even if cached data exists

    Returns:
        List of meetings
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("STEP 1: FETCHING MEETINGS FROM AVOMA")
    logger.info("=" * 70)

    cache_file = "avoma_meetings_list.json"

    # Check for cached data
    if not force:
        cached_meetings = load_json(cache_file)
        if cached_meetings:
            logger.info(f"Found cached meetings data ({len(cached_meetings)} meetings)")
            logger.info("Use --force-fetch to re-download")
            return cached_meetings

    # Fetch meetings
    from_date = Config.EXPORT_FROM_DATE
    meetings = avoma_client.fetch_all_meetings(from_date=from_date)

    # Save to cache
    save_json(meetings, cache_file)

    return meetings


def step_fetch_complete_data(
    avoma_client: AvomaClient, meetings: list, force: bool = False
) -> list:
    """
    Step 2: Fetch complete data for each meeting.

    Args:
        avoma_client: Avoma API client
        meetings: List of basic meeting data
        force: Force refetch even if cached data exists

    Returns:
        List of complete meeting data
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("STEP 2: FETCHING COMPLETE DATA FOR EACH MEETING")
    logger.info("=" * 70)

    cache_file = "avoma_meetings_complete.json"

    # Check for cached data
    if not force:
        cached_complete = load_json(cache_file)
        if cached_complete:
            logger.info(f"Found cached complete data ({len(cached_complete)} meetings)")
            logger.info("Use --force-fetch to re-download")
            return cached_complete

    # Fetch complete data
    complete_meetings = avoma_client.fetch_all_complete_meetings(meetings)

    # Save to cache
    save_json(complete_meetings, cache_file)

    return complete_meetings


def step_transform_data(complete_meetings: list, force: bool = False) -> list:
    """
    Step 3: Transform Avoma data to Notion format.

    Args:
        complete_meetings: List of complete meeting data
        force: Force re-transformation even if cached data exists

    Returns:
        List of transformed meetings
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info("STEP 3: TRANSFORMING DATA FOR NOTION")
    logger.info("=" * 70)

    cache_file = "notion_import_data.json"

    # Check for cached data
    if not force:
        cached_transformed = load_json(cache_file)
        if cached_transformed:
            logger.info(f"Found cached transformed data ({len(cached_transformed)} meetings)")
            logger.info("Use --force-transform to re-transform")
            return cached_transformed

    # Transform data
    transformer = MeetingTransformer()
    transformed_meetings = transformer.transform_meetings(complete_meetings)

    # Save to cache
    save_json(transformed_meetings, cache_file)

    return transformed_meetings


def step_import_to_notion(
    notion_client: NotionClientWrapper,
    transformed_meetings: list,
    dry_run: bool = False,
) -> dict:
    """
    Step 4: Import meetings into Notion.

    Args:
        notion_client: Notion API client
        transformed_meetings: List of transformed meeting data
        dry_run: If True, simulate import without creating pages

    Returns:
        Import summary
    """
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"STEP 4: IMPORTING TO NOTION {'(DRY RUN)' if dry_run else ''}")
    logger.info("=" * 70)

    # Import meetings
    summary = notion_client.import_meetings(transformed_meetings, dry_run=dry_run)

    # Save failed imports if any
    if summary["failed_details"]:
        failed_file = f"failed_imports_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_json(summary["failed_details"], failed_file)

    return summary


def verify_notion_schema(notion_client: NotionClientWrapper):
    """Verify Notion database schema and provide guidance."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("VERIFYING NOTION DATABASE SCHEMA")
    logger.info("=" * 70)

    # Define required properties (adapted to existing database schema)
    required_properties = {
        "Name": "title",  # Using existing "Name" field
        "Date": "date",
        "Duration": "number",
        "Participants": "multi_select",
        "Recording": "url",  # Using existing "Recording" field
        "Avoma ID": "rich_text",
        "Host": "select",
    }

    # Verify properties
    result = notion_client.verify_property_types(required_properties)

    if result["missing"] or result["mismatched"]:
        logger.warning("")
        logger.warning("⚠️  SCHEMA ISSUES DETECTED")
        logger.warning("")

        if result["missing"]:
            logger.warning("Missing properties (you need to add these to your Notion database):")
            for prop in result["missing"]:
                expected_type = required_properties[prop]
                logger.warning(f"  - {prop} (type: {expected_type})")

        if result["mismatched"]:
            logger.warning("Mismatched property types:")
            for prop in result["mismatched"]:
                logger.warning(f"  - {prop}")

        logger.warning("")
        logger.warning("Please update your Notion database schema before importing.")
        logger.warning("You can add properties manually in Notion or adjust the transformation logic.")
        logger.warning("")

        return False
    else:
        logger.info("✓ All required properties are present with correct types")
        return True


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Export meetings from Avoma and import to Notion",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test connections
  python main.py --test-connection

  # Verify Notion database schema
  python main.py --verify-schema

  # Dry run (simulate import without creating pages)
  python main.py --dry-run

  # Full export and import
  python main.py

  # Force re-fetch and re-import
  python main.py --force-fetch --force-transform
        """,
    )

    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test API connections and exit",
    )

    parser.add_argument(
        "--verify-schema",
        action="store_true",
        help="Verify Notion database schema and exit",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate import without creating Notion pages",
    )

    parser.add_argument(
        "--force-fetch",
        action="store_true",
        help="Force re-fetch data from Avoma (ignore cache)",
    )

    parser.add_argument(
        "--force-transform",
        action="store_true",
        help="Force re-transform data (ignore cache)",
    )

    parser.add_argument(
        "--from-date",
        type=str,
        help="Override start date for export (ISO format: YYYY-MM-DD)",
    )

    args = parser.parse_args()

    # Print header
    logger.info("")
    logger.info("=" * 70)
    logger.info("AVOMA TO NOTION EXPORT TOOL")
    logger.info("=" * 70)
    logger.info("")

    try:
        # Validate configuration
        logger.info("Validating configuration...")
        Config.validate()
        Config.setup_directories()
        logger.info("✓ Configuration valid")

        # Override from_date if provided
        if args.from_date:
            Config.EXPORT_FROM_DATE = args.from_date
            logger.info(f"Using custom start date: {args.from_date}")

        # Initialize clients
        logger.info("Initializing API clients...")
        avoma_client = AvomaClient()
        notion_client = NotionClientWrapper()
        logger.info("✓ Clients initialized")

        # Test connections
        if args.test_connection or args.verify_schema:
            logger.info("")
            logger.info("Testing API connections...")
            avoma_client.test_connection()
            notion_client.test_connection()
            logger.info("")
            logger.info("✓ All connections successful!")

            if args.verify_schema:
                verify_notion_schema(notion_client)

            return 0

        # Verify schema before proceeding
        logger.info("")
        schema_valid = verify_notion_schema(notion_client)

        if not schema_valid:
            logger.error("")
            logger.error("Please fix schema issues before proceeding.")
            logger.error("Run with --verify-schema to check schema again.")
            return 1

        # Execute export pipeline
        meetings = step_fetch_meetings(avoma_client, force=args.force_fetch)

        if not meetings:
            logger.warning("No meetings found to export")
            return 0

        complete_meetings = step_fetch_complete_data(
            avoma_client, meetings, force=args.force_fetch
        )

        transformed_meetings = step_transform_data(
            complete_meetings, force=args.force_transform
        )

        summary = step_import_to_notion(
            notion_client, transformed_meetings, dry_run=args.dry_run
        )

        # Final summary
        logger.info("")
        logger.info("=" * 70)
        logger.info("EXPORT COMPLETE!")
        logger.info("=" * 70)
        logger.info("")

        if args.dry_run:
            logger.info("✓ Dry run completed successfully")
            logger.info("  Run without --dry-run to perform actual import")
        else:
            logger.info(f"✓ Successfully imported {summary['successful']} meetings")
            if summary["failed"]:
                logger.warning(f"⚠️  {summary['failed']} meetings failed to import")
                logger.warning("  Check the failed_imports_*.json file for details")

        logger.info("")
        logger.info("Data files saved in: exports/")
        logger.info("Log files saved in: logs/")
        logger.info("")

        return 0

    except (ValueError, AvomaAPIError, NotionAPIError) as e:
        logger.error("")
        logger.error(f"❌ Error: {e}")
        logger.error("")
        return 1

    except KeyboardInterrupt:
        logger.warning("")
        logger.warning("⚠️  Export cancelled by user")
        logger.warning("")
        return 130

    except Exception as e:
        logger.error("")
        logger.error(f"❌ Unexpected error: {e}")
        logger.exception("Full traceback:")
        logger.error("")
        return 1


if __name__ == "__main__":
    sys.exit(main())
