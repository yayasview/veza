"""Data transformation module for converting Avoma data to Notion format."""

from typing import Dict, List, Any, Optional
from datetime import datetime
from dateutil import parser as date_parser

from .logger import setup_logger

logger = setup_logger()


class MeetingTransformer:
    """Transform Avoma meeting data to Notion page format."""

    # Maximum characters per Notion block
    MAX_BLOCK_SIZE = 1900

    # Maximum total characters for transcript before warning
    MAX_TRANSCRIPT_SIZE = 10000

    @staticmethod
    def _safe_get(data: Optional[Dict], *keys, default=None):
        """Safely get nested dictionary values."""
        if data is None:
            return default

        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default

            if current is None:
                return default

        return current if current is not None else default

    @staticmethod
    def _split_into_blocks(text: str, max_size: int = MAX_BLOCK_SIZE) -> List[str]:
        """Split text into chunks suitable for Notion blocks."""
        if not text:
            return []

        chunks = []
        for i in range(0, len(text), max_size):
            chunks.append(text[i : i + max_size])

        return chunks

    @staticmethod
    def _format_date(date_string: Optional[str]) -> Optional[str]:
        """Format date string to ISO format for Notion."""
        if not date_string:
            return None

        try:
            # Parse the date string
            dt = date_parser.parse(date_string)
            # Return ISO format
            return dt.isoformat()
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_string}': {e}")
            return None

    @staticmethod
    def _extract_participants(meeting: Dict[str, Any]) -> List[str]:
        """Extract participant names from meeting data."""
        participants = []

        # Try different possible field names
        attendees = (
            meeting.get("participants")
            or meeting.get("attendees")
            or meeting.get("invitees")
            or []
        )

        for participant in attendees:
            if isinstance(participant, str):
                participants.append(participant)
            elif isinstance(participant, dict):
                # Try to get name or email
                name = (
                    participant.get("name")
                    or participant.get("display_name")
                    or participant.get("email")
                    or participant.get("user_name")
                )
                if name:
                    participants.append(name)

        return participants

    @staticmethod
    def _calculate_duration(meeting: Dict[str, Any]) -> Optional[int]:
        """Calculate meeting duration in minutes."""
        # Check if duration is provided directly
        duration = meeting.get("duration") or meeting.get("duration_minutes")

        if duration:
            return int(duration)

        # Try to calculate from start and end times
        start = meeting.get("start_at") or meeting.get("start_time")
        end = meeting.get("end_at") or meeting.get("end_time")

        if start and end:
            try:
                start_dt = date_parser.parse(start)
                end_dt = date_parser.parse(end)
                duration_seconds = (end_dt - start_dt).total_seconds()
                return int(duration_seconds / 60)
            except Exception as e:
                logger.warning(f"Failed to calculate duration: {e}")

        return None

    def transform_meeting(self, meeting_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform Avoma meeting data to Notion page format.

        Args:
            meeting_data: Complete meeting data from Avoma

        Returns:
            Transformed data ready for Notion import
        """
        meeting = meeting_data.get("meeting", {})
        transcript = meeting_data.get("transcript", {})
        notes = meeting_data.get("notes", {})
        recording = meeting_data.get("recording", {})

        # Extract basic meeting information
        title = (
            self._safe_get(meeting, "subject")
            or self._safe_get(meeting, "title")
            or self._safe_get(meeting, "name")
            or "Untitled Meeting"
        )

        meeting_id = str(self._safe_get(meeting, "uuid") or self._safe_get(meeting, "id", "unknown"))
        start_date = self._format_date(
            self._safe_get(meeting, "start_at") or self._safe_get(meeting, "start_time")
        )
        end_date = self._format_date(
            self._safe_get(meeting, "end_at") or self._safe_get(meeting, "end_time")
        )
        created_at = self._format_date(
            self._safe_get(meeting, "created_at")
            or self._safe_get(meeting, "created")
            or self._safe_get(meeting, "created_time")
        )

        participants = self._extract_participants(meeting)
        duration = self._calculate_duration(meeting)

        # Extract host information
        host = (
            self._safe_get(meeting, "host_name")
            or self._safe_get(meeting, "organizer_email")
            or self._safe_get(meeting, "organizer", "name")
            or self._safe_get(meeting, "host", "name")
            or "Unknown"
        )

        # Extract status
        status = self._safe_get(meeting, "status", "Completed")

        # Extract tags
        tags = self._safe_get(meeting, "tags", [])
        if not isinstance(tags, list):
            tags = []

        # Extract recording URL
        recording_url = (
            self._safe_get(recording, "video_url")
            or self._safe_get(recording, "url")
            or self._safe_get(meeting, "recording_url")
        )

        # Build Notion properties (using existing database schema)
        properties = {
            "Name": {"title": [{"text": {"content": title[:2000]}}]},  # Using existing "Name" field
            "Avoma ID": {"rich_text": [{"text": {"content": meeting_id}}]},
        }

        # Add date property if available
        if start_date:
            date_prop = {"start": start_date}
            if end_date:
                date_prop["end"] = end_date
            properties["Date"] = {"date": date_prop}

        # Add duration if available
        if duration:
            properties["Duration"] = {"number": duration}

        # Add participants
        if participants:
            # Notion multi-select doesn't allow commas in values, so sanitize them
            sanitized_participants = [p.replace(",", " -")[:100] for p in participants[:20]]
            properties["Participants"] = {
                "multi_select": [{"name": p} for p in sanitized_participants]
            }

        # Add host
        if host:
            # Sanitize host name too (for select fields)
            properties["Host"] = {"select": {"name": host.replace(",", " -")[:100]}}

        # Add recording URL (using existing "Recording" field)
        if recording_url:
            properties["Recording"] = {"url": recording_url[:2000]}

        # Build page content blocks
        children = []

        # Add AI-generated notes section (from insights endpoint)
        # Use direct .get() to avoid _safe_get bug with non-None defaults
        ai_notes = notes.get("ai_notes", []) if notes else []

        if isinstance(ai_notes, list) and ai_notes:
            # Group notes by type
            key_takeaways = []
            action_items = []

            for note in ai_notes:
                if isinstance(note, dict):
                    text = note.get("text", "")
                    note_type = note.get("note_type", "")

                    if note_type == "key_takeaways" and text:
                        key_takeaways.append(text)
                    elif note_type == "action_item" and text:
                        action_items.append(text)

            # Add Key Takeaways section
            if key_takeaways:
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Key Takeaways"}}],
                        "color": "default",
                    },
                })

                for takeaway in key_takeaways[:30]:  # Limit to 30
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"text": {"content": takeaway[:2000]}}]
                        },
                    })

            # Add Action Items section
            if action_items:
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Action Items"}}],
                        "color": "default",
                    },
                })

                for action in action_items[:30]:  # Limit to 30
                    children.append({
                        "object": "block",
                        "type": "to_do",
                        "to_do": {
                            "rich_text": [{"text": {"content": action[:2000]}}],
                            "checked": False,
                        },
                    })

        # Add keywords if available
        # Keywords structure: {"popular": [{"word": "...", "score": ..., "count": ...}], "occurrences": [...]}
        keywords_data = notes.get("keywords") if notes else None
        if keywords_data and isinstance(keywords_data, dict):
            popular_keywords = keywords_data.get("popular", [])
            if popular_keywords and isinstance(popular_keywords, list):
                # Extract the "word" field from each keyword object
                keywords_list = [kw.get("word", "") for kw in popular_keywords if isinstance(kw, dict) and kw.get("word")]
                keywords_text = ", ".join(keywords_list[:20])

                if keywords_text:
                    children.append({
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "rich_text": [
                                {"text": {"content": f"🔑 Key Topics: {keywords_text}"}}
                            ],
                            "color": "blue_background",
                            "icon": {"emoji": "🔑"},
                        },
                    })

        # Add transcript section
        # Transcript is a list of dictionaries with speaker segments
        transcript_segments = transcript.get("transcript", []) if transcript else []

        if transcript_segments and isinstance(transcript_segments, list):
            # Extract text from each segment and join them
            transcript_text = " ".join(
                segment.get("transcript", "") for segment in transcript_segments if isinstance(segment, dict)
            )

            if transcript_text.strip():
                children.append({
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"text": {"content": "Transcript"}}],
                        "color": "default",
                    },
                })

                # Check transcript size
                if len(transcript_text) > self.MAX_TRANSCRIPT_SIZE:
                    # Add warning callout
                    children.append({
                        "object": "block",
                        "type": "callout",
                        "callout": {
                            "rich_text": [
                                {
                                    "text": {
                                        "content": f"⚠️ Transcript is very long ({len(transcript_text):,} characters). "
                                        f"Only the first {self.MAX_TRANSCRIPT_SIZE:,} characters are included below. "
                                        "Consider viewing the full transcript in Avoma or the recording."
                                    }
                                }
                            ],
                            "color": "yellow_background",
                        },
                    })
                    # Truncate transcript
                    transcript_text = transcript_text[: self.MAX_TRANSCRIPT_SIZE]

                # Split transcript into blocks
                transcript_chunks = self._split_into_blocks(transcript_text)

                # Add as toggle block to save space
                children.append({
                    "object": "block",
                    "type": "toggle",
                    "toggle": {
                        "rich_text": [{"text": {"content": "View Full Transcript"}}],
                        "children": [
                            {
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {"rich_text": [{"text": {"content": chunk}}]},
                            }
                            for chunk in transcript_chunks[:100]  # Limit to 100 blocks
                        ],
                    },
                })

        # Add metadata section
        children.append({
            "object": "block",
            "type": "divider",
            "divider": {},
        })

        children.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [
                    {
                        "text": {
                            "content": f"📊 Exported from Avoma | Meeting ID: {meeting_id} | "
                            f"Exported on: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        }
                    }
                ],
                "color": "gray_background",
                "icon": {"emoji": "📊"},
            },
        })

        return {"properties": properties, "children": children}

    def transform_meetings(self, meetings_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Transform multiple meetings.

        Args:
            meetings_data: List of complete meeting data

        Returns:
            List of transformed meetings ready for Notion
        """
        transformed = []
        total = len(meetings_data)

        logger.info(f"Transforming {total} meetings...")

        for i, meeting_data in enumerate(meetings_data, 1):
            try:
                transformed_meeting = self.transform_meeting(meeting_data)
                transformed.append(transformed_meeting)

                if i % 10 == 0:
                    logger.debug(f"Transformed {i}/{total} meetings")

            except Exception as e:
                # Get meeting title for error logging
                title = "Unknown"
                try:
                    meeting = meeting_data.get("meeting", {})
                    title = meeting.get("subject") or meeting.get("title") or "Unknown"
                except:
                    pass

                logger.error(f"Failed to transform meeting '{title}': {e}")

                # Add a minimal entry to maintain consistency
                transformed.append({
                    "properties": {
                        "Name": {"title": [{"text": {"content": f"[ERROR] {title}"}}]},
                        "Avoma ID": {
                            "rich_text": [
                                {"text": {"content": str(meeting_data.get("meeting", {}).get("uuid") or meeting_data.get("meeting", {}).get("id", "unknown"))}}
                            ]
                        },
                    },
                    "children": [
                        {
                            "object": "block",
                            "type": "callout",
                            "callout": {
                                "rich_text": [
                                    {"text": {"content": f"⚠️ Error transforming this meeting: {str(e)}"}}
                                ],
                                "color": "red_background",
                                "icon": {"emoji": "⚠️"},
                            },
                        }
                    ],
                })

        logger.info(f"✓ Successfully transformed {len(transformed)} meetings")
        return transformed
