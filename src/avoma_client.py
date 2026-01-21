"""Avoma API client for fetching meeting data."""

import time
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .config import Config
from .logger import setup_logger

logger = setup_logger()


class AvomaAPIError(Exception):
    """Exception raised for Avoma API errors."""
    pass


class AvomaClient:
    """Client for interacting with the Avoma API."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Avoma client.

        Args:
            api_key: Avoma API key (defaults to Config.AVOMA_API_KEY)
        """
        self.api_key = api_key or Config.AVOMA_API_KEY
        self.base_url = Config.AVOMA_BASE_URL
        self.rate_limit = 1.0 / Config.AVOMA_RATE_LIMIT  # seconds between requests

        if not self.api_key:
            raise ValueError("Avoma API key is required")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=2, max=16),
        retry=retry_if_exception_type((requests.exceptions.RequestException, AvomaAPIError)),
    )
    def _make_request(
        self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the Avoma API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            params: Query parameters
            data: Request body data

        Returns:
            Response JSON

        Raises:
            AvomaAPIError: If the request fails
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            response = self.session.request(
                method=method, url=url, params=params, json=data, timeout=30
            )

            # Rate limiting
            time.sleep(self.rate_limit)

            # Handle different status codes
            if response.status_code == 401:
                raise AvomaAPIError("Invalid API key or unauthorized access")
            elif response.status_code == 429:
                logger.warning("Rate limit exceeded, retrying...")
                raise AvomaAPIError("Rate limit exceeded")
            elif response.status_code >= 500:
                raise AvomaAPIError(f"Server error: {response.status_code}")
            elif response.status_code >= 400:
                raise AvomaAPIError(f"Client error: {response.status_code} - {response.text}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise AvomaAPIError(f"Request failed: {e}")

    def test_connection(self) -> bool:
        """
        Test the API connection.

        Returns:
            True if connection is successful

        Raises:
            AvomaAPIError: If connection fails
        """
        try:
            logger.info("Testing Avoma API connection...")
            # Avoma API requires from_date and to_date parameters
            from datetime import datetime, timedelta
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            self._make_request("GET", "/meetings", params={
                "limit": 1,
                "from_date": from_date,
                "to_date": to_date
            })
            logger.info("✓ Avoma API connection successful")
            return True
        except Exception as e:
            logger.error(f"✗ Avoma API connection failed: {e}")
            raise

    def get_meetings(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Get a list of meetings from Avoma.

        Args:
            from_date: Start date (ISO format: YYYY-MM-DD)
            to_date: End date (ISO format: YYYY-MM-DD)
            page: Page number
            limit: Number of results per page

        Returns:
            API response with meetings list
        """
        params = {
            "page": page,
            "limit": limit,
        }

        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date

        logger.debug(f"Fetching meetings page {page} with limit {limit}")
        return self._make_request("GET", "/meetings", params=params)

    def fetch_all_meetings(
        self, from_date: Optional[str] = None, to_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch all meetings with pagination.

        Args:
            from_date: Start date (ISO format: YYYY-MM-DD)
            to_date: End date (ISO format: YYYY-MM-DD), defaults to today

        Returns:
            List of all meetings
        """
        # Default to_date to today if not provided
        if not to_date:
            from datetime import datetime
            to_date = datetime.now().strftime("%Y-%m-%d")

        all_meetings = []
        page = 1
        limit = Config.BATCH_SIZE

        logger.info("Fetching all meetings from Avoma...")
        logger.info(f"Date range: {from_date or 'beginning'} to {to_date}")

        while True:
            try:
                response = self.get_meetings(
                    from_date=from_date, to_date=to_date, page=page, limit=limit
                )

                # Handle different response structures
                meetings = response.get("data", response.get("results", []))

                if not meetings:
                    break

                all_meetings.extend(meetings)

                # Get total count for progress reporting
                total_count = response.get("count", response.get("total", 0))
                progress_str = f"{len(all_meetings)}/{total_count}" if total_count else str(len(all_meetings))
                logger.info(f"Fetched page {page}: {len(meetings)} meetings (total: {progress_str})")

                # Check if there are more pages using the "next" field (most reliable)
                has_next = response.get("next") is not None
                has_more = response.get("has_more", False)

                # Break if no more pages
                if not has_next and not has_more:
                    break

                # Also break if we've fetched all meetings based on count
                if total_count > 0 and len(all_meetings) >= total_count:
                    break

                page += 1

            except Exception as e:
                logger.error(f"Error fetching meetings on page {page}: {e}")
                raise

        logger.info(f"✓ Total meetings fetched: {len(all_meetings)}")
        return all_meetings

    def get_meeting_details(self, meeting_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific meeting.

        Args:
            meeting_id: Meeting ID

        Returns:
            Meeting details
        """
        logger.debug(f"Fetching details for meeting {meeting_id}")
        return self._make_request("GET", f"/meetings/{meeting_id}")

    def get_meeting_transcript(self, meeting: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get transcript for a specific meeting.

        Args:
            meeting: Meeting object (must contain uuid or id, and transcription_uuid if available)

        Returns:
            Transcript data or None if not available
        """
        try:
            # Get transcription_uuid from the meeting object
            transcription_uuid = meeting.get("transcription_uuid")

            if not transcription_uuid:
                logger.debug(f"No transcription_uuid for meeting {meeting.get('uuid') or meeting.get('id')}")
                return None

            logger.debug(f"Fetching transcript {transcription_uuid}")
            return self._make_request("GET", f"/transcriptions/{transcription_uuid}")
        except AvomaAPIError as e:
            if "404" in str(e):
                logger.debug(f"Transcript not found: {transcription_uuid}")
                return None
            raise

    def get_meeting_notes(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """
        Get notes/insights for a specific meeting.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Insights data (ai_notes, keywords, speakers) or None if not available
        """
        try:
            logger.debug(f"Fetching insights for meeting {meeting_id}")
            return self._make_request("GET", f"/meetings/{meeting_id}/insights")
        except AvomaAPIError as e:
            if "404" in str(e) or "405" in str(e):
                logger.debug(f"No insights available for meeting {meeting_id}")
                return None
            raise

    def get_meeting_recording(self, meeting: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get recording information for a specific meeting.

        Args:
            meeting: Meeting object (must contain recording_uuid if available)

        Returns:
            Recording data (video_url, audio_url) or None if not available
        """
        try:
            # Get recording_uuid from the meeting object
            recording_uuid = meeting.get("recording_uuid")

            if not recording_uuid:
                logger.debug(f"No recording_uuid for meeting {meeting.get('uuid') or meeting.get('id')}")
                return None

            logger.debug(f"Fetching recording {recording_uuid}")
            return self._make_request("GET", f"/recordings/{recording_uuid}")
        except AvomaAPIError as e:
            if "404" in str(e):
                logger.debug(f"Recording not found: {recording_uuid}")
                return None
            raise

    def get_complete_meeting_data(self, meeting_id: str) -> Dict[str, Any]:
        """
        Get complete data for a meeting including details, transcript, notes, and recording.

        Args:
            meeting_id: Meeting UUID

        Returns:
            Complete meeting data
        """
        logger.debug(f"Fetching complete data for meeting {meeting_id}")

        # First get the full meeting details (includes transcription_uuid, recording_uuid, etc.)
        meeting = self.get_meeting_details(meeting_id)

        data = {
            "meeting": meeting,
            "transcript": self.get_meeting_transcript(meeting),
            "notes": self.get_meeting_notes(meeting_id),
            "recording": self.get_meeting_recording(meeting),
        }

        return data

    def fetch_all_complete_meetings(
        self, meetings: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fetch complete data for all meetings.

        Args:
            meetings: List of basic meeting data

        Returns:
            List of complete meeting data
        """
        complete_meetings = []
        total = len(meetings)

        logger.info(f"Fetching complete data for {total} meetings...")

        for i, meeting in enumerate(meetings, 1):
            meeting_id = meeting.get("uuid") or meeting.get("id")

            if not meeting_id:
                logger.warning(f"Meeting {i} has no ID/UUID, skipping")
                continue

            try:
                complete_data = self.get_complete_meeting_data(meeting_id)
                complete_meetings.append(complete_data)

                if i % 10 == 0:
                    logger.info(f"Progress: {i}/{total} meetings processed")

            except Exception as e:
                logger.error(f"Error fetching complete data for meeting {meeting_id}: {e}")
                # Store partial data
                complete_meetings.append({
                    "meeting": meeting,
                    "transcript": None,
                    "notes": None,
                    "recording": None,
                    "error": str(e),
                })

        logger.info(f"✓ Complete data fetched for {len(complete_meetings)} meetings")
        return complete_meetings
