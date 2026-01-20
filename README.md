# Avoma to Notion Export Tool

A Python tool to export all meeting data from Avoma and import it into a Notion database.

## Features

- **Complete Data Export**: Exports meetings, transcripts, notes, recordings, and participant information
- **Smart Transformation**: Automatically converts Avoma data to Notion's format
- **Robust Error Handling**: Retry logic, rate limiting, and graceful error recovery
- **Caching**: Saves intermediate results to allow resuming interrupted exports
- **Dry Run Mode**: Test the import without creating actual Notion pages
- **Schema Validation**: Verifies your Notion database has the required properties
- **Detailed Logging**: Console and file logging with progress tracking

## Prerequisites

- Python 3.7 or higher
- Avoma account with Admin access (to generate API key)
- Notion workspace with integration access

## Installation

### 1. Clone or Download This Repository

```bash
cd avoma-notion-export
```

### 2. Create a Virtual Environment

```bash
python -m venv venv

# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

## Configuration

### 1. Get Avoma API Key

1. Log into Avoma with an Admin account
2. Navigate to **Settings → Organization → Developer**
3. Create a new API key and copy it
4. Test the key:
   ```bash
   curl -H "Authorization: Bearer YOUR_KEY" https://api.avoma.com/v1/meetings
   ```

### 2. Get Notion Integration Token

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"+ New integration"**
3. Name it (e.g., "Avoma Import")
4. Select your workspace
5. Copy the **Internal Integration Token**

### 3. Share Notion Database with Integration

1. Open your "Notes" database in Notion
2. Click **"..."** (top right) → **"Connections"** → **"Connect to"**
3. Select your integration (e.g., "Avoma Import")

### 4. Get Notion Database ID

1. Open your "Notes" database in Notion
2. Click **"..."** → **"Copy link"**
3. Extract the database ID from the URL:
   ```
   https://www.notion.so/{workspace}/{DATABASE_ID}?v=...
   ```
   The DATABASE_ID is the 32-character hex string (with dashes)

### 5. Create Environment File

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:

```env
# Avoma API Configuration
AVOMA_API_KEY=your_avoma_api_key_here

# Notion API Configuration
NOTION_API_KEY=your_notion_integration_token_here
NOTION_DATABASE_ID=your_notion_database_id_here

# Optional: Export Configuration
EXPORT_FROM_DATE=2020-01-01
BATCH_SIZE=50
AVOMA_RATE_LIMIT=2
NOTION_RATE_LIMIT=3
```

## Notion Database Schema

Your Notion "Notes" database should have the following properties:

| Property Name | Type | Required | Description |
|--------------|------|----------|-------------|
| **Title** | Title | Yes | Meeting subject/title |
| **Date** | Date | Yes | Meeting start/end date |
| **Duration** | Number | No | Meeting duration in minutes |
| **Participants** | Multi-select | No | Meeting attendees |
| **Recording URL** | URL | No | Link to meeting recording |
| **Avoma ID** | Rich Text | Yes | Original Avoma meeting ID |
| **Status** | Select | No | Meeting status (Completed, Cancelled, etc.) |
| **Tags** | Multi-select | No | Meeting tags/topics |
| **Host** | Select | No | Meeting organizer |
| **Created At** | Date | No | When meeting was created in Avoma |

### Adding Properties to Notion

If your database is missing properties:

1. Open the database in Notion
2. Click **"+"** next to the last column header
3. Select the property type from the table above
4. Name it exactly as shown (case-sensitive)

**OR** run the verification command to see what's missing:

```bash
python main.py --verify-schema
```

## Usage

### Test Connections

Verify that your API credentials work:

```bash
python main.py --test-connection
```

### Verify Notion Schema

Check that your Notion database has the required properties:

```bash
python main.py --verify-schema
```

### Dry Run (Recommended First)

Test the export without creating actual Notion pages:

```bash
python main.py --dry-run
```

This will:
- Fetch all meetings from Avoma
- Transform the data
- Simulate the import
- Show you what would be created

### Full Export and Import

Run the complete export and import:

```bash
python main.py
```

### Advanced Options

```bash
# Force re-fetch from Avoma (ignore cached data)
python main.py --force-fetch

# Force re-transform data
python main.py --force-transform

# Export meetings from a specific date
python main.py --from-date 2023-01-01

