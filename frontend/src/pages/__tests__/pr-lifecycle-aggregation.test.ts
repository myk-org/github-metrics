import { describe, it, expect } from "vitest";
import { aggregateThreadsByPR, type Thread } from "@/utils/pr-aggregation";

/**
 * Tests for PR lifecycle aggregation logic.
 *
 * This tests the shared aggregation utility used by pr-lifecycle.tsx
 * to aggregate thread data by PR number.
 */
describe("PR Lifecycle Aggregation", () => {
  it("aggregates threads with number time_from_can_be_merged_hours correctly", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: 5.0,
        time_from_can_be_merged_hours: -21.3,
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: -21.7,
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T12:00:00Z",
        resolution_time_hours: 4.5,
        time_from_can_be_merged_hours: -21.9,
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T13:00:00Z",
        resolution_time_hours: 7.0,
        time_from_can_be_merged_hours: -21.9,
      },
      {
        repository: "org/repo",
        pr_number: 2970,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T14:00:00Z",
        resolution_time_hours: 5.5,
        time_from_can_be_merged_hours: -21.7,
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

  it("aggregates threads correctly using minimum time_from_can_be_merged_hours", () => {
    const threads: Thread[] = [
      {
        repository: "org/repo",
        pr_number: 123,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T10:00:00Z",
        resolution_time_hours: 5.0,
        time_from_can_be_merged_hours: -21.3,
      },
      {
        repository: "org/repo",
        pr_number: 123,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: -21.7,
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
        time_from_can_be_merged_hours: null,
      },
      {
        repository: "org/repo",
        pr_number: 456,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: -21.7,
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
        time_from_can_be_merged_hours: 10.5, // Positive (resolved after CI)
      },
      {
        repository: "org/repo",
        pr_number: 789,
        pr_title: "Test PR",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 6.0,
        time_from_can_be_merged_hours: -5.3, // Negative (resolved before CI)
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
        time_from_can_be_merged_hours: -10.0,
      },
      {
        repository: "org/repo1",
        pr_number: 200,
        pr_title: "PR 200",
        resolved_at: "2024-01-01T11:00:00Z",
        resolution_time_hours: 3.0,
        time_from_can_be_merged_hours: -15.0,
      },
      {
        repository: "org/repo1",
        pr_number: 100,
        pr_title: "PR 100",
        resolved_at: "2024-01-01T12:00:00Z",
        resolution_time_hours: 7.0,
        time_from_can_be_merged_hours: -12.0,
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
