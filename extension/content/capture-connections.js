// Day-One Backfill: scrape the user's 1st-degree connection list.
// Triggered by a message from the extension popup. Scrolls the virtualized
// list, extracts each connection's profile_url / name / headline, POSTs in
// chunks of 100 to /extension/connections/bulk, then calls
// /workspace/backfill/trigger.
//
// Part of the Phase 2 Backfill slice. Runs only on the connections page.

(function initCaptureConnections() {
  if (!window.location.pathname.includes("/mynetwork/invite-connect/connections")) {
    return;
  }

  function extractConnectionsFromDOM() {
    // LinkedIn's connections page uses mn-connection-card containers.
    // Selectors here are brittle by definition — when LinkedIn changes DOM,
    // this script's telemetry will flag the mismatch.
    const rows = document.querySelectorAll(".mn-connection-card, [data-chameleon-result-urn]");
    const out = [];
    for (const row of rows) {
      const link = row.querySelector('a[href*="/in/"]');
      if (!link) continue;
      let profile_url;
      try {
        const u = new URL(link.href);
        profile_url = u.origin + u.pathname.replace(/\/$/, "");
      } catch {
        continue;
      }
      const linkedin_id = profile_url.split("/in/")[1];
      if (!linkedin_id) continue;
      const nameEl = row.querySelector(".mn-connection-card__name, [data-test-app-aware-link] span");
      const name = nameEl?.textContent?.trim() || "";
      if (!name) continue;
      const headlineEl = row.querySelector(".mn-connection-card__occupation");
      const headline = headlineEl?.textContent?.trim() || null;
      out.push({
        linkedin_id,
        name,
        headline,
        company: null,
        profile_url,
      });
    }
    return out;
  }

  async function scrollAndCollect(maxScrolls = 30) {
    const seen = new Set();
    const all = [];
    for (let i = 0; i < maxScrolls; i++) {
      const batch = extractConnectionsFromDOM();
      for (const c of batch) {
        if (!seen.has(c.linkedin_id)) {
          seen.add(c.linkedin_id);
          all.push(c);
        }
      }
      window.scrollTo(0, document.body.scrollHeight);
      await new Promise((r) => setTimeout(r, 1500));
    }
    return all;
  }

  async function getAuthToken() {
    return new Promise((resolve) => {
      chrome.storage.local.get(["auth_token"], (r) => resolve(r.auth_token || ""));
    });
  }

  async function postBulk(connections, backendBaseUrl) {
    const CHUNK = 100;
    const token = await getAuthToken();
    for (let i = 0; i < connections.length; i += CHUNK) {
      const chunk = connections.slice(i, i + CHUNK);
      const res = await fetch(`${backendBaseUrl}/extension/connections/bulk`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ connections: chunk }),
      });
      if (!res.ok) throw new Error(`bulk post failed: ${res.status}`);
    }
  }

  async function triggerBackfill(backendBaseUrl) {
    const token = await getAuthToken();
    const res = await fetch(`${backendBaseUrl}/workspace/backfill/trigger`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok && res.status !== 409) {
      throw new Error(`trigger failed: ${res.status}`);
    }
  }

  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.type !== "run_day_one_scan") return;
    const backendBaseUrl = msg.backendBaseUrl || "http://localhost:8000";
    (async () => {
      try {
        const connections = await scrollAndCollect();
        if (connections.length === 0) {
          sendResponse({ ok: false, error: "no_connections_found" });
          return;
        }
        await postBulk(connections, backendBaseUrl);
        await triggerBackfill(backendBaseUrl);
        sendResponse({ ok: true, count: connections.length });
      } catch (e) {
        sendResponse({ ok: false, error: String(e) });
      }
    })();
    return true; // keep channel open for async response
  });
})();
