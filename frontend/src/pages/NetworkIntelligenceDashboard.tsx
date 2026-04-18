import { useCallback, useState } from "react";
import api from "../api/client";
import { usePolledEndpoint } from "../hooks/usePolledEndpoint";

interface DashboardPerson {
  connection_id: string;
  name: string;
  title: string | null;
  company: string | null;
  relationship_degree: 1 | 2;
  mutual_count: number | null;
  aggregate_score: number;
  trend_direction: "up" | "flat" | "down";
  last_signal_at: string;
  recent_post_snippet: string | null;
  matching_signal_phrase: string | null;
  recent_post_url: string | null;
}

interface DashboardResponse {
  people: DashboardPerson[];
  threshold_used: number;
  total: number;
}

const TREND_ICON: Record<DashboardPerson["trend_direction"], string> = {
  up: "↑",
  flat: "→",
  down: "↓",
};

export function NetworkIntelligenceDashboard() {
  const [threshold, setThreshold] = useState<number>(0.65);
  const [tiers, setTiers] = useState<Set<1 | 2>>(new Set([1, 2]));

  const fetcher = useCallback(async (): Promise<DashboardResponse> => {
    const relationship = [...tiers].sort().join(",");
    const { data } = await api.get<DashboardResponse>(
      `/workspace/dashboard/people?threshold=${threshold}&relationship=${relationship}`
    );
    return data;
  }, [threshold, tiers]);

  const { data, error, isLoading, isStale } = usePolledEndpoint(fetcher, {
    intervalMs: 30000,
  });

  const toggleTier = (t: 1 | 2) => {
    const next = new Set(tiers);
    if (next.has(t)) {
      next.delete(t);
    } else {
      next.add(t);
    }
    if (next.size === 0) return; // always keep at least one tier selected
    setTiers(next);
  };

  const people = data?.people ?? [];

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "24px 16px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, margin: 0 }}>Network Intelligence</h1>
        {isStale && <span style={{ fontSize: 12, color: "#888" }}>Updating…</span>}
      </header>

      <section style={{ marginBottom: 24, padding: 16, border: "1px solid #eee", borderRadius: 8 }}>
        <label style={{ display: "block", marginBottom: 8 }}>
          Threshold: <strong>{threshold.toFixed(2)}</strong>
          <input
            type="range"
            min={0.5}
            max={0.95}
            step={0.05}
            value={threshold}
            onChange={(e) => setThreshold(parseFloat(e.target.value))}
            style={{ width: "100%", marginTop: 4 }}
          />
        </label>
        <div style={{ display: "flex", gap: 16, marginTop: 8 }}>
          <label>
            <input
              type="checkbox"
              checked={tiers.has(1)}
              onChange={() => toggleTier(1)}
            />{" "}
            1st-degree
          </label>
          <label>
            <input
              type="checkbox"
              checked={tiers.has(2)}
              onChange={() => toggleTier(2)}
            />{" "}
            2nd-degree
          </label>
        </div>
      </section>

      {error && (
        <div style={{ color: "#b00", padding: 12, background: "#fee", borderRadius: 8, marginBottom: 16 }}>
          Failed to load dashboard: {error.message}
        </div>
      )}

      {isLoading && people.length === 0 && (
        <div style={{ color: "#888", padding: 24, textAlign: "center" }}>Loading…</div>
      )}

      {!isLoading && people.length === 0 && (
        <div style={{ color: "#666", padding: 24, textAlign: "center", border: "1px dashed #ddd", borderRadius: 8 }}>
          No signals in your network above this threshold yet. Try lowering the threshold, or wait for more posts to flow through.
        </div>
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {people.map((p) => (
          <li
            key={p.connection_id}
            style={{ border: "1px solid #eee", borderRadius: 8, padding: 16, marginBottom: 12 }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <span style={{
                  display: "inline-block", padding: "2px 8px", borderRadius: 12,
                  background: p.relationship_degree === 1 ? "#d4f7d4" : "#fff3d4",
                  fontSize: 12, marginRight: 8,
                }}>
                  {p.relationship_degree === 1 ? "🟢 1st" : `🟡 2nd${p.mutual_count ? ` · ${p.mutual_count} mutual` : ""}`}
                </span>
                <strong>{p.name}</strong>
                {p.title && <span style={{ color: "#666" }}> · {p.title}</span>}
                {p.company && <span style={{ color: "#666" }}> at {p.company}</span>}
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 18, fontWeight: 600 }}>
                  {(p.aggregate_score * 100).toFixed(0)}% {TREND_ICON[p.trend_direction]}
                </div>
              </div>
            </div>
            {p.recent_post_snippet && (
              <div style={{ marginTop: 8, color: "#444", fontSize: 14 }}>"{p.recent_post_snippet}"</div>
            )}
            {p.matching_signal_phrase && (
              <div style={{ marginTop: 4, fontSize: 12, color: "#888", fontStyle: "italic" }}>
                Matched: {p.matching_signal_phrase}
              </div>
            )}
            <div style={{ marginTop: 8, display: "flex", gap: 8 }}>
              {p.recent_post_url && (
                <a
                  href={p.recent_post_url}
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: 12, padding: "4px 8px", border: "1px solid #ddd", borderRadius: 4, textDecoration: "none", color: "#333" }}
                >
                  View thread
                </a>
              )}
              <button
                style={{ fontSize: 12, padding: "4px 8px", border: "1px solid #ddd", borderRadius: 4, background: "#fff", cursor: "pointer" }}
                onClick={() => alert("Outreach drafting — coming soon")}
              >
                Draft outreach
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default NetworkIntelligenceDashboard;
