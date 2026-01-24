#!/usr/bin/env python3
"""
Duplicate Cleanup Script

Removes duplicate meeting entries from Notion database based on Avoma ID.
Keeps the entry with the most complete content (notes, transcripts, etc.)
and deletes less complete duplicates.
"""

import argparse
import time
from collections import defaultdict
from datetime import datetime
from typing import Dict, List

from src.config import Config
from src.logger import setup_logger
from notion_client import Client

logger = setup_logger()

# Rate limiting for Notion API
_notion_last_request_time = 0.0
_notion_rate_limit = 1.0 / Config.NOTION_RATE_LIMIT  # seconds between requests


def _wait_for_rate_limit():
    """Wait if necessary to respect Notion API rate limits."""
    global _notion_last_request_time
    current_time = time.time()
    time_since_last_request = current_time - _notion_last_request_time
    
    if time_since_last_request < _notion_rate_limit:
        sleep_time = _notion_rate_limit - time_since_last_request
        time.sleep(sleep_time)
    
    _notion_last_request_time = time.time()


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

        _wait_for_rate_limit()
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


def get_page_content_score(client: Client, page_id: str) -> Dict[str, int]:
    """
    Analyze page content to determine completeness score.
    
    Args:
        client: Notion client
        page_id: Page ID to analyze
        
    Returns:
        Dictionary with content analysis scores
    """
    score = {
        "has_key_takeaways": 0,
        "has_action_items": 0,
        "has_transcript": 0,
        "transcript_length": 0,
        "total_blocks": 0,
        "total_score": 0
    }
    
    try:
        # Fetch page children (content blocks)
        has_more = True
        start_cursor = None
        all_blocks = []
        
        while has_more:
            params = {"block_id": page_id, "page_size": 100}
            if start_cursor:
                params["start_cursor"] = start_cursor
            
            _wait_for_rate_limit()
            response = client.blocks.children.list(**params)
            all_blocks.extend(response.get("results", []))
            
            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")
        
        score["total_blocks"] = len(all_blocks)
        
        # Analyze blocks for content
        transcript_text = ""
        in_transcript_section = False
        
        for block in all_blocks:
            block_type = block.get("type", "")
            
            # Check for headings that indicate sections
            if block_type == "heading_2":
                heading_content = ""
                try:
                    rich_text = block.get("heading_2", {}).get("rich_text", [])
                    if rich_text:
                        heading_content = " ".join([rt.get("text", {}).get("content", "") for rt in rich_text]).lower()
                    
                    if "key takeaways" in heading_content:
                        score["has_key_takeaways"] = 1
                    elif "action items" in heading_content:
                        score["has_action_items"] = 1
                    elif "transcript" in heading_content:
                        in_transcript_section = True
                        score["has_transcript"] = 1
                except:
                    pass
            
            # Collect transcript text
            if in_transcript_section or block_type in ["paragraph", "bulleted_list_item", "numbered_list_item"]:
                try:
                    if block_type == "paragraph":
                        rich_text = block.get("paragraph", {}).get("rich_text", [])
                    elif block_type == "bulleted_list_item":
                        rich_text = block.get("bulleted_list_item", {}).get("rich_text", [])
                    elif block_type == "numbered_list_item":
                        rich_text = block.get("numbered_list_item", {}).get("rich_text", [])
                    else:
                        rich_text = []
                    
                    if rich_text:
                        block_text = " ".join([rt.get("text", {}).get("content", "") for rt in rich_text])
                        transcript_text += block_text + " "
                except:
                    pass
        
        # Calculate transcript length
        score["transcript_length"] = len(transcript_text.strip())
        
        # Calculate total score (weighted)
        # Key takeaways: 10 points
        # Action items: 10 points
        # Transcript: 20 points base + 1 point per 100 characters
        score["total_score"] = (
            score["has_key_takeaways"] * 10 +
            score["has_action_items"] * 10 +
            score["has_transcript"] * 20 +
            (score["transcript_length"] // 100)
        )
        
    except Exception as e:
        logger.debug(f"Error analyzing page {page_id}: {e}")
        # Return default score if analysis fails
    
    return score


def cleanup_duplicates(
    client: Client, duplicates: Dict[str, List[Dict]], dry_run: bool = True
) -> Dict:
    """
    Remove duplicate pages, keeping the one with the most complete content.

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
    logger.info("Analyzing content to keep the most complete version...")
    logger.info("")

    deleted_count = 0
    kept_count = 0
    failed = []

    for avoma_id, pages in duplicates.items():
        logger.info(f"Avoma ID: {avoma_id}")
        logger.info(f"  Analyzing {len(pages)} duplicate pages...")
        
        # Analyze content for each page
        page_scores = []
        for page in pages:
            page_id = page["id"]
            page_title = get_page_title(page)
            page_time = get_page_created_time(page)
            
            logger.debug(f"    Analyzing: {page_title}")
            score = get_page_content_score(client, page_id)
            score["page"] = page
            score["title"] = page_title
            score["created_time"] = page_time
            page_scores.append(score)
            
            logger.debug(f"      Score: {score['total_score']} (Takeaways: {score['has_key_takeaways']}, "
                       f"Actions: {score['has_action_items']}, Transcript: {score['has_transcript']}, "
                       f"Length: {score['transcript_length']} chars)")
        
        # Sort by total score (highest first), then by created time (newest first) as tiebreaker
        page_scores.sort(key=lambda x: (x["total_score"], x["created_time"]), reverse=True)
        
        # Keep the page with the highest score
        keep_score = page_scores[0]
        keep_page = keep_score["page"]
        keep_title = keep_score["title"]
        keep_time = keep_score["created_time"]
        
        logger.info(f"  ✓ KEEPING: {keep_title}")
        logger.info(f"    Created: {keep_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"    Content Score: {keep_score['total_score']} "
                   f"(Takeaways: {keep_score['has_key_takeaways']}, "
                   f"Actions: {keep_score['has_action_items']}, "
                   f"Transcript: {keep_score['has_transcript']}, "
                   f"{keep_score['transcript_length']} chars)")

        kept_count += 1

        # Delete other duplicates
        for dup_score in page_scores[1:]:
            dup_page = dup_score["page"]
            dup_title = dup_score["title"]
            dup_time = dup_score["created_time"]
            dup_id = dup_page["id"]
            dup_score_val = dup_score["total_score"]

            if dry_run:
                logger.info(f"  [DRY RUN] Would delete: {dup_title}")
                logger.info(f"    Created: {dup_time.strftime('%Y-%m-%d %H:%M:%S')}, Score: {dup_score_val}")
            else:
                try:
                    logger.info(f"  Deleting: {dup_title} (Score: {dup_score_val})")

                    # Archive (soft delete) the page
                    _wait_for_rate_limit()
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
    logger.info(f"Pages kept (most complete content): {kept_count}")

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
