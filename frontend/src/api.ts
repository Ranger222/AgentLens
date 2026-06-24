// Minimal typed data layer: a ~25-line useFetch hook + a few endpoint helpers.
// No React Query/SWR/axios for a local, read-only, 3-endpoint app.

import { useCallback, useEffect, useState } from "react";
import type { RunDetail, RunListResponse } from "./types";

// Same-origin in production (FastAPI serves the SPA); Vite proxies /api in dev.
const BASE = "";

async function getJSON<T>(url: string): Promise<T> {
  const res = await fetch(BASE + url);
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  return (await res.json()) as T;
}

export interface FetchState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useFetch<T>(url: string | null): FetchState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(url !== null);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    if (url === null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    getJSON<T>(url)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [url, nonce]);

  return { data, loading, error, reload };
}

export function useRuns(limit = 100): FetchState<RunListResponse> {
  return useFetch<RunListResponse>(`/api/runs?limit=${limit}`);
}

export function useRun(runId: string | null): FetchState<RunDetail> {
  return useFetch<RunDetail>(runId ? `/api/runs/${runId}` : null);
}

export async function deleteRun(runId: string): Promise<void> {
  const res = await fetch(`${BASE}/api/runs/${runId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to delete run: ${res.status}`);
}
