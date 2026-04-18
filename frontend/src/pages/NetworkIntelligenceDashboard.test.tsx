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

  it("changing the threshold updates the displayed value", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: { people: [], threshold_used: 0.65, total: 0 },
    });

    render(<NetworkIntelligenceDashboard />);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));

    // The initial threshold is 0.65
    expect(screen.getByText("0.65")).toBeInTheDocument();

    const slider = screen.getByRole("slider");
    fireEvent.change(slider, { target: { value: "0.8" } });

    // After the change handler runs, the displayed threshold updates to 0.80.
    // Note: usePolledEndpoint doesn't refetch on fetcher-identity change
    // (it only reacts to interval + visibility), so the refetch will happen
    // on the next poll tick — we assert on the observable state change instead.
    await waitFor(() => expect(screen.getByText("0.80")).toBeInTheDocument());
  });
});
