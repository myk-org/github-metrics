export interface WorkloadContributor {
  readonly user: string;
  readonly prs_created: number;
  readonly prs_reviewed: number;
  readonly prs_approved: number;
  readonly [key: string]: unknown;
}

export interface WorkloadSummary {
  readonly total_contributors: number;
  readonly avg_prs_per_contributor: number;
  readonly top_contributor: {
    readonly user: string;
    readonly total_prs: number;
  } | null;
  readonly workload_gini: number;
}

export interface ReviewerEfficiency {
  readonly user: string;
  readonly avg_review_time_hours: number;
  readonly median_review_time_hours: number;
  readonly total_reviews: number;
  readonly [key: string]: unknown;
}

export interface ReviewEfficiencySummary {
  readonly avg_review_time_hours: number;
  readonly median_review_time_hours: number;
  readonly fastest_reviewer: {
    readonly user: string;
    readonly avg_hours: number;
  } | null;
  readonly slowest_reviewer: {
    readonly user: string;
    readonly avg_hours: number;
  } | null;
}

export interface ApprovalBottleneck {
  readonly approver: string;
  readonly avg_approval_hours: number;
  readonly total_approvals: number;
  readonly [key: string]: unknown;
}

export interface BottleneckAlert {
  readonly approver: string;
  readonly avg_approval_hours: number;
  readonly team_pending_count: number;
  readonly severity: "warning" | "critical";
}

export interface Pagination {
  readonly page: number;
  readonly page_size: number;
  readonly total: number;
  readonly total_pages: number;
}

export interface TeamDynamicsResponse {
  readonly workload: {
    readonly summary: WorkloadSummary;
    readonly by_contributor: readonly WorkloadContributor[];
    readonly pagination: Pagination;
  };
  readonly review_efficiency: {
    readonly summary: ReviewEfficiencySummary;
    readonly by_reviewer: readonly ReviewerEfficiency[];
    readonly pagination: Pagination;
  };
  readonly bottlenecks: {
    readonly alerts: readonly BottleneckAlert[];
    readonly by_approver: readonly ApprovalBottleneck[];
    readonly pagination: Pagination;
  };
}
