/**
 * Shared utility for aggregating PR comment threads by PR number.
 * Used by both the pr-lifecycle page and its tests.
 */

export interface Thread {
  readonly repository: string;
  readonly pr_number: number;
  readonly pr_title: string | null;
  readonly resolved_at: string | null;
  readonly resolution_time_hours: number | null;
  readonly time_from_can_be_merged_hours: number | null;
}

export interface PRAggregated {
  readonly repository: string;
  readonly pr_number: number;
  readonly pr_title: string;
  readonly total_threads: number;
  readonly resolved_threads: number;
  readonly total_resolution_hours: number;
  readonly resolved_count: number;
  readonly time_from_can_be_merged_hours: number | null;
  readonly avg_resolution_hours: number | null;
}

/**
 * Aggregate comment threads by PR number.
 *
 * For each PR, calculates:
 * - Total threads
 * - Resolved threads
 * - Average resolution time
 * - Minimum (most negative) time_from_can_be_merged_hours
 *
 * @param threads - Array of thread data from API
 * @returns Array of aggregated PR data
 */
export function aggregateThreadsByPR(threads: readonly Thread[]): PRAggregated[] {
  const prMap = new Map<
    string,
    {
      repository: string;
      pr_number: number;
      pr_title: string;
      total_threads: number;
      resolved_threads: number;
      total_resolution_hours: number;
      resolved_count: number;
      time_from_can_be_merged_hours: number | null;
    }
  >();

  for (const thread of threads) {
    const key = `${thread.repository}#${String(thread.pr_number)}`;
    const existing = prMap.get(key);

    if (existing) {
      existing.total_threads++;
      if (thread.resolved_at) {
        existing.resolved_threads++;
        const resolutionTime = parseResolutionTime(thread.resolution_time_hours);
        if (resolutionTime !== null && !Number.isNaN(resolutionTime)) {
          existing.total_resolution_hours += resolutionTime;
          existing.resolved_count++;
        }
      }

      // Take the minimum (earliest/most negative) time_from_can_be_merged
      const mergedTime = parseResolutionTime(thread.time_from_can_be_merged_hours);
      if (mergedTime !== null && !Number.isNaN(mergedTime)) {
        if (existing.time_from_can_be_merged_hours === null) {
          existing.time_from_can_be_merged_hours = mergedTime;
        } else {
          existing.time_from_can_be_merged_hours = Math.min(
            existing.time_from_can_be_merged_hours,
            mergedTime
          );
        }
      }
    } else {
      const resolutionTime = parseResolutionTime(thread.resolution_time_hours);
      const mergedTime = parseResolutionTime(thread.time_from_can_be_merged_hours);

      const hasValidResolution = resolutionTime !== null && !Number.isNaN(resolutionTime);
      const validMergedTime = mergedTime !== null && !Number.isNaN(mergedTime) ? mergedTime : null;

      prMap.set(key, {
        repository: thread.repository,
        pr_number: thread.pr_number,
        pr_title: thread.pr_title ?? `PR #${String(thread.pr_number)}`,
        total_threads: 1,
        resolved_threads: thread.resolved_at ? 1 : 0,
        total_resolution_hours: hasValidResolution ? resolutionTime : 0,
        resolved_count: hasValidResolution ? 1 : 0,
        time_from_can_be_merged_hours: validMergedTime,
      });
    }
  }

  return Array.from(prMap.values()).map((pr) => ({
    ...pr,
    avg_resolution_hours:
      pr.resolved_count > 0 ? pr.total_resolution_hours / pr.resolved_count : null,
  }));
}

/**
 * Parse resolution time from API response.
 */
function parseResolutionTime(value: number | null | undefined): number | null {
  return typeof value === "number" ? value : null;
}
