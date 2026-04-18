import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import BackfillBanner from "./BackfillBanner";

vi.mock("../api/client", () => ({
  default: { get: vi.fn() },
}));

describe("BackfillBanner", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders nothing when state is idle", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: { state: "idle", profile_count: 0, backfill_started_at: null, backfill_completed_at: null },
    });

    const { container } = render(<BackfillBanner />);
    await waitFor(() => expect(api.get).toHaveBeenCalled());
    expect(container.textContent).toBe("");
  });

  it("renders running banner when state is running", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: {
        state: "running",
        profile_count: 0,
        backfill_started_at: new Date().toISOString(),
        backfill_completed_at: null,
      },
    });
    render(<BackfillBanner />);
    await waitFor(() =>
      expect(screen.getByText(/backfill in progress/i)).toBeInTheDocument()
    );
  });

  it("renders done banner when state is done", async () => {
    const api = (await import("../api/client")).default as unknown as {
      get: ReturnType<typeof vi.fn>;
    };
    api.get.mockResolvedValue({
      data: {
        state: "done",
        profile_count: 127,
        backfill_started_at: new Date().toISOString(),
        backfill_completed_at: new Date().toISOString(),
      },
    });
    render(<BackfillBanner />);
    await waitFor(() =>
      expect(screen.getByText(/backfill complete/i)).toBeInTheDocument()
    );
  });
});
