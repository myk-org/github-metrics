export interface PRCreator {
  readonly user: string;
  readonly total_prs: number;
  readonly merged_prs: number;
  readonly closed_prs: number;
  readonly avg_commits_per_pr: number;
  readonly [key: string]: unknown;
}

export interface PRReviewer {
  readonly user: string;
  readonly total_reviews: number;
  readonly prs_reviewed: number;
  readonly avg_reviews_per_pr: number;
  readonly cross_team_reviews: number;
  readonly [key: string]: unknown;
}

export interface PRApprover {
  readonly user: string;
  readonly total_approvals: number;
  readonly prs_approved: number;
  readonly [key: string]: unknown;
}

export interface PRLgtm {
  readonly user: string;
  readonly total_lgtm: number;
  readonly prs_lgtm: number;
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

export interface ContributorMetrics {
  readonly time_range: {
    readonly start_time: string | null;
    readonly end_time: string | null;
  };
  readonly pr_creators: {
    readonly data: readonly PRCreator[];
    readonly pagination: Pagination;
  };
  readonly pr_reviewers: {
    readonly data: readonly PRReviewer[];
    readonly pagination: Pagination;
  };
  readonly pr_approvers: {
    readonly data: readonly PRApprover[];
    readonly pagination: Pagination;
  };
  readonly pr_lgtm: {
    readonly data: readonly PRLgtm[];
    readonly pagination: Pagination;
  };
}
