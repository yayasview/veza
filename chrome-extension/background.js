/**
 * Google Meet Auto Record - Background Service Worker
 *
 * Handles extension lifecycle and messaging
 */

// Set default settings on install
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === 'install') {
    chrome.storage.sync.set({
      enabled: true,
      autoRecord: true,
      autoTranscript: true
    });
    console.log('[Meet Auto Record] Extension installed with default settings');
  }
});

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'GET_STATUS') {
    chrome.storage.local.get(['recordingStarted', 'transcriptStarted'], (result) => {
      sendResponse(result);
    });
    return true; // Required for async response
  }

  if (message.type === 'LOG') {
    console.log(`[Meet Auto Record] ${message.text}`);
  }
});

// Update badge when recording status changes
chrome.storage.onChanged.addListener((changes, namespace) => {
  if (namespace === 'local') {
    if (changes.recordingStarted) {
      const isRecording = changes.recordingStarted.newValue;
      chrome.action.setBadgeText({ text: isRecording ? 'REC' : '' });
      chrome.action.setBadgeBackgroundColor({ color: '#ea4335' });
    }
  }
});
