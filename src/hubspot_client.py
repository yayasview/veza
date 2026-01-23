"""HubSpot API client for deal and meeting lookups."""

import requests
from typing import Dict, List, Optional, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from .config import Config
from .logger import setup_logger

logger = setup_logger()


def is_retryable_error(exception):
    """Check if the exception is retryable (not a 4xx client error)."""
    if isinstance(exception, HubSpotAPIError):
        return exception.status_code is None or exception.status_code >= 500
    return True


class HubSpotAPIError(Exception):
    """Exception raised for HubSpot API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class HubSpotClient:
    """Client for interacting with HubSpot API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the HubSpot client.

        Args:
            api_key: HubSpot private app access token (defaults to Config.HUBSPOT_API_KEY)
        """
        self.api_key = api_key or Config.HUBSPOT_API_KEY
        self.base_url = Config.HUBSPOT_BASE_URL

        if not self.api_key:
            raise ValueError("HubSpot API key is required")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def test_connection(self) -> bool:
        """
        Test the HubSpot API connection.

        Returns:
            True if connection is successful
        """
        try:
            logger.info("Testing HubSpot API connection...")
            response = self.session.get(f"{self.base_url}/crm/v3/objects/deals?limit=1")
            response.raise_for_status()
            logger.info("HubSpot API connection successful")
            return True
        except requests.RequestException as e:
            logger.error(f"HubSpot API connection failed: {e}")
            raise HubSpotAPIError(f"Failed to connect to HubSpot: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception(is_retryable_error),
        reraise=True,
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Make an API request to HubSpot."""
        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
            )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            error_msg = f"HubSpot API error: {e}"
            try:
                error_data = e.response.json()
                error_msg = f"HubSpot API error: {error_data.get('message', str(e))}"
            except Exception:
                pass
            raise HubSpotAPIError(error_msg, status_code)
        except requests.RequestException as e:
            raise HubSpotAPIError(f"Request failed: {e}")

    def search_deals(self, query: str, properties: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for deals by name or other criteria.

        Args:
            query: Search query string
            properties: List of deal properties to include in results

        Returns:
            List of matching deals
        """
        if properties is None:
            properties = [
                "dealname",
                "dealstage",
                "amount",
                "closedate",
                "pipeline",
                "hubspot_owner_id",
                "createdate",
                "notes_last_updated",
                "hs_lastmodifieddate",
            ]

        search_body = {
            "query": query,
            "properties": properties,
            "limit": 100,
        }

        logger.info(f"Searching HubSpot deals for: {query}")
        result = self._make_request(
            method="POST",
            endpoint="/crm/v3/objects/deals/search",
            json_data=search_body,
        )

        deals = result.get("results", [])
        logger.info(f"Found {len(deals)} matching deals")
        return deals

    def get_deal(self, deal_id: str, properties: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get a specific deal by ID.

        Args:
            deal_id: HubSpot deal ID
            properties: List of properties to retrieve

        Returns:
            Deal data
        """
        params = {}
        if properties:
            params["properties"] = ",".join(properties)

        return self._make_request(
            method="GET",
            endpoint=f"/crm/v3/objects/deals/{deal_id}",
            params=params,
        )

    def get_deal_associations(self, deal_id: str, to_object_type: str) -> List[Dict[str, Any]]:
        """
        Get associations for a deal (e.g., contacts, companies, notes).

        Args:
            deal_id: HubSpot deal ID
            to_object_type: Type of associated object (contacts, companies, notes, etc.)

        Returns:
            List of associations
        """
        result = self._make_request(
            method="GET",
            endpoint=f"/crm/v3/objects/deals/{deal_id}/associations/{to_object_type}",
        )
        return result.get("results", [])

    def get_deal_notes(self, deal_id: str) -> List[Dict[str, Any]]:
        """
        Get notes associated with a deal.

        Args:
            deal_id: HubSpot deal ID

        Returns:
            List of notes with their content
        """
        associations = self.get_deal_associations(deal_id, "notes")
        notes = []

        for assoc in associations:
            note_id = assoc.get("id")
            if note_id:
                try:
                    note = self._make_request(
                        method="GET",
                        endpoint=f"/crm/v3/objects/notes/{note_id}",
                        params={"properties": "hs_note_body,hs_timestamp,hs_lastmodifieddate"},
                    )
                    notes.append(note)
                except HubSpotAPIError as e:
                    logger.warning(f"Failed to fetch note {note_id}: {e}")

        return notes

    def get_deal_with_details(self, deal_id: str) -> Dict[str, Any]:
        """
        Get a deal with all associated details.

        Args:
            deal_id: HubSpot deal ID

        Returns:
            Deal data with associations
        """
        properties = [
            "dealname",
            "dealstage",
            "amount",
            "closedate",
            "pipeline",
            "hubspot_owner_id",
            "createdate",
            "notes_last_updated",
            "hs_lastmodifieddate",
            "description",
        ]

        deal = self.get_deal(deal_id, properties)

        deal["associations"] = {
            "notes": self.get_deal_notes(deal_id),
        }

        return deal
