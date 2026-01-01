export interface SummaryData {
  readonly total_events: number;
  readonly successful_events: number;
  readonly failed_events: number;
  readonly success_rate: number;
  readonly avg_processing_time_ms: number;
  readonly median_processing_time_ms: number;
  readonly p95_processing_time_ms: number;
  readonly max_processing_time_ms: number;
  readonly total_api_calls: number;
  readonly avg_api_calls_per_event: number;
  readonly total_token_spend: number;
  readonly total_events_trend: number;
  readonly success_rate_trend: number;
  readonly failed_events_trend: number;
  readonly avg_duration_trend: number;
}

export interface TopRepository {
  readonly repository: string;
  readonly total_events: number;
  readonly percentage: number;
  readonly success_rate: number;
}

export interface MetricsSummary {
  readonly time_range: {
    readonly start_time: string | null;
    readonly end_time: string | null;
  };
  readonly summary: SummaryData;
  readonly top_repositories: readonly TopRepository[];
  readonly event_type_distribution: Record<string, number>;
  readonly hourly_event_rate: number;
  readonly daily_event_rate: number;
}

export interface TrendDataPoint {
  readonly timestamp: string;
  readonly count: number;
}

export interface TurnaroundByRepository extends Record<string, unknown> {
  readonly repository: string;
  readonly avg_time_to_first_review_hours: number;
  readonly avg_time_to_first_changes_requested_hours: number;
  readonly avg_time_to_approval_hours: number;
  readonly avg_time_to_first_verified_hours: number;
  readonly avg_pr_lifecycle_hours: number;
  readonly total_prs: number;
}

export interface TurnaroundByReviewer extends Record<string, unknown> {
  readonly reviewer: string;
  readonly avg_response_time_hours: number;
  readonly total_reviews: number;
  readonly repositories_reviewed: readonly string[];
}

export interface TurnaroundSummary {
  readonly avg_time_to_first_review_hours: number;
  readonly avg_time_to_first_changes_requested_hours: number;
  readonly avg_time_to_approval_hours: number;
  readonly avg_time_to_first_verified_hours: number;
  readonly avg_pr_lifecycle_hours: number;
  readonly total_prs_analyzed: number;
}

export interface TurnaroundMetrics {
  readonly summary: TurnaroundSummary;
  readonly by_repository: readonly TurnaroundByRepository[];
  readonly by_reviewer: readonly TurnaroundByReviewer[];
}
