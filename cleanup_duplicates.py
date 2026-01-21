#!/usr/bin/env python3
"""
Duplicate Cleanup Script

Removes duplicate meeting entries from Notion database based on Avoma ID.
Keeps the most recently created entry and deletes older duplicates.
"""

import argparse
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from src.config import Config
from src.logger import setup_logger
from notion_client import Client

logger = setup_logger()


def find_duplicates(client: Client, database_id: str) -> Dict[str, List[Dict]]:
    """
    Find duplicate pages in the Notion database based on Avoma ID.

    Args:
        client: Notion client
        database_id: Database ID

    Returns:
        Dictionary mapping Avoma ID to list of duplicate pages
    """
    logger.info("Scanning Notion database for duplicates...")

    # Query all pages from the database
    all_pages = []
    has_more = True
    start_cursor = None

    while has_more:
        params = {"database_id": database_id, "page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor

        response = client.databases.query(**params)
        all_pages.extend(response["results"])

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    logger.info(f"Found {len(all_pages)} total pages in database")

    # Group pages by Avoma ID
    avoma_id_groups = defaultdict(list)

    for page in all_pages:
        # Extract Avoma ID
        avoma_id = None
        if "Avoma ID" in page["properties"]:
            rich_text = page["properties"]["Avoma ID"].get("rich_text", [])
            if rich_text:
                avoma_id = rich_text[0]["text"]["content"]

        if avoma_id:
            avoma_id_groups[avoma_id].append(page)

    # Find duplicates (groups with more than 1 page)
    duplicates = {
        avoma_id: pages
        for avoma_id, pages in avoma_id_groups.items()
        if len(pages) > 1
    }

    logger.info(f"Found {len(duplicates)} Avoma IDs with duplicates")

    return duplicates


def get_page_title(page: Dict) -> str:
    """Extract title from page."""
    try:
        name_prop = page["properties"].get("Name", {})
        if name_prop.get("title"):
            return name_prop["title"][0]["text"]["content"]
    except (KeyError, IndexError):
        pass
    return "Untitled"


def get_page_created_time(page: Dict) -> datetime:
    """Extract created time from page."""
    created = page.get("created_time", "")
    try:
        return datetime.fromisoformat(created.replace("Z", "+00:00"))
    except:
        return datetime.min


def cleanup_duplicates(
    client: Client, duplicates: Dict[str, List[Dict]], dry_run: bool = True
) -> Dict:
    """
    Remove duplicate pages, keeping the most recently created one.

    Args:
        client: Notion client
        duplicates: Dictionary of duplicate pages
        dry_run: If True, don't actually delete pages

    Returns:
        Summary of cleanup operation
    """
    total_duplicates = sum(len(pages) - 1 for pages in duplicates.values())

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"{'[DRY RUN] ' if dry_run else ''}CLEANING UP DUPLICATES")
    logger.info("=" * 70)
    logger.info(f"Total duplicate pages to remove: {total_duplicates}")
    logger.info("")

    deleted_count = 0
    kept_count = 0
    failed = []

    for avoma_id, pages in duplicates.items():
        # Sort pages by created time (newest first)
        sorted_pages = sorted(pages, key=get_page_created_time, reverse=True)

        # Keep the newest page
        keep_page = sorted_pages[0]
        keep_title = get_page_title(keep_page)
        keep_time = get_page_created_time(keep_page)

        logger.info(f"Avoma ID: {avoma_id}")
        logger.info(f"  KEEPING: {keep_title} (created: {keep_time.strftime('%Y-%m-%d %H:%M:%S')})")

        kept_count += 1

        # Delete older duplicates
        for dup_page in sorted_pages[1:]:
            dup_title = get_page_title(dup_page)
            dup_time = get_page_created_time(dup_page)
            dup_id = dup_page["id"]

            if dry_run:
                logger.info(f"  [DRY RUN] Would delete: {dup_title} (created: {dup_time.strftime('%Y-%m-%d %H:%M:%S')})")
            else:
                try:
                    logger.info(f"  Deleting: {dup_title} (created: {dup_time.strftime('%Y-%m-%d %H:%M:%S')})")

                    # Archive (soft delete) the page
                    client.pages.update(page_id=dup_id, archived=True)

                    deleted_count += 1

                except Exception as e:
                    logger.error(f"  Failed to delete page {dup_id}: {e}")
                    failed.append({
                        "page_id": dup_id,
                        "title": dup_title,
                        "error": str(e),
                    })

        logger.info("")

    # Summary
    summary = {
        "total_duplicates": total_duplicates,
        "deleted": deleted_count,
        "kept": kept_count,
        "failed": failed,
        "dry_run": dry_run,
    }

    logger.info("=" * 70)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Duplicate pages found: {total_duplicates}")
    logger.info(f"Pages kept (newest): {kept_count}")

    if dry_run:
        logger.info(f"Pages that would be deleted: {total_duplicates}")
        logger.info("")
        logger.info("[DRY RUN] No pages were actually deleted")
    else:
        logger.info(f"Pages deleted: {deleted_count}")
        if failed:
            logger.info(f"Failed deletions: {len(failed)}")

    logger.info("=" * 70)

    return summary


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Remove duplicate meeting entries from Notion database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be deleted (dry-run)
  python cleanup_duplicates.py --dry-run

  # Actually delete duplicates
  python cleanup_duplicates.py

  # Force check even if no duplicates expected
  python cleanup_duplicates.py --force
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview deletions without actually deleting pages",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force cleanup even if no duplicates are expected",
    )

    args = parser.parse_args()

    # Print header
    logger.info("")
    logger.info("=" * 70)
    logger.info("NOTION DUPLICATE CLEANUP TOOL")
    logger.info("=" * 70)
    logger.info("")

    try:
        # Validate configuration
        Config.validate()
        Config.setup_directories()

        # Initialize Notion client
        logger.info("Initializing Notion client...")
        client = Client(auth=Config.NOTION_API_KEY)
        database_id = Config.NOTION_DATABASE_ID
        logger.info("✓ Client initialized")
        logger.info("")

        # Find duplicates
        duplicates = find_duplicates(client, database_id)

        if not duplicates:
            logger.info("")
            logger.info("=" * 70)
            logger.info("✓ No duplicates found!")
            logger.info("=" * 70)
            logger.info("")
            return 0

        # Clean up duplicates
        summary = cleanup_duplicates(client, duplicates, dry_run=args.dry_run)

        if args.dry_run:
            logger.info("")
            logger.info("Run without --dry-run to actually delete the duplicates")
            logger.info("")

        return 0

    except Exception as e:
        logger.error("")
        logger.error(f"❌ Error: {e}")
        logger.exception("Full traceback:")
        logger.error("")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
