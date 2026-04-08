// extension/content/linkedin-scraper.js

const MIN_SYNC_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

async function shouldSync() {
  const lastSync = await SonarStorage.getLastSyncTime();
  return (Date.now() - lastSync) >= MIN_SYNC_INTERVAL_MS;
}

async function scrollFeedAndCollect() {
  const highWaterMark = await SonarStorage.getHighWaterMark();
  const seenIds = await SonarStorage.getSeenPostIds();
  const newPosts = [];
  let hitWaterMark = false;
  let scrollAttempts = 0;
  const MAX_SCROLLS = 15;

  while (scrollAttempts < MAX_SCROLLS && !hitWaterMark) {
    const visible = extractVisiblePosts();

    for (const post of visible) {
      if (seenIds.has(post.linkedin_post_id)) continue;
      if (post.linkedin_post_id === highWaterMark) {
        hitWaterMark = true;
        break;
      }
      newPosts.push(post);
    }

    if (hitWaterMark || visible.length === 0) break;

    window.scrollBy(0, 600 + Math.random() * 400);
    const delay = 800 + Math.random() * 600;
    await new Promise(r => setTimeout(r, delay));

    if (scrollAttempts % 3 === 2) {
      await new Promise(r => setTimeout(r, 1200 + Math.random() * 2600));
    }

    scrollAttempts++;
  }

  return newPosts;
}

async function runSync() {
  const token = await SonarStorage.getAuthToken();
  if (!token) return;

  if (!(await shouldSync())) return;

  console.log('[Sonar] Starting feed sync...');

  try {
    const posts = await scrollFeedAndCollect();

    if (posts.length === 0) {
      console.log('[Sonar] No new posts found.');
      return;
    }

    const seenIds = await SonarStorage.getSeenPostIds();
    const freshPosts = posts.filter(p => !seenIds.has(p.linkedin_post_id));

    if (freshPosts.length === 0) return;

    for (let i = 0; i < freshPosts.length; i += 50) {
      const batch = freshPosts.slice(i, i + 50);
      await SonarAPI.ingestPosts(batch);
    }

    const newIds = freshPosts.map(p => p.linkedin_post_id);
    await SonarStorage.addSeenPostIds(newIds);
    if (freshPosts[0]) {
      await SonarStorage.setHighWaterMark(freshPosts[0].linkedin_post_id);
    }
    await SonarStorage.setLastSyncTime(Date.now());

    console.log(`[Sonar] Synced ${freshPosts.length} new posts.`);
  } catch (e) {
    console.error('[Sonar] Sync error:', e.message);
  }
}

runSync();

let lastUrl = location.href;
new MutationObserver(() => {
  if (location.href !== lastUrl) {
    lastUrl = location.href;
    if (location.pathname === '/feed/') {
      setTimeout(runSync, 2000);
    }
  }
}).observe(document.body, { subtree: true, childList: true });

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'SONAR_SYNC') {
    runSync();
  }
});
