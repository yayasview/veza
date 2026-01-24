/**
 * Google Meet Auto Record & Transcript
 *
 * This content script automatically starts recording and transcription
 * when joining a Google Meet call.
 */

(function() {
  'use strict';

  // Configuration
  const CONFIG = {
    maxAttempts: 30,
    checkInterval: 2000,
    buttonClickDelay: 1000,
    meetingDetectionDelay: 5000
  };

  // State
  let hasStartedRecording = false;
  let hasStartedTranscript = false;
  let isInMeeting = false;
  let attemptCount = 0;

  /**
   * Log messages with prefix for easy identification
   */
  function log(message, type = 'info') {
    const prefix = '[Meet Auto Record]';
    const styles = {
      info: 'color: #4285f4',
      success: 'color: #34a853',
      warning: 'color: #fbbc04',
      error: 'color: #ea4335'
    };
    console.log(`%c${prefix} ${message}`, styles[type] || styles.info);
  }

  /**
   * Check if we're in an active meeting (not lobby/waiting room)
   */
  function isInActiveMeeting() {
    // Check for presence of meeting controls (camera, mic buttons)
    const meetingControls = document.querySelector('[data-is-muted]');

    // Check for video tiles or participant list
    const videoTiles = document.querySelector('[data-participant-id]');

    // Check for the "You" indicator in participants
    const selfVideo = document.querySelector('[data-self-name]');

    // Check if leave button is present (reliable indicator of being in meeting)
    const leaveButton = document.querySelector('[aria-label*="Leave call"]') ||
                        document.querySelector('[aria-label*="leave"]') ||
                        document.querySelector('[data-tooltip*="Leave call"]');

    return !!(meetingControls || videoTiles || selfVideo || leaveButton);
  }

  /**
   * Find the Activities button (three dots or activities panel)
   */
  function findActivitiesButton() {
    // Try different selectors for the Activities button
    const selectors = [
      '[aria-label="Activities"]',
      '[data-tooltip="Activities"]',
      'button[aria-label*="Activities"]',
      '[aria-label="More options"]',
      '[data-tooltip="More options"]'
    ];

    for (const selector of selectors) {
      const button = document.querySelector(selector);
      if (button) return button;
    }
    return null;
  }

  /**
   * Find the recording button in the activities panel or menu
   */
  function findRecordButton() {
    // Look for recording option in menus/panels
    const selectors = [
      '[aria-label*="Record"]',
      '[data-tooltip*="Record"]',
      'span:contains("Recording")',
      '[aria-label="Start recording"]',
      '[aria-label="Recording"]'
    ];

    // Search through all elements
    const allElements = document.querySelectorAll('*');
    for (const el of allElements) {
      const ariaLabel = el.getAttribute('aria-label') || '';
      const textContent = el.textContent || '';
      const tooltip = el.getAttribute('data-tooltip') || '';

      if (ariaLabel.toLowerCase().includes('start recording') ||
          ariaLabel.toLowerCase().includes('record meeting') ||
          tooltip.toLowerCase().includes('record')) {
        return el;
      }

      // Check for menu items with "Recording" text
      if (el.tagName === 'LI' || el.getAttribute('role') === 'menuitem') {
        if (textContent.toLowerCase().includes('recording')) {
          return el;
        }
      }
    }
    return null;
  }

  /**
   * Find the transcript/captions button
   */
  function findTranscriptButton() {
    const selectors = [
      '[aria-label*="caption"]',
      '[aria-label*="Caption"]',
      '[aria-label*="transcript"]',
      '[aria-label*="Transcript"]',
      '[data-tooltip*="caption"]',
      '[data-tooltip*="Caption"]',
      '[aria-label="Turn on captions"]',
      'button[aria-label*="captions"]'
    ];

    for (const selector of selectors) {
      const button = document.querySelector(selector);
      if (button) return button;
    }
    return null;
  }

  /**
   * Click a button with retry logic
   */
  function clickButton(button, description) {
    return new Promise((resolve) => {
      if (!button) {
        log(`${description} button not found`, 'warning');
        resolve(false);
        return;
      }

      try {
        // Try multiple click methods
        button.click();

        // Also dispatch events for stubborn buttons
        button.dispatchEvent(new MouseEvent('click', {
          bubbles: true,
          cancelable: true,
          view: window
        }));

        log(`Clicked: ${description}`, 'success');
        resolve(true);
      } catch (error) {
        log(`Failed to click ${description}: ${error.message}`, 'error');
        resolve(false);
      }
    });
  }

  /**
   * Open the Activities panel and look for recording option
   */
  async function openActivitiesAndRecord() {
    // First, try to find a direct record button
    let recordButton = findRecordButton();
    if (recordButton) {
      return await clickButton(recordButton, 'Record');
    }

    // Try opening Activities panel
    const activitiesButton = findActivitiesButton();
    if (activitiesButton) {
      await clickButton(activitiesButton, 'Activities');

      // Wait for menu to open
      await new Promise(resolve => setTimeout(resolve, CONFIG.buttonClickDelay));

      // Now look for recording option
      recordButton = findRecordButton();
      if (recordButton) {
        return await clickButton(recordButton, 'Start Recording');
      }
    }

    return false;
  }

  /**
   * Start recording
   */
  async function startRecording() {
    if (hasStartedRecording) return;

    log('Attempting to start recording...', 'info');

    const success = await openActivitiesAndRecord();
    if (success) {
      hasStartedRecording = true;
      log('Recording started successfully!', 'success');

      // Notify via storage for popup
      chrome.storage.local.set({ recordingStarted: true });
    }
  }

  /**
   * Start transcription/captions
   */
  async function startTranscript() {
    if (hasStartedTranscript) return;

    log('Attempting to start transcription...', 'info');

    const transcriptButton = findTranscriptButton();
    const success = await clickButton(transcriptButton, 'Turn on captions/transcript');

    if (success) {
      hasStartedTranscript = true;
      log('Transcription started successfully!', 'success');

      // Notify via storage for popup
      chrome.storage.local.set({ transcriptStarted: true });
    }
  }

  /**
   * Main function to check and start recording/transcription
   */
  async function checkAndStart() {
    // Check if extension is enabled
    const settings = await chrome.storage.sync.get({
      autoRecord: true,
      autoTranscript: true,
      enabled: true
    });

    if (!settings.enabled) {
      log('Extension is disabled', 'info');
      return;
    }

    // Check if we're in a meeting
    if (!isInActiveMeeting()) {
      if (attemptCount < CONFIG.maxAttempts) {
        attemptCount++;
        log(`Waiting for meeting to start... (attempt ${attemptCount}/${CONFIG.maxAttempts})`, 'info');
        setTimeout(checkAndStart, CONFIG.checkInterval);
      } else {
        log('Max attempts reached. Not in a meeting.', 'warning');
      }
      return;
    }

    if (!isInMeeting) {
      isInMeeting = true;
      log('Meeting detected! Starting automation...', 'success');

      // Small delay to ensure UI is fully loaded
      await new Promise(resolve => setTimeout(resolve, CONFIG.meetingDetectionDelay));
    }

    // Try to start recording if enabled
    if (settings.autoRecord && !hasStartedRecording) {
      await startRecording();
    }

    // Try to start transcript if enabled
    if (settings.autoTranscript && !hasStartedTranscript) {
      await startTranscript();
    }

    // Continue checking if we haven't succeeded yet
    const needsRetry = (settings.autoRecord && !hasStartedRecording) ||
                       (settings.autoTranscript && !hasStartedTranscript);

    if (needsRetry && attemptCount < CONFIG.maxAttempts) {
      attemptCount++;
      setTimeout(checkAndStart, CONFIG.checkInterval);
    }
  }

  /**
   * Initialize the extension
   */
  function init() {
    log('Extension loaded. Monitoring for Google Meet...', 'info');

    // Reset state for this meeting
    hasStartedRecording = false;
    hasStartedTranscript = false;
    isInMeeting = false;
    attemptCount = 0;

    // Clear previous meeting state
    chrome.storage.local.set({
      recordingStarted: false,
      transcriptStarted: false
    });

    // Start checking
    checkAndStart();

    // Also set up a MutationObserver to detect dynamic changes
    const observer = new MutationObserver((mutations) => {
      // If we're not in a meeting yet, check again
      if (!isInMeeting && isInActiveMeeting()) {
        checkAndStart();
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Also reinitialize when URL changes (for joining new meetings)
  let lastUrl = location.href;
  new MutationObserver(() => {
    const currentUrl = location.href;
    if (currentUrl !== lastUrl) {
      lastUrl = currentUrl;
      log('URL changed, reinitializing...', 'info');
      init();
    }
  }).observe(document, { subtree: true, childList: true });

})();
