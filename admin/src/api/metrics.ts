import { apiFetch } from "./client";
import type { MetricsSummary } from "./types";

export function getMetricsSummary(signal?: AbortSignal): Promise<MetricsSummary> {
  return apiFetch<MetricsSummary>("/v1/metrics/summary", { signal });
}
