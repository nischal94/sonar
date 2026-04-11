// extension/popup/popup.js
async function getApiBase() {
  const data = await chrome.storage.local.get('api_base');
  return data.api_base || 'http://localhost:8000';
}

async function init() {
  const { auth_token, signal_count, last_sync_time } = await chrome.storage.local.get([
    'auth_token', 'signal_count', 'last_sync_time'
  ]);

  if (auth_token) {
    showConnected(signal_count || 0, last_sync_time);
  } else {
    showDisconnected();
  }
}

function showConnected(count, lastSyncTime) {
  document.getElementById('auth-section').style.display = 'none';
  document.getElementById('stats-section').style.display = 'block';
  document.getElementById('signal-count').textContent = count;

  if (lastSyncTime) {
    const mins = Math.round((Date.now() - lastSyncTime) / 60000);
    document.getElementById('last-sync-text').textContent =
      `Last sync: ${mins < 1 ? 'just now' : `${mins}m ago`}`;
  }
}

function showDisconnected() {
  document.getElementById('auth-section').style.display = 'block';
  document.getElementById('stats-section').style.display = 'none';
}

document.getElementById('connect-btn')?.addEventListener('click', async () => {
  const email = document.getElementById('email-input').value;
  const password = document.getElementById('password-input').value;

  const apiBase = await getApiBase();
  const resp = await fetch(`${apiBase}/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
  });

  if (resp.ok) {
    const { access_token } = await resp.json();
    await chrome.storage.local.set({ auth_token: access_token });
    showConnected(0, null);
  } else {
    document.getElementById('status-text').textContent = 'Login failed. Check credentials.';
  }
});

document.getElementById('sync-now-btn')?.addEventListener('click', async () => {
  const tabs = await chrome.tabs.query({ url: 'https://www.linkedin.com/*' });
  if (tabs.length > 0) {
    chrome.tabs.sendMessage(tabs[0].id, { type: 'SONAR_SYNC' });
    window.close();
  } else {
    alert('Please open LinkedIn first.');
  }
});

init();
