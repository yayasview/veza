# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2026-01-20

### Initial Release

#### Features
- Complete Avoma meeting data export (meetings, transcripts, notes, recordings)
- Automatic transformation to Notion database format
- Robust error handling with retry logic
- Rate limiting for both Avoma and Notion APIs
- Caching system for resumable exports
- Dry-run mode for testing without importing
- Schema validation for Notion database
- Comprehensive logging (console + file)
- Progress tracking and status updates

#### Components
- **Avoma Client**: Full API integration with pagination and retry logic
- **Notion Client**: Wrapper around official Notion SDK with enhancements
- **Transformer**: Smart data mapping from Avoma to Notion format
- **Configuration**: Environment-based configuration management
- **Logger**: Dual-output logging system

#### Data Exported
- Meeting titles and subjects
- Start/end dates and times
- Duration in minutes
- Full participant lists
- Meeting hosts/organizers
- Complete transcripts (with length management)
- Meeting notes and summaries
- Action items (as Notion to-do blocks)
- Recording URLs
- Tags and metadata
- Meeting status
- Avoma meeting IDs (for reference)

#### Documentation
- Comprehensive README with setup instructions
- Quick Start guide for fast setup
- Schema example with property definitions
- Setup verification script
- Troubleshooting guide
- Example configuration files

#### Developer Features
- Type hints throughout codebase
- Modular architecture for easy extension
- Configurable rate limits
- Batch size controls
- Date range filtering
- Force refresh options
- JSON data exports at each stage
