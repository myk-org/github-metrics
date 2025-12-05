export interface PRStory {
  readonly pr: {
    readonly number: number;
    readonly title: string;
    readonly author: string;
    readonly state: string;
    readonly merged: boolean;
    readonly repository: string;
    readonly created_at: string;
  };
  readonly events: readonly PRStoryEvent[];
  readonly summary: {
    readonly total_commits: number;
    readonly total_reviews: number;
    readonly total_check_runs: number;
    readonly total_comments: number;
  };
}

export interface PRStoryEvent {
  readonly event_type: string;
  readonly timestamp: string;
  readonly description?: string;
  readonly body?: string;
  readonly url?: string;
  readonly truncated?: boolean;
  readonly children?: readonly PRStoryCheckRun[];
  readonly commit?: string;
}

export interface PRStoryCheckRun {
  readonly name: string;
  readonly conclusion: string;
  readonly description?: string;
}

export type PREventType =
  | "pr_opened"
  | "pr_closed"
  | "pr_merged"
  | "pr_reopened"
  | "commit"
  | "review_approved"
  | "review_changes"
  | "review_commented"
  | "review_comment"
  | "comment"
  | "review_requested"
  | "label_added"
  | "label_removed"
  | "verified"
  | "approved_label"
  | "lgtm"
  | "check_run"
  | "check_run_completed"
  | "ready_for_review"
  | "converted_to_draft";
