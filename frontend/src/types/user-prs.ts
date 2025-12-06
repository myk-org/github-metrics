export interface UserPR {
  readonly number: number;
  readonly title: string;
  readonly owner: string;
  readonly repository: string;
  readonly state: string;
  readonly merged: boolean;
  readonly url: string;
  readonly created_at: string;
  readonly updated_at: string;
  readonly commits_count: number;
  readonly head_sha: string;
  readonly [key: string]: unknown;
}

export interface UserPRsResponse {
  readonly data: readonly UserPR[];
  readonly pagination: {
    readonly page: number;
    readonly page_size: number;
    readonly total: number;
    readonly total_pages: number;
  };
}