# Combine options
python main.py --force-fetch --dry-run
```

### Get Help

```bash
python main.py --help
```

## How It Works

The tool follows a 4-step process:

### Step 1: Fetch Meetings List

- Retrieves all meetings from Avoma within the specified date range
- Uses pagination to handle large datasets
- Saves results to `exports/avoma_meetings_list.json`

### Step 2: Fetch Complete Meeting Data

- For each meeting, fetches:
  - Meeting details (participants, duration, etc.)
  - Transcript
  - Notes and action items
  - Recording information
- Saves results to `exports/avoma_meetings_complete.json`

### Step 3: Transform Data

- Converts Avoma data structure to Notion format
- Handles different data types and property mappings
- Splits long content into appropriate Notion blocks
- Saves results to `exports/notion_import_data.json`

### Step 4: Import to Notion

- Creates a new page in your Notion database for each meeting
- Includes all meeting data, notes, and transcripts
- Handles rate limiting and errors gracefully
- Saves failed imports to `exports/failed_imports_*.json`

## Output Files

All output files are saved in the `exports/` directory:

- `avoma_meetings_list.json` - Raw list of meetings from Avoma
- `avoma_meetings_complete.json` - Complete meeting data with transcripts/notes
- `notion_import_data.json` - Transformed data ready for Notion
- `failed_imports_*.json` - Details of any failed imports (if applicable)

Log files are saved in the `logs/` directory:

- `export_YYYYMMDD_HHMMSS.log` - Detailed log of the export process

## Troubleshooting

### "Invalid API key or unauthorized access"

- Verify your Avoma API key is correct in `.env`
- Ensure you have Admin access in Avoma
- Test with: `curl -H "Authorization: Bearer YOUR_KEY" https://api.avoma.com/v1/meetings`

### "Failed to connect to Notion"

- Verify your Notion integration token is correct in `.env`
- Ensure you shared the database with your integration
- Check that the database ID is correct (32-character hex string)

### "Missing properties" or "Mismatched property types"

- Run `python main.py --verify-schema` to see what's wrong
- Add missing properties to your Notion database manually
- Ensure property names match exactly (case-sensitive)

### "Rate limit exceeded"

- The tool includes automatic retry logic
- If issues persist, adjust rate limits in `.env`:
  ```env
  AVOMA_RATE_LIMIT=1  # Lower = slower but safer
  NOTION_RATE_LIMIT=2
  ```

### Import Failed for Some Meetings

- Check `exports/failed_imports_*.json` for details
- Common issues:
  - Property type mismatches
  - Content too long for Notion blocks
  - Missing required fields
- Fix issues and re-run (cached data will be reused)

### Out of Memory

If you have thousands of meetings:

1. Export in batches by date range:
   ```bash
   python main.py --from-date 2023-01-01 --to-date 2023-06-30
   python main.py --from-date 2023-07-01 --to-date 2023-12-31
   ```

2. Or increase your system's available memory

## Resuming Interrupted Exports

The tool caches data at each step. If interrupted:

1. Simply run the command again
2. It will resume from the last completed step
3. Use `--force-fetch` or `--force-transform` to start fresh

## After Export

### Verify Import

1. Open your Notion "Notes" database
2. Sort by "Date" to see imported meetings
3. Spot-check several meetings for accuracy

### Backup Data

Keep these files safe before cancelling Avoma:

- All files in `exports/` directory
- Any downloaded recordings (if applicable)
- Export to CSV from Notion as additional backup

### Optional: Download Recordings

If you want local copies of recordings:

1. Check `exports/avoma_meetings_complete.json`
2. Extract recording URLs
3. Download with a tool like `wget` or `curl`

## Performance

- **Avoma API**: ~2 requests/second (configurable)
- **Notion API**: ~3 requests/second (Notion's limit)
- **Estimated time**:
  - 100 meetings: ~30-45 minutes
  - 500 meetings: ~2-3 hours
  - 1000 meetings: ~4-6 hours

Times depend on:
- Number of meetings
- Size of transcripts
- Network speed
- API rate limits

## Security

- **Never commit `.env`** - It's in `.gitignore`
- Store API keys securely
- Revoke API keys after export if no longer needed
- Keep exported JSON files secure (they contain meeting data)

## Limitations

- **Transcript length**: Very long transcripts (>10,000 chars) are truncated with a warning
- **Notion blocks**: Maximum 100 blocks per toggle (for very long transcripts)
- **Participants**: Maximum 20 participants per meeting
- **Tags**: Maximum 20 tags per meeting
- **Property values**: Truncated to Notion's limits (e.g., 2000 chars for URLs)

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review the log file in `logs/`
3. Run with `--test-connection` to verify API access
4. Run with `--verify-schema` to check Notion database setup

## License

This tool is provided as-is for personal use.

## Acknowledgments

- [Avoma API](https://help.avoma.com/api-documentation)
- [Notion API](https://developers.notion.com/)
- [Notion Python SDK](https://github.com/ramnes/notion-sdk-py)
