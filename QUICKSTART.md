# Quick Start Guide

Get up and running in 5 minutes!

## 1. Install Dependencies (2 minutes)

```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate     # Windows

# Install packages
pip install -r requirements.txt
```

## 2. Get API Credentials (2 minutes)

### Avoma API Key
1. Avoma → Settings → Organization → Developer
2. Create API key → Copy it

### Notion Integration
1. Go to: https://www.notion.so/my-integrations
2. Create integration → Copy token
3. Open your "Notes" database → Share with integration

### Notion Database ID
1. Open "Notes" database
2. Copy link
3. Extract ID from URL (32-character string)

## 3. Configure (1 minute)

```bash
# Copy example
cp .env.example .env

# Edit .env and add:
# - AVOMA_API_KEY
# - NOTION_API_KEY
# - NOTION_DATABASE_ID
```

## 4. Run! (30 seconds)

```bash
# Test connections
python main.py --test-connection

# Verify schema
python main.py --verify-schema

# Dry run (recommended first)
python main.py --dry-run

# Real import
python main.py
```

## Done! 🎉

Your meetings are now in Notion!

---

## What Gets Imported?

✅ Meeting titles and dates
✅ Participants and host
✅ Meeting duration
✅ Full transcripts
✅ Notes and action items
✅ Recording links
✅ Tags and metadata

## Common Issues

**"Invalid API key"**
- Check `.env` has correct Avoma key
- Ensure you have Admin access

**"Failed to connect to Notion"**
- Verify integration token in `.env`
- Confirm database is shared with integration
- Check database ID is correct

**"Missing properties"**
- Run: `python main.py --verify-schema`
- Add missing properties to Notion database

## Need Help?

See the full [README.md](README.md) for:
- Detailed troubleshooting
- Advanced options
- API documentation
- Performance tips
