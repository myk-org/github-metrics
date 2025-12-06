import type { TimeRangeResponse, Pagination } from "./api";

export interface Repository {
  readonly repository: string;
  readonly total_events: number;
  readonly percentage: number | null;
  readonly [key: string]: unknown;
}

export interface RepositoriesResponse {
  readonly time_range: TimeRangeResponse;
  readonly repositories: readonly Repository[];
  readonly pagination: Pagination;
}
