// extension/utils/storage.js
const SonarStorage = {
  async getAuthToken() {
    const data = await chrome.storage.local.get(['auth_token']);
    return data.auth_token || null;
  },

  async setAuthToken(token) {
    await chrome.storage.local.set({ auth_token: token });
  },

  async getHighWaterMark() {
    const data = await chrome.storage.local.get(['high_water_mark']);
    return data.high_water_mark || null;
  },

  async setHighWaterMark(postId) {
    await chrome.storage.local.set({ high_water_mark: postId });
  },

  async getLastSyncTime() {
    const data = await chrome.storage.local.get(['last_sync_time']);
    return data.last_sync_time || 0;
  },

  async setLastSyncTime(timestamp) {
    await chrome.storage.local.set({ last_sync_time: timestamp });
  },

  async getSeenPostIds() {
    const data = await chrome.storage.local.get(['seen_post_ids']);
    return new Set(data.seen_post_ids || []);
  },

  async addSeenPostIds(ids) {
    const existing = await this.getSeenPostIds();
    const merged = [...existing, ...ids];
    // Keep last 2000 IDs to prevent unbounded growth
    const trimmed = merged.slice(-2000);
    await chrome.storage.local.set({ seen_post_ids: trimmed });
  },

  async getSignalCount() {
    const data = await chrome.storage.local.get(['signal_count']);
    return data.signal_count || 0;
  },

  async incrementSignalCount(n) {
    const current = await this.getSignalCount();
    await chrome.storage.local.set({ signal_count: current + n });
  }
};
