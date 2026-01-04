import { useState, useMemo } from "react";
import { useFilters } from "@/hooks/use-filters";
import { useTurnaround, useCommentResolution, usePRStory, useExcludeUsers } from "@/hooks/use-api";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { DataTable, type ColumnDef } from "@/components/shared/data-table";
import { KPICards, type KPIItem } from "@/components/shared/kpi-cards";
import { DownloadButtons } from "@/components/shared/download-buttons";
import { PRStoryModal } from "@/components/pr-story/pr-story-modal";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { History, Info } from "lucide-react";
import type { TurnaroundByRepository } from "@/types/metrics";
import { formatHours } from "@/utils/time-format";
import { aggregateThreadsByPR, type PRAggregated } from "@/utils/pr-aggregation";

const MAX_AGGREGATION_THREADS = 1000;
const MODAL_CLOSE_ANIMATION_MS = 200;

/**
 * Safely formats a number to fixed decimal places.
 * Returns "-" if the value is not a valid number.
 * This handles edge cases where API might return unexpected types.
 */
function safeToFixed(value: unknown, decimals: number): string {
  if (typeof value === "number" && !Number.isNaN(value)) {
    return value.toFixed(decimals);
  }
  return "-";
}

export function PRLifecyclePage(): React.ReactElement {
  const { filters } = useFilters();

  // PR Story modal state
  const [prStoryModalOpen, setPrStoryModalOpen] = useState(false);
  const [selectedPR, setSelectedPR] = useState<{ repository: string; number: number } | null>(null);

  // Handlers for PR Story modal
  const handleOpenPRStory = (repository: string, prNumber: number): void => {
    setSelectedPR({ repository, number: prNumber });
    setPrStoryModalOpen(true);
  };

  const handleClosePRStory = (): void => {
    setPrStoryModalOpen(false);
    // Don't clear selectedPR immediately to avoid flashing during close animation
    setTimeout(() => {
      setSelectedPR(null);
    }, MODAL_CLOSE_ANIMATION_MS);
  };

  // Combine exclude_users with maintainers if excludeMaintainers is enabled
  const { users: effectiveExcludeUsers, isLoading: isExcludeUsersLoading } = useExcludeUsers(
    filters.excludeUsers,
    filters.excludeMaintainers
  );

  // Fetch turnaround metrics for lifecycle KPIs
  const { data: turnaround, isLoading: turnaroundDataLoading } = useTurnaround(
    filters.timeRange,
    {
      repositories: filters.repositories,
      users: filters.users,
      exclude_users: effectiveExcludeUsers,
    },
    !isExcludeUsersLoading
  );

  // Combine loading states
  const turnaroundLoading = turnaroundDataLoading || isExcludeUsersLoading;

  // Fetch comment resolution data (client-side aggregation by PR)
  const { data: commentsData, isLoading: commentsLoading } = useCommentResolution(
    filters.timeRange,
    filters.repositories,
    1,
    MAX_AGGREGATION_THREADS
  );

  // Aggregate threads by PR using shared utility
  const prAggregatedData = useMemo(() => {
    if (!commentsData) return [];
    return aggregateThreadsByPR(commentsData.threads);
  }, [commentsData]);

  // Fetch PR Story when modal is open and PR is selected
  const {
    data: prStoryData,
    isLoading: prStoryLoading,
    error: prStoryError,
  } = usePRStory(
    selectedPR?.repository ?? "",
    selectedPR?.number ?? 0,
    prStoryModalOpen && selectedPR !== null
  );

  // Build KPI items from turnaround metrics
  const lifecycleKPIs: readonly KPIItem[] = turnaround?.summary
    ? [
        {
          label: "Avg Time to First Review",
          value: formatHours(turnaround.summary.avg_time_to_first_review_hours),
          tooltip:
            "Average hours from PR opened to first review. Calculated from pull_request_review submitted events, excluding self-reviews.",
        },
        {
          label: "Avg Time to Changes Requested",
          value: formatHours(turnaround.summary.avg_time_to_first_changes_requested_hours),
          tooltip:
            "Average hours from PR opened to first changes_requested review. Calculated from pull_request_review events with state=changes_requested.",
        },
        {
          label: "Avg Time to Approval",
          value: formatHours(turnaround.summary.avg_time_to_approval_hours),
          tooltip:
            "Average hours from PR opened to first approved-* label. Calculated from pull_request labeled events.",
        },
        {
          label: "Avg Time to First Verified",
          value: formatHours(turnaround.summary.avg_time_to_first_verified_hours),
          tooltip:
            "Average hours from PR opened to first *verified* label. Calculated from pull_request labeled events.",
        },
        {
          label: "Avg PR Lifecycle",
          value: formatHours(turnaround.summary.avg_pr_lifecycle_hours),
          tooltip:
            "Average hours from PR opened to closed/merged. Only completed PRs. Calculated from pull_request closed events.",
        },
        {
          label: "PRs Analyzed",
          value: turnaround.summary.total_prs_analyzed,
          tooltip:
            "Total PRs opened in the time range. Counted from pull_request opened webhook events.",
        },
      ]
    : [];

  // KPI items for PR Comments section
  const commentsKPIs: readonly KPIItem[] = commentsData?.summary
    ? [
        {
          label: "Avg Resolution Time",
          value: formatHours(commentsData.summary.avg_resolution_time_hours),
          tooltip:
            "Average hours from first comment to thread resolution. Calculated from pull_request_review_thread resolved events.",
        },
        {
          label: "Median Resolution Time",
          value: formatHours(commentsData.summary.median_resolution_time_hours),
          tooltip:
            "Median hours to resolution (50th percentile). Less affected by outliers. From pull_request_review_thread events.",
        },
        {
          label: "Avg Time to First Response",
          value: formatHours(commentsData.summary.avg_time_to_first_response_hours),
          tooltip:
            "Average hours from first comment to second comment in thread. Calculated from pull_request_review_comment events.",
        },
        {
          label: "Avg Comments per Thread",
          value: safeToFixed(commentsData.summary.avg_comments_per_thread, 1),
          tooltip:
            "Average comments per review thread. Counted from pull_request_review_comment created events.",
        },
        {
          label: "Total Threads",
          value: commentsData.summary.total_threads_analyzed,
          tooltip:
            "Total review threads in the time range. Counted from unique thread IDs in pull_request_review_comment events.",
        },
        {
          label: "Resolution Rate",
          value: `${safeToFixed(commentsData.summary.resolution_rate, 1)}%`,
          tooltip:
            "Percentage of threads resolved. (Resolved threads / Total threads) × 100. From pull_request_review_thread events.",
        },
      ]
    : [];

  // Column definitions for Turnaround by Repository
  const turnaroundByRepoColumns: readonly ColumnDef<TurnaroundByRepository>[] = [
    {
      key: "repository",
      label: "Repository",
      sortable: true,
    },
    {
      key: "avg_time_to_first_review_hours",
      label: "First Review",
      tooltip: "Average hours from PR opened to first review. From pull_request_review events.",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_time_to_first_review_hours),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.avg_time_to_first_review_hours,
    },
    {
      key: "avg_time_to_first_changes_requested_hours",
      label: "Changes Req.",
      tooltip: "Average hours to first changes_requested review",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_time_to_first_changes_requested_hours),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.avg_time_to_first_changes_requested_hours,
    },
    {
      key: "avg_time_to_approval_hours",
      label: "Approval",
      tooltip: "Average hours to first approved-* label",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_time_to_approval_hours),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.avg_time_to_approval_hours,
    },
    {
      key: "avg_time_to_first_verified_hours",
      label: "Verified",
      tooltip: "Average hours to first *verified* label",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_time_to_first_verified_hours),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.avg_time_to_first_verified_hours,
    },
    {
      key: "avg_pr_lifecycle_hours",
      label: "Lifecycle",
      tooltip: "Average hours from PR opened to closed/merged (completed PRs only)",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_pr_lifecycle_hours),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.avg_pr_lifecycle_hours,
    },
    {
      key: "total_prs",
      label: "PRs",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_prs,
    },
  ];

  // Column definitions for PR Comments (aggregated by PR)
  const commentsColumns: readonly ColumnDef<PRAggregated>[] = [
    {
      key: "pr_info",
      label: "Pull Request",
      sortable: true,
      render: (item) => (
        <div className="min-w-0 max-w-sm">
          <div className="flex items-center gap-2 mb-1">
            <a
              href={`https://github.com/${item.repository}/pull/${item.pr_number}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm font-bold text-primary hover:underline flex-shrink-0"
            >
              #{item.pr_number}
            </a>
            <span className="text-sm font-medium truncate" title={item.pr_title}>
              {item.pr_title}
            </span>
          </div>
          <div className="text-xs text-muted-foreground font-mono truncate">{item.repository}</div>
        </div>
      ),
      getValue: (item) => item.pr_number,
    },
    {
      key: "total_threads",
      label: "Threads",
      align: "right",
      sortable: true,
      render: (item) => <span className="whitespace-nowrap">{item.total_threads}</span>,
      getValue: (item) => item.total_threads,
    },
    {
      key: "resolved_threads",
      label: "Resolved",
      align: "right",
      sortable: true,
      render: (item) => <span className="whitespace-nowrap">{item.resolved_threads}</span>,
      getValue: (item) => item.resolved_threads,
    },
    {
      key: "avg_resolution_hours",
      label: "Avg Resolution",
      tooltip: "Average hours to resolve threads on this PR",
      align: "right",
      sortable: true,
      render: (item) => (
        <span className="whitespace-nowrap">{formatHours(item.avg_resolution_hours)}</span>
      ),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.avg_resolution_hours,
    },
    {
      key: "time_from_can_be_merged_hours",
      label: "Post-CI Wait",
      tooltip: "Hours from can-be-merged check success to last thread resolution",
      align: "right",
      sortable: true,
      render: (item) => (
        <span className="whitespace-nowrap">{formatHours(item.time_from_can_be_merged_hours)}</span>
      ),
      // null values sort to end (handled by DataTable component)
      getValue: (item) => item.time_from_can_be_merged_hours,
    },
    {
      key: "actions",
      label: "Timeline",
      sortable: false,
      render: (item) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            handleOpenPRStory(item.repository, item.pr_number);
          }}
          className="h-8 w-8 p-0"
          aria-label={`View PR story for #${item.pr_number}`}
        >
          <History className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* PR Lifecycle KPIs */}
      <KPICards items={lifecycleKPIs} isLoading={turnaroundLoading} columns={6} />

      {/* Turnaround by Repository */}
      <CollapsibleSection
        title="Turnaround by Repository"
        actions={
          <DownloadButtons
            data={turnaround?.by_repository ?? []}
            filename="turnaround-by-repository"
          />
        }
      >
        <DataTable
          columns={turnaroundByRepoColumns}
          data={turnaround?.by_repository ?? []}
          isLoading={turnaroundLoading}
          keyExtractor={(item) => item.repository}
          emptyMessage="No turnaround data by repository found"
        />
      </CollapsibleSection>

      {/* PR Comments Section */}
      <CollapsibleSection
        title="PR Comments"
        actions={<DownloadButtons data={prAggregatedData} filename="pr-comments" />}
      >
        <div className="space-y-4">
          <KPICards items={commentsKPIs} isLoading={commentsLoading} columns={3} />
          {commentsData?.pagination && commentsData.pagination.total > MAX_AGGREGATION_THREADS && (
            <Alert
              variant="default"
              className="bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800"
            >
              <Info className="h-4 w-4 text-blue-600 dark:text-blue-500" />
              <AlertDescription className="text-blue-800 dark:text-blue-200">
                Showing aggregated data for {MAX_AGGREGATION_THREADS.toLocaleString()} of{" "}
                {commentsData.pagination.total.toLocaleString()} total threads. Narrow your time
                range or repository filter for complete data.
              </AlertDescription>
            </Alert>
          )}
          <DataTable
            columns={commentsColumns}
            data={prAggregatedData}
            isLoading={commentsLoading}
            keyExtractor={(item: PRAggregated) => `${item.repository}#${item.pr_number}`}
            emptyMessage="No PR comments data available. Enable pull_request_review_thread webhooks to see data."
          />
          <div className="text-sm text-muted-foreground">Showing {prAggregatedData.length} PRs</div>
        </div>
      </CollapsibleSection>

      {/* PR Story Modal */}
      <PRStoryModal
        isOpen={prStoryModalOpen}
        onClose={handleClosePRStory}
        prStory={prStoryData}
        isLoading={prStoryLoading}
        error={prStoryError}
      />
    </div>
  );
}
