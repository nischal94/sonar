// extension/utils/api-client.js
const SONAR_API_BASE = 'https://api.yoursonar.com'; // Change to http://localhost:8000 for dev

const SonarAPI = {
  async ingestPosts(posts) {
    const token = await SonarStorage.getAuthToken();
    if (!token) {
      console.warn('[Sonar] No auth token — skipping ingest');
      return null;
    }

    const response = await fetch(`${SONAR_API_BASE}/ingest`, {
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
