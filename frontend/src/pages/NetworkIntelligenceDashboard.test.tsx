import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import NetworkIntelligenceDashboard from "./NetworkIntelligenceDashboard";

vi.mock("../api/client", () => ({
  default: {
    get: vi.fn(),
  },
}));

describe("NetworkIntelligenceDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // BackfillBanner renders inside the dashboard and polls /workspace/backfill/status.
  // Route that URL to an idle response so the banner stays hidden during dashboard tests.
  const mockApiGet = (
    api: { get: ReturnType<typeof vi.fn> },
    dashboardData: unknown
  ) => {
    api.get.mockImplementation((url: string) => {
      if (url.startsWith("/workspace/backfill/status")) {
        return Promise.resolve({
          data: {
            state: "idle",
            profile_count: 0,
            backfill_started_at: null,
            backfill_completed_at: null,
          },
        });
      }
      return Promise.resolve({ data: dashboardData });
    });
  };

  const dashboardCallCount = (api: { get: ReturnType<typeof vi.fn> }) =>
    api.get.mock.calls.filter(
      (c) => !(c[0] as string).startsWith("/workspace/backfill/status")
    ).length;

  it("renders loading then empty state when the list is empty", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    mockApiGet(api, { people: [], threshold_used: 0.65, total: 0 });

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/no signals in your network/i)).toBeInTheDocument()
    );
  });

  it("renders the list of people when the endpoint returns rows", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    mockApiGet(api, {
      people: [
        {
          connection_id: "abc",
          name: "Jane Doe",
          title: "VP Engineering",
          company: "Acme",
          relationship_degree: 1,
          mutual_count: null,
          aggregate_score: 0.82,
          trend_direction: "up",
          last_signal_at: new Date().toISOString(),
          recent_post_snippet: "We've been interviewing for 4 months…",
          matching_signal_phrase: "struggling to hire",
          recent_post_url: null,
        },
      ],
      threshold_used: 0.65,
      total: 1,
    });

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() => expect(screen.getByText("Jane Doe")).toBeInTheDocument());
    expect(screen.getByText(/VP Engineering/)).toBeInTheDocument();
    expect(screen.getByText(/82%/)).toBeInTheDocument();
    expect(screen.getByText(/struggling to hire/i)).toBeInTheDocument();
  });

  it("changing the threshold triggers an immediate refetch with the new value", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    mockApiGet(api, { people: [], threshold_used: 0.65, total: 0 });

    render(<NetworkIntelligenceDashboard />);
    // Initial mount: the hook's mount fetch + the filter-change effect's mount
    // run = 2 dashboard calls. (The extra mount call is accepted cost of instant
    // filter responsiveness — see NetworkIntelligenceDashboard.tsx.) BackfillBanner
    // also polls /workspace/backfill/status but we filter those out.
    await waitFor(() => expect(dashboardCallCount(api)).toBe(2));

    expect(screen.getByText("0.65")).toBeInTheDocument();

    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "0.8" } });

    // The displayed threshold updates + an immediate refetch fires with the
    // new value (the filter-change effect now covers this — see hook comment).
    await waitFor(() => expect(screen.getByText("0.80")).toBeInTheDocument());
    await waitFor(() => {
      const urls = api.get.mock.calls.map((c) => c[0] as string);
      expect(urls.some((u) => u.includes("threshold=0.8"))).toBe(true);
    });
  });
});
