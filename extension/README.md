# Sonar Chrome Extension

Chrome MV3 extension that captures LinkedIn feed posts and syncs them to the Sonar backend.

---

## How It Works

The extension runs entirely inside the user's own authenticated LinkedIn session — no LinkedIn API keys required. It captures posts from the feed using DOM extraction, deduplicates them using a high-water mark, and batches them to the Sonar ingest endpoint.

```
LinkedIn feed loaded
        ↓
MutationObserver detects new posts (SPA navigation)
        ↓
extractVisiblePosts() — DOM → structured post objects
        ↓
Deduplication: skip post IDs seen in the last 2000 posts
        ↓
POST /ingest with Bearer token
        ↓
Background alarm fires every 30 ± 3 min (jitter prevents thundering herd)
```

---

## Installation (Development)

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repo
5. The Sonar icon appears in your toolbar

---

## First Use

1. Click the Sonar icon in your toolbar
2. Enter your Sonar account email and password
3. Click **Sign In** — the extension stores your JWT token in `chrome.storage.local`
4. Open `https://linkedin.com` and scroll your feed
5. The extension begins syncing automatically

The popup shows:
- **Signal count** — total alerts generated so far
- **Last sync time**
- **Sync now** button — triggers an immediate sync

---

## Sync Schedule

Syncs run on a Chrome Alarm that fires every **30 minutes ± 3 minutes** (random jitter). The jitter prevents all users from syncing simultaneously when they first install, which would spike the backend.

Manual sync: click **Sync now** in the popup, or send `SONAR_SYNC` to the content script from the popup.

---

## High-Water Mark

To avoid re-processing posts you've already seen, the extension maintains:

- **`last_sync_ts`** — timestamp of the most recent successful sync
- **`seen_post_ids`** — set of the last 2000 LinkedIn post IDs (ring buffer)

Posts older than `last_sync_ts` or already in `seen_post_ids` are skipped before being sent to the backend. This means duplicate filtering happens in two places: the extension (before network) and the backend (database deduplication via unique constraint on `workspace_id + linkedin_post_id`).

---

## Storage Schema

All data is stored in `chrome.storage.local`:

| Key | Type | Description |
|---|---|---|
| `sonar_token` | `string` | JWT access token |
| `last_sync_ts` | `number` | Unix timestamp of last sync |
| `seen_post_ids` | `string[]` | Ring buffer of last 2000 post IDs |
| `signal_count` | `number` | Total alerts received (for popup display) |

---

## File Structure

```
extension/
├── manifest.json              # MV3 manifest
├── background/
│   └── service-worker.js      # Chrome Alarms + sync trigger
├── content/
│   └── linkedin-scraper.js    # DOM extraction + MutationObserver
├── popup/
│   ├── popup.html             # Login form + stats view
│   └── popup.js               # Popup logic
└── utils/
    ├── storage.js             # SonarStorage — chrome.storage.local wrapper
    ├── extractor.js           # DOM selectors + extractPost()
    └── api-client.js          # SonarAPI.ingestPosts() with Bearer auth
```

---

## Permissions

| Permission | Reason |
|---|---|
| `activeTab` | Read the current LinkedIn tab's DOM |
| `storage` | Persist auth token + sync state |
| `alarms` | Schedule periodic background syncs |
| `host_permissions: *://*.linkedin.com/*` | Run content script on LinkedIn pages |

---

## Troubleshooting

**Extension shows "Not authenticated"**
→ Sign in via the popup. If login fails, verify the Sonar backend is running at `http://localhost:8000`.

**No posts syncing**
→ Open LinkedIn in a tab and scroll your feed. The extension only captures posts visible in the DOM. Posts loaded before the extension was installed won't be captured.

**Sync not triggering automatically**
→ Chrome may suspend service workers in low-memory conditions. Use the "Sync now" button in the popup to trigger manually.

**CORS errors in the console**
→ Verify `VITE_API_BASE` / the backend URL in `utils/api-client.js` matches where your Sonar API is running.
