/**
 * Google Meet Auto Record - Popup Script
 */

document.addEventListener('DOMContentLoaded', async () => {
  // Get DOM elements
  const enabledToggle = document.getElementById('enabledToggle');
  const autoRecordToggle = document.getElementById('autoRecordToggle');
  const autoTranscriptToggle = document.getElementById('autoTranscriptToggle');
  const masterToggle = document.getElementById('masterToggle');
  const featureToggles = document.getElementById('featureToggles');
  const recordingDot = document.getElementById('recordingDot');
  const transcriptDot = document.getElementById('transcriptDot');
  const recordingStatus = document.getElementById('recordingStatus');
  const transcriptStatus = document.getElementById('transcriptStatus');

  // Load saved settings
  const settings = await chrome.storage.sync.get({
    enabled: true,
    autoRecord: true,
    autoTranscript: true
  });

  // Apply settings to toggles
  enabledToggle.checked = settings.enabled;
  autoRecordToggle.checked = settings.autoRecord;
  autoTranscriptToggle.checked = settings.autoTranscript;

  // Update UI based on enabled state
  updateEnabledState(settings.enabled);

  // Load current meeting status
  const status = await chrome.storage.local.get({
    recordingStarted: false,
    transcriptStarted: false
  });

  updateStatusDisplay(status);

  // Event listeners for toggles
  enabledToggle.addEventListener('change', (e) => {
    const enabled = e.target.checked;
    chrome.storage.sync.set({ enabled });
    updateEnabledState(enabled);
  });

  autoRecordToggle.addEventListener('change', (e) => {
    chrome.storage.sync.set({ autoRecord: e.target.checked });
  });

  autoTranscriptToggle.addEventListener('change', (e) => {
    chrome.storage.sync.set({ autoTranscript: e.target.checked });
  });

  // Update enabled state UI
  function updateEnabledState(enabled) {
    if (enabled) {
      masterToggle.classList.remove('disabled');
      featureToggles.style.opacity = '1';
      featureToggles.style.pointerEvents = 'auto';
    } else {
      masterToggle.classList.add('disabled');
      featureToggles.style.opacity = '0.5';
      featureToggles.style.pointerEvents = 'none';
    }
  }

  // Update status display
  function updateStatusDisplay(status) {
    if (status.recordingStarted) {
      recordingDot.classList.remove('inactive');
      recordingDot.classList.add('active');
      recordingStatus.textContent = 'Recording: Active';
    } else {
      recordingDot.classList.remove('active');
      recordingDot.classList.add('inactive');
      recordingStatus.textContent = 'Recording: Inactive';
    }

    if (status.transcriptStarted) {
      transcriptDot.classList.remove('inactive');
      transcriptDot.classList.add('active');
      transcriptStatus.textContent = 'Transcript: Active';
    } else {
      transcriptDot.classList.remove('active');
      transcriptDot.classList.add('inactive');
      transcriptStatus.textContent = 'Transcript: Inactive';
    }
  }

  // Listen for storage changes to update status in real-time
  chrome.storage.onChanged.addListener((changes, namespace) => {
    if (namespace === 'local') {
      const newStatus = {};
      if (changes.recordingStarted) {
        newStatus.recordingStarted = changes.recordingStarted.newValue;
      }
      if (changes.transcriptStarted) {
        newStatus.transcriptStarted = changes.transcriptStarted.newValue;
      }
      if (Object.keys(newStatus).length > 0) {
        chrome.storage.local.get({
          recordingStarted: false,
          transcriptStarted: false
        }, updateStatusDisplay);
      }
    }
  });
});
