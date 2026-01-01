import { describe, it, expect } from "vitest";

/**
 * Tests for PR lifecycle aggregation logic.
 *
 * This tests the exact logic used in pr-lifecycle.tsx lines 77-152
 * to aggregate thread data by PR number.
 */
describe("PR Lifecycle Aggregation", () => {
  interface Thread {
    repository: string;
    pr_number: number;
    pr_title: string | null;
    resolved_at: string | null;
    resolution_time_hours: number | string | null;
    time_from_can_be_merged_hours: number | string | null;
  }

  interface PRAggregated {
    repository: string;
    pr_number: number;
    pr_title: string;
    total_threads: number;
    resolved_threads: number;
    total_resolution_hours: number;
    resolved_count: number;
    time_from_can_be_merged_hours: number | null;
    avg_resolution_hours: number | null;
  }

  function aggregateThreadsByPR(threads: Thread[]): PRAggregated[] {
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
          const resolutionTime =
            typeof thread.resolution_time_hours === "string"
              ? parseFloat(thread.resolution_time_hours)
              : thread.resolution_time_hours;
          if (resolutionTime !== null && !Number.isNaN(resolutionTime)) {
            existing.total_resolution_hours += resolutionTime;
            existing.resolved_count++;
          }
        }

        // Take the minimum (earliest/most negative) time_from_can_be_merged
        const mergedTime =
          typeof thread.time_from_can_be_merged_hours === "string"
            ? parseFloat(thread.time_from_can_be_merged_hours)
            : thread.time_from_can_be_merged_hours;
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
        const resolutionTime =
          typeof thread.resolution_time_hours === "string"
            ? parseFloat(thread.resolution_time_hours)
            : thread.resolution_time_hours;
        const mergedTime =
          typeof thread.time_from_can_be_merged_hours === "string"
            ? parseFloat(thread.time_from_can_be_merged_hours)
            : thread.time_from_can_be_merged_hours;

        const validResolutionTime =
          resolutionTime !== null && !Number.isNaN(resolutionTime) ? resolutionTime : 0;
        const validMergedTime =
          mergedTime !== null && !Number.isNaN(mergedTime) ? mergedTime : null;

        prMap.set(key, {
          repository: thread.repository,
          pr_number: thread.pr_number,
          pr_title: thread.pr_title ?? `PR #${String(thread.pr_number)}`,
          total_threads: 1,
          resolved_threads: thread.resolved_at ? 1 : 0,
          total_resolution_hours: validResolutionTime,
          resolved_count: validResolutionTime > 0 || resolutionTime === 0 ? 1 : 0,
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

  it("aggregates threads with string time_from_can_be_merged_hours correctly", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: "5.0",
        time_from_can_be_merged_hours: "-21.3", // STRING
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: "6.0",
        time_from_can_be_merged_hours: "-21.7", // STRING
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T12:00:00Z",
        resolution_time_hours: "4.5",
        time_from_can_be_merged_hours: "-21.9", // STRING
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T13:00:00Z",
        resolution_time_hours: "7.0",
        time_from_can_be_merged_hours: "-21.9", // STRING
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T14:00:00Z",
        resolution_time_hours: "5.5",
        time_from_can_be_merged_hours: "-21.7", // STRING
      },
    ];

    const result = aggregateThreadsByPR(threads);

    expect(result).toHaveLength(1);
    expect(result[0].pr_number).toBe(2970);
    expect(result[0].total_threads).toBe(5);
    expect(result[0].resolved_threads).toBe(5);
    expect(result[0].time_from_can_be_merged_hours).toBe(-21.9); // Should be MOST negative
    expect(result[0].avg_resolution_hours).toBeCloseTo(5.6, 1);
  });

  it("aggregates threads with number time_from_can_be_merged_hours correctly", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo",
        pr_number: 123,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: 5.0,
        time_from_can_be_merged_hours: -21.3, // NUMBER
      },
      {
        repository: "org/repo",
        pr_number: 123,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: -21.7, // NUMBER
      },
    ];

    const result = aggregateThreadsByPR(threads);

    expect(result).toHaveLength(1);
    expect(result[0].time_from_can_be_merged_hours).toBe(-21.7);
  });

  it("handles null time_from_can_be_merged_hours correctly", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo",
        pr_number: 456,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: 5.0,
        time_from_can_be_merged_hours: null, // NULL
      },
      {
        repository: "org/repo",
        pr_number: 456,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: "-21.7",
      },
    ];

    const result = aggregateThreadsByPR(threads);

    expect(result).toHaveLength(1);
    expect(result[0].time_from_can_be_merged_hours).toBe(-21.7); // Should use the non-null value
  });

  it("handles mixed positive and negative values correctly", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo",
        pr_number: 789,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: 5.0,
        time_from_can_be_merged_hours: "10.5", // Positive (resolved after CI)
      },
      {
        repository: "org/repo",
        pr_number: 789,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: "-5.3", // Negative (resolved before CI)
      },
    ];

    const result = aggregateThreadsByPR(threads);

    expect(result).toHaveLength(1);
    expect(result[0].time_from_can_be_merged_hours).toBe(-5.3); // Should be minimum (most negative)
  });

  it("aggregates multiple PRs correctly", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo1",
        pr_number: 100,
        pr_title: "PR 100",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: 5.0,
        time_from_can_be_merged_hours: "-10.0",
      },
      {
        repository: "org/repo1",
        pr_number: 200,
        pr_title: "PR 200",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 3.0,
        time_from_can_be_merged_hours: "-15.0",
      },
      {
        repository: "org/repo1",
        pr_number: 100,
        pr_title: "PR 100",
        resolved_at: "2024-01-01T12:00:00Z",
        resolution_time_hours: 7.0,
        time_from_can_be_merged_hours: "-12.0",
      },
    ];

    const result = aggregateThreadsByPR(threads);

    expect(result).toHaveLength(2);

    const pr100 = result.find((pr) => pr.pr_number === 100);
    const pr200 = result.find((pr) => pr.pr_number === 200);

    expect(pr100?.total_threads).toBe(2);
    expect(pr100?.time_from_can_be_merged_hours).toBe(-12.0); // min(-10, -12)

    expect(pr200?.total_threads).toBe(1);
    expect(pr200?.time_from_can_be_merged_hours).toBe(-15.0);
  });
});
