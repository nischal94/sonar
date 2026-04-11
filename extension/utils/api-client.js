// extension/utils/api-client.js
// API base is read from storage (set via popup settings). Defaults to localhost for dev.
let _cachedApiBase = null;

async function _getApiBase() {
  if (_cachedApiBase) return _cachedApiBase;
  const data = await chrome.storage.local.get('api_base');
  _cachedApiBase = data.api_base || 'http://localhost:8000';
  return _cachedApiBase;
}

const SonarAPI = {
  async ingestPosts(posts) {
    const token = await SonarStorage.getAuthToken();
    if (!token) {
      console.warn('[Sonar] No auth token — skipping ingest');
      return null;
    }

    const apiBase = await _getApiBase();
    const response = await fetch(`${apiBase}/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        posts: posts,
        extraction_version: '1.0.0',
      }),
    });

    if (response.status === 401) {
      await SonarStorage.setAuthToken(null);
      return null;
    }

    if (!response.ok) {
      console.error('[Sonar] Ingest failed:', response.status);
      return null;
    }

    return await response.json();
  },

  async setAuthToken(token) {
    await SonarStorage.setAuthToken(token);
  }
};
