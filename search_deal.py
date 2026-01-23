#!/usr/bin/env python3
"""Script to search for a deal in HubSpot and find related meeting notes in Notion."""

import sys
import json
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from src.hubspot_client import HubSpotClient, HubSpotAPIError
from src.notion_client_wrapper import NotionClientWrapper, NotionAPIError
from src.logger import setup_logger

logger = setup_logger()


def extract_text_from_blocks(blocks: list) -> str:
    """Extract plain text content from Notion blocks."""
    text_parts = []
    for block in blocks:
        block_type = block.get("type")
        if block_type and block_type in block:
            rich_text = block[block_type].get("rich_text", [])
            for text_item in rich_text:
                text_parts.append(text_item.get("plain_text", ""))
    return "\n".join(text_parts)


def format_deal_info(deal: dict) -> str:
    """Format deal information for display."""
    props = deal.get("properties", {})
    output = []
    output.append(f"\n{'='*60}")
    output.append(f"DEAL: {props.get('dealname', 'Unknown')}")
    output.append(f"{'='*60}")
    output.append(f"  ID: {deal.get('id')}")
    output.append(f"  Stage: {props.get('dealstage', 'Unknown')}")
    output.append(f"  Amount: {props.get('amount', 'N/A')}")
    output.append(f"  Close Date: {props.get('closedate', 'N/A')}")
    output.append(f"  Created: {props.get('createdate', 'N/A')}")
    output.append(f"  Last Modified: {props.get('hs_lastmodifieddate', 'N/A')}")

    if props.get('description'):
        output.append(f"  Description: {props.get('description')}")

    return "\n".join(output)


def format_notion_page(page: dict, include_content: bool = False, content: Optional[list] = None) -> str:
    """Format Notion page information for display."""
    props = page.get("properties", {})
    output = []

    # Get title
    title = "Unknown"
    title_prop = props.get("Name", {})
    if title_prop.get("title"):
        title = title_prop["title"][0].get("plain_text", "Unknown") if title_prop["title"] else "Unknown"

    output.append(f"\n{'-'*60}")
    output.append(f"MEETING: {title}")
    output.append(f"{'-'*60}")

    # Get date
    date_prop = props.get("Date", {})
    if date_prop.get("date"):
        start = date_prop["date"].get("start", "N/A")
        output.append(f"  Date: {start}")

    # Get participants
    participants_prop = props.get("Participants", {})
    if participants_prop.get("multi_select"):
        participants = [p.get("name", "") for p in participants_prop["multi_select"]]
        if participants:
            output.append(f"  Participants: {', '.join(participants)}")

    # Get status
    status_prop = props.get("Status", {})
    if status_prop.get("select"):
        output.append(f"  Status: {status_prop['select'].get('name', 'N/A')}")

    # Get URL
    output.append(f"  Notion URL: {page.get('url', 'N/A')}")

    # Include content if requested
    if include_content and content:
        text_content = extract_text_from_blocks(content)
        if text_content.strip():
            output.append(f"\n  NOTES PREVIEW:")
            output.append(f"  {'-'*40}")
            # Truncate if too long
            preview = text_content[:1500]
            if len(text_content) > 1500:
                preview += "\n  ... [truncated]"
            for line in preview.split("\n"):
                output.append(f"    {line}")

    return "\n".join(output)


def search_hubspot_deal(search_term: str) -> list:
    """Search for deals in HubSpot."""
    try:
        client = HubSpotClient()
        deals = client.search_deals(search_term)
        return deals
    except ValueError as e:
        logger.warning(f"HubSpot not configured: {e}")
        return []
    except HubSpotAPIError as e:
        logger.error(f"HubSpot API error: {e}")
        return []


def search_notion_meetings(search_term: str, limit: int = 5) -> list:
    """Search for meeting notes in Notion."""
    try:
        client = NotionClientWrapper()
        pages = client.search_pages(search_term)

        # Get content for top results
        results = []
        for page in pages[:limit]:
            try:
                content = client.get_page_content(page["id"])
                results.append({"page": page, "content": content})
            except NotionAPIError:
                results.append({"page": page, "content": []})

        return results
    except ValueError as e:
        logger.warning(f"Notion not configured: {e}")
        return []
    except NotionAPIError as e:
        logger.error(f"Notion API error: {e}")
        return []


def get_recent_meetings(limit: int = 5) -> list:
    """Get the most recent meetings from Notion."""
    try:
        client = NotionClientWrapper()
        pages = client.get_all_pages(sort_by_date=True)

        results = []
        for page in pages[:limit]:
            try:
                content = client.get_page_content(page["id"])
                results.append({"page": page, "content": content})
            except NotionAPIError:
                results.append({"page": page, "content": []})

        return results
    except ValueError as e:
        logger.warning(f"Notion not configured: {e}")
        return []
    except NotionAPIError as e:
        logger.error(f"Notion API error: {e}")
        return []


def main(search_term: str = "Neue World"):
    """Main function to search for deal and meeting notes."""
    print(f"\n{'#'*60}")
    print(f"# Searching for: {search_term}")
    print(f"# Time: {datetime.now().isoformat()}")
    print(f"{'#'*60}")

    # Search HubSpot
    print("\n\n[HUBSPOT DEALS]")
    print("="*60)
    deals = search_hubspot_deal(search_term)

    if deals:
        print(f"Found {len(deals)} matching deal(s):")
        for deal in deals:
            print(format_deal_info(deal))
    else:
        print(f"No deals found matching '{search_term}'")

    # Search Notion for matching meetings
    print("\n\n[NOTION MEETING NOTES - Search Results]")
    print("="*60)
    notion_results = search_notion_meetings(search_term, limit=5)

    if notion_results:
        print(f"Found {len(notion_results)} meeting(s) matching '{search_term}':")
        for result in notion_results:
            print(format_notion_page(
                result["page"],
                include_content=True,
                content=result["content"]
            ))
    else:
        print(f"No meeting notes found matching '{search_term}'")

        # If no matching meetings, show recent meetings
        print("\n\n[NOTION - Most Recent Meetings]")
        print("="*60)
        recent = get_recent_meetings(limit=5)
        if recent:
            print(f"Showing {len(recent)} most recent meeting(s):")
            for result in recent:
                print(format_notion_page(
                    result["page"],
                    include_content=True,
                    content=result["content"]
                ))
        else:
            print("No meetings found in Notion database")

    print("\n")


if __name__ == "__main__":
    search_term = sys.argv[1] if len(sys.argv) > 1 else "Neue World"
    main(search_term)
