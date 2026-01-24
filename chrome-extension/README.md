# Google Meet Auto Record Chrome Extension

Automatically start recording and transcription when joining a Google Meet call.

## Features

- **Auto Record**: Automatically starts meeting recording when you join
- **Auto Transcript**: Automatically enables captions/transcription
- **Settings Popup**: Easy toggle controls for each feature
- **Status Indicator**: Shows current recording/transcript status

## Installation

### Load as Unpacked Extension (Developer Mode)

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **Load unpacked**
4. Select the `chrome-extension` folder
5. The extension icon should appear in your toolbar

### Pin the Extension

1. Click the puzzle piece icon in Chrome toolbar
2. Find "Google Meet Auto Record"
3. Click the pin icon to keep it visible

## Usage

1. **Enable/Disable**: Click the extension icon to toggle features
2. **Join a Meeting**: Simply join any Google Meet
3. **Automatic Actions**: The extension will:
   - Detect when you've joined the meeting
   - Automatically click the record button (if enabled)
   - Automatically enable captions (if enabled)

## Settings

Click the extension icon to access settings:

- **Extension Enabled**: Master switch to enable/disable all features
- **Auto Record**: Toggle automatic recording on/off
- **Auto Transcript**: Toggle automatic captions on/off

## Important Notes

### Recording Permissions

- Recording requires appropriate Google Workspace permissions
- You may need to be the meeting organizer or have recording rights
- Some organizations restrict recording capabilities

### Known Limitations

- Google Meet's UI changes occasionally, which may affect button detection
- Recording may require consent from all participants depending on settings
- The extension cannot bypass organizational restrictions

## Troubleshooting

### Recording doesn't start automatically

1. Ensure you have recording permissions for the meeting
2. Check that the extension is enabled (click the icon)
3. Open Chrome DevTools (F12) and check console for `[Meet Auto Record]` logs
4. Try refreshing the Google Meet page

### Extension not detecting the meeting

The extension waits for the meeting to fully load before attempting to start recording. If it's not detecting the meeting:

1. Wait a few seconds after joining
2. Check the console logs for status messages
3. Ensure you're on a `meet.google.com` URL

## Development

### File Structure

```
chrome-extension/
├── manifest.json      # Extension configuration
├── background.js      # Service worker
├── content.js         # Main logic (runs on Meet pages)
├── popup.html         # Settings popup UI
├── popup.js           # Popup functionality
├── create_icons.py    # Icon generation script
└── icons/
    ├── icon16.png
    ├── icon48.png
    └── icon128.png
```

### Customizing Icons

Run the icon generator or replace with your own PNG files:
- `icon16.png` - 16x16 pixels (toolbar)
- `icon48.png` - 48x48 pixels (extensions page)
- `icon128.png` - 128x128 pixels (Chrome Web Store)

## Privacy

This extension:
- Only runs on Google Meet pages
- Does not collect or transmit any data
- Stores settings locally in Chrome
- Does not access your Google account

## License

MIT License - Feel free to modify and distribute.
