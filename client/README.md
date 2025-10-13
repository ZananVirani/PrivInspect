# Privacy Inspector Demo - Chrome Extension

## Quick Setup Instructions

### 1. Load Extension into Chrome

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right corner)
3. Click **"Load unpacked"**
4. Select this folder: `/Users/zananvirani/Desktop/PrivInspect/chrome-extension/`
5. The extension should now appear in your extensions list

### 2. Test the Extension

1. Click the extension icon in Chrome's toolbar (you may need to pin it first)
2. You should see a popup with "Hello World" and extension information
3. Open the Developer Console (F12) to see console logs from the extension

### 3. Missing Icons

The extension references icon files that don't exist yet. You can:

- **Option A**: Create simple 16x16, 32x32, 48x48, and 128x128 PNG icons in the `icons/` folder
- **Option B**: Remove the icon references from `manifest.json` temporarily
- **Option C**: Use placeholder icons from any source

## File Structure

```
chrome-extension/
├── manifest.json          # Extension configuration
├── background.js          # Background service worker
├── content.js            # Runs on web pages
├── popup.html            # Extension popup UI
├── popup.js              # Popup functionality
├── style.css             # Popup styling
├── icons/                # Extension icons (create these)
└── README.md             # This file
```

## Features Included

- ✅ Manifest V3 compliance
- ✅ All required permissions for privacy analysis
- ✅ Background service worker
- ✅ Content scripts on all pages
- ✅ Interactive popup with "Hello World"
- ✅ Extension status information
- ✅ Current page information display
- ✅ Test buttons for functionality
- ✅ Local storage integration
- ✅ Proper error handling

## Next Steps for Privacy Analysis

This extension is ready for you to add:

1. Cookie analysis functionality
2. Script detection and analysis
3. Network request monitoring
4. Integration with your FastAPI backend
5. Privacy scoring algorithms

## Troubleshooting

- If extension doesn't load: Check Developer Console for errors
- If popup doesn't appear: Ensure popup.html path is correct
- If content scripts don't work: Check site permissions
- If background worker fails: Check background.js console logs

The extension is fully functional and ready for testing!
