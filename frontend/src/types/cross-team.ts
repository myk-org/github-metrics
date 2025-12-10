import type { Pagination } from "./contributors";

export interface CrossTeamReview {
  readonly pr_number: number;
  readonly repository: string;
  readonly reviewer: string;
  readonly reviewer_team: string;
  readonly pr_sig_label: string;
  readonly review_type: string;
  readonly created_at: string;
}

// Wrapper type for DataTable compatibility
export type CrossTeamReviewRow = CrossTeamReview & Record<string, unknown>;

export interface CrossTeamSummary {
  readonly total_cross_team_reviews: number;
  readonly by_reviewer_team: Record<string, number>;
  readonly by_pr_team: Record<string, number>;
}

export interface CrossTeamData {
  readonly data: readonly CrossTeamReview[];
  readonly summary: CrossTeamSummary;
  readonly pagination: Pagination;
}
