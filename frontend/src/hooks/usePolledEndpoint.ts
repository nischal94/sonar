import { useEffect, useRef, useState } from "react";

interface Options {
  intervalMs: number;
  enabled?: boolean;
}

interface State<T> {
  data: T | null;
  error: Error | null;
  isLoading: boolean;
  isStale: boolean;
}

export function usePolledEndpoint<T>(
  fetcher: () => Promise<T>,
  { intervalMs, enabled = true }: Options
): State<T> & { refetch: () => Promise<void> } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStale, setIsStale] = useState(false);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const doFetch = async () => {
    if (data !== null) setIsStale(true);
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setIsLoading(false);
      setIsStale(false);
    }
  };

  useEffect(() => {
    if (!enabled) return;
    doFetch();

    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        doFetch();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);

    const intervalId = setInterval(() => {
      if (document.visibilityState === "visible") {
        doFetch();
      }
    }, intervalMs);

    return () => {
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs]);

  return { data, error, isLoading, isStale, refetch: doFetch };
}
