import type { AppConfig, SearchResponse, StructuredQuery, SummariesResponse } from "./types";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function call<T>(path: string, body?: unknown, timeoutMs = 45000): Promise<T> {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!res.ok) {
      let detail = `Request failed (HTTP ${res.status}).`;
      try {
        const data = await res.json();
        if (typeof data?.detail === "string") detail = data.detail;
      } catch {
        /* non-JSON error body */
      }
      if (res.status >= 500 && res.status !== 503) detail = "The ScoutIQ API is unreachable. Is the backend running on port 8000?";
      throw new ApiError(detail, res.status);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === "AbortError") throw new ApiError("The request timed out. Please try again.");
    throw new ApiError("Could not reach the ScoutIQ API. Is the backend running?");
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  config: () => call<AppConfig>("/config"),
  search: (text: string) => call<SearchResponse>("/search", { text }),
  rank: (query: StructuredQuery) => call<SearchResponse>("/rank", { query }),
  refine: (query: StructuredQuery, text: string) => call<SearchResponse>("/refine", { query, text }),
  summaries: (query: StructuredQuery, player_ids: number[]) =>
    call<SummariesResponse>("/summaries", { query, player_ids }),
};
