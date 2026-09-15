import { useEffect, useState } from "react";

/**
 * usePolling — call `fetchFn` once immediately, then again every `intervalMs`,
 * for as long as the component stays on screen. This is how pages watch the
 * agent's progress "live" without a refresh: the offer list just re-asks the
 * backend "what's the status now?" every few seconds.
 *
 * @param {() => Promise<any>} fetchFn - e.g. () => apiGet("/api/restaurant/offers")
 * @param {number} intervalMs - how often to re-fetch, e.g. 3000 for every 3 seconds
 * @param {any[]} deps - re-subscribe if any of these change (like useEffect's deps)
 * @returns {{ data: any, error: string | null }}
 */
export function usePolling(fetchFn, intervalMs, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false; // guards against setting state after the component unmounts

    async function load() {
      try {
        const result = await fetchFn();
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message);
        }
      }
    }

    load();
    const intervalId = setInterval(load, intervalMs);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps is the caller's explicit dependency list
  }, deps);

  return { data, error };
}
