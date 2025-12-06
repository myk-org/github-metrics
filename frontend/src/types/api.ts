export interface Pagination {
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
  readonly total_pages: number;
  readonly has_next: boolean;
  readonly has_prev: boolean;
}

export interface PaginatedResponse<T> {
  readonly data: readonly T[];
  readonly pagination: Pagination;
}

export interface TimeRange {
  readonly start_time?: string;
  readonly end_time?: string;
  readonly [key: string]: string | undefined;
}

export interface TimeRangeResponse {
  readonly start_time: string;
  readonly end_time: string;
}

export interface ApiError {
  readonly detail: string;
  readonly status_code: number;
}
