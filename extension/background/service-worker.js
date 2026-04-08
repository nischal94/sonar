// extension/background/service-worker.js

chrome.runtime.onInstalled.addListener(() => {
  scheduleNextAlarm();
});

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'sonar-sync') {
    triggerLinkedInSync();
    scheduleNextAlarm();
  }
});

function scheduleNextAlarm() {
  // 30 minutes ± 3 minutes jitter
  const jitterMinutes = (Math.random() * 6) - 3;
  const delayMinutes = 30 + jitterMinutes;
  chrome.alarms.create('sonar-sync', { delayInMinutes: delayMinutes });
}

async function triggerLinkedInSync() {
  const tabs = await chrome.tabs.query({ url: 'https://www.linkedin.com/*' });

  if (tabs.length > 0) {
    try {
      await chrome.tabs.sendMessage(tabs[0].id, { type: 'SONAR_SYNC' });
    } catch (e) {
      // Content script not ready — ignore
    }
  }
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === 'SET_AUTH_TOKEN') {
    chrome.storage.local.set({ auth_token: message.token });
    sendResponse({ success: true });
  }
});
