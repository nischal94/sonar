import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { usePolledEndpoint } from "./usePolledEndpoint";

describe("usePolledEndpoint", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("calls fetcher once on mount and exposes loading + data", async () => {
    const fetcher = vi.fn().mockResolvedValue({ hello: "world" });
    const { result } = renderHook(() =>
      usePolledEndpoint(fetcher, { intervalMs: 30000 })
    );
    expect(result.current.isLoading).toBe(true);
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.data).toEqual({ hello: "world" });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("re-polls every interval", async () => {
    const fetcher = vi.fn().mockResolvedValue({ count: 1 });
    renderHook(() => usePolledEndpoint(fetcher, { intervalMs: 30000 }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));

    act(() => {
      vi.advanceTimersByTime(30000);
    });
    await waitFor(() => expect(fetcher).toHaveBeenCalledTimes(2));
  });
});
