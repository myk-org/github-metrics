/**
 * Response structure for the maintainers API endpoint.
 */
export interface MaintainersResponse {
  /** Mapping of repository names to their maintainer usernames */
  readonly maintainers: Readonly<Record<string, readonly string[]>>;
  /** Deduplicated sorted list of all maintainers across all repositories */
  readonly all_maintainers: readonly string[];
}
