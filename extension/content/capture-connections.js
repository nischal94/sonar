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
    // LinkedIn's connections page keeps rebuilding its class names (tested
    // 2026-04-20: old .mn-connection-card and [data-chameleon-result-urn]
    // both gone). Instead of chasing class changes, anchor on the stable
    // fact that every connection has an /in/<slug> profile link, then
    // dedupe and walk up for headline text.
    const links = document.querySelectorAll('a[href*="/in/"]');
    const byId = new Map();
    for (const link of links) {
      let profile_url;
      try {
        const u = new URL(link.href);
        profile_url = u.origin + u.pathname.replace(/\/$/, "");
      } catch {
        continue;
      }
      const linkedin_id = profile_url.split("/in/")[1];
      if (!linkedin_id || linkedin_id.includes("/")) continue;
      const text = (link.textContent || "").trim().replace(/\s+/g, " ");
      const existing = byId.get(linkedin_id);
      // Per connection LinkedIn renders 2-3 overlapping links (photo wrapper
      // with empty text + name link with the name). Skip the empty-text
      // one if we already captured the name, but don't drop the entry.
      if (existing && existing.name && !text) continue;
      const name = text || (existing && existing.name) || "";
      if (!name || name.length < 2) continue;

      // Walk up to 5 ancestors, collecting the first plausible headline
      // from adjacent <span>/<p> text. Skip UI labels and connection-date
      // footers.
      let headline = null;
      let ancestor = link.parentElement;
      const skip = /^(Message|Follow|Remove Connection|More|Connected on|Pending)/;
      for (let i = 0; i < 5 && ancestor && !headline; i++) {
        const candidates = ancestor.querySelectorAll("span, p");
        for (const c of candidates) {
          const t = (c.textContent || "").trim().replace(/\s+/g, " ");
          if (
            t &&
            t !== name &&
            t.length >= 5 &&
            t.length <= 200 &&
            !skip.test(t)
          ) {
            headline = t;
            break;
          }
        }
        ancestor = ancestor.parentElement;
      }

      // Clamp to backend Pydantic limits (backend/app/schemas/backfill.py):
      // name max 200, headline max 500, profile_url max 500. LinkedIn's
      // textContent concatenates the name <span> with the headline <span>
      // into one string (e.g. "Debayan RoyProduct Marketing | Welingkar
      // | PGDM'24 | IOCL"), and some users' combined text exceeds 200.
      // Truncate rather than drop the row — linkedin_id + profile_url
      // remain clean and are what the backend dedupes/joins on.
      const clampedName = name.slice(0, 200);
      const clampedHeadline = headline ? headline.slice(0, 500) : null;
      const clampedUrl = profile_url.slice(0, 500);

      byId.set(linkedin_id, {
        linkedin_id: linkedin_id.slice(0, 200),
        name: clampedName,
        headline: clampedHeadline,
        company: null,
        profile_url: clampedUrl,
      });
    }
    return Array.from(byId.values());
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
