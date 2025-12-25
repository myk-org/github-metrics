export interface CommentResolutionSummary {
  readonly avg_resolution_time_hours: number;
  readonly median_resolution_time_hours: number;
  readonly avg_time_to_first_response_hours: number;
  readonly avg_comments_per_thread: number;
  readonly total_threads_analyzed: number;
  readonly resolution_rate: number;
}

export interface RepositoryCommentMetrics {
  readonly repository: string;
  readonly avg_resolution_time_hours: number;
  readonly total_threads: number;
  readonly resolved_threads: number;
}

export interface CommentThread {
  readonly thread_node_id: string;
  readonly repository: string;
  readonly pr_number: number;
  readonly first_comment_at: string | null;
  readonly resolved_at: string | null;
  readonly resolution_time_hours: number | null;
  readonly time_to_first_response_hours: number | null;
  readonly comment_count: number;
  readonly resolver: string | null;
  readonly participants: readonly string[];
  readonly file_path: string | null;
  readonly can_be_merged_at: string | null;
  readonly time_from_can_be_merged_hours: number | null;
  readonly [key: string]: unknown;
}

export interface Pagination {
  readonly total: number;
  readonly page: number;
  readonly page_size: number;
  readonly total_pages: number;
  readonly has_next: boolean;
  readonly has_prev: boolean;
}

export interface CommentResolutionResponse {
  readonly summary: CommentResolutionSummary;
  readonly by_repository: readonly RepositoryCommentMetrics[];
  readonly threads: readonly CommentThread[];
  readonly pagination: Pagination;
}
