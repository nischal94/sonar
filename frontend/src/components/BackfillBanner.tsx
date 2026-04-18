import { useCallback, useState } from "react";
import api from "../api/client";
import { usePolledEndpoint } from "../hooks/usePolledEndpoint";

interface BackfillStatus {
  state: "idle" | "running" | "done" | "failed";
  profile_count: number;
  backfill_started_at: string | null;
  backfill_completed_at: string | null;
}

export function BackfillBanner() {
  const [reachedTerminal, setReachedTerminal] = useState(false);

  const fetcher = useCallback(async (): Promise<BackfillStatus> => {
    const { data } = await api.get<BackfillStatus>("/workspace/backfill/status");
    if (data.state === "done" || data.state === "failed") {
      // Stop the poll loop once we've observed a terminal state. The banner
      // continues to render the last-known status from `data`.
      setReachedTerminal(true);
    }
    return data;
  }, []);

  const { data } = usePolledEndpoint(fetcher, {
    intervalMs: 5000,
    enabled: !reachedTerminal,
  });

  if (!data || data.state === "idle") {
    return null;
  }

  if (data.state === "running") {
    return (
      <div
        role="status"
        style={{
          padding: 12,
          background: "#eef6ff",
          border: "1px solid #b3d4ff",
          borderRadius: 8,
          marginBottom: 16,
          fontSize: 14,
        }}
      >
        Backfill in progress — your dashboard will populate as we process your network.
      </div>
    );
  }

  if (data.state === "done") {
    return (
      <div
        role="status"
        style={{
          padding: 12,
          background: "#e9f7e9",
          border: "1px solid #b6dfb6",
          borderRadius: 8,
          marginBottom: 16,
          fontSize: 14,
        }}
      >
        Backfill complete — you're seeing your full 60-day network snapshot ({data.profile_count} people).
      </div>
    );
  }

  // failed
  return (
    <div
      role="status"
      style={{
        padding: 12,
        background: "#fdecec",
        border: "1px solid #f5c2c2",
        borderRadius: 8,
        marginBottom: 16,
        fontSize: 14,
      }}
    >
      Backfill didn't complete cleanly — signals will accumulate from here. Contact support if this persists.
    </div>
  );
}

export default BackfillBanner;
