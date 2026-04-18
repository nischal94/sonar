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

  it("renders loading then empty state when the list is empty", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: { people: [], threshold_used: 0.65, total: 0 },
    });

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() =>
      expect(screen.getByText(/no signals in your network/i)).toBeInTheDocument()
    );
  });

  it("renders the list of people when the endpoint returns rows", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: {
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
      },
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
    api.get.mockResolvedValue({
      data: { people: [], threshold_used: 0.65, total: 0 },
    });

    render(<NetworkIntelligenceDashboard />);
    // Initial mount: the hook's mount fetch + the filter-change effect's mount
    // run = 2 calls. (The extra mount call is accepted cost of instant filter
    // responsiveness — see NetworkIntelligenceDashboard.tsx.)
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2));

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
