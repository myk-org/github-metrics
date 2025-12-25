import { useState } from "react";
import { useFilters } from "@/hooks/use-filters";
import { useCommentResolution, usePRStory } from "@/hooks/use-api";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { DataTable, type ColumnDef } from "@/components/shared/data-table";
import { KPICards, type KPIItem } from "@/components/shared/kpi-cards";
import { DownloadButtons } from "@/components/shared/download-buttons";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { PRStoryModal } from "@/components/pr-story/pr-story-modal";
import { Button } from "@/components/ui/button";
import { History } from "lucide-react";
import { formatHours } from "@/utils/time-format";
import type { CommentThread } from "@/types/comment-resolution";

export function CommentResolutionPage(): React.ReactElement {
  const { filters } = useFilters();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

  // PR Story modal state
  const [prStoryModalOpen, setPrStoryModalOpen] = useState(false);
  const [selectedPR, setSelectedPR] = useState<{ repository: string; number: number } | null>(null);

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
    }, 200);
  };

  // Fetch comment resolution data with server-side pagination
  const { data, isLoading } = useCommentResolution(
    filters.timeRange,
    filters.repositories,
    page,
    pageSize
  );

  const threads = data?.threads ?? [];

  // KPI Cards for summary metrics
  const summaryKPIs: readonly KPIItem[] = data?.summary
    ? [
        {
          label: "Avg Resolution Time",
          value: formatHours(data.summary.avg_resolution_time_hours),
        },
        {
          label: "Median Resolution Time",
          value: formatHours(data.summary.median_resolution_time_hours),
        },
        {
          label: "Avg Time to First Response",
          value: formatHours(data.summary.avg_time_to_first_response_hours),
        },
        {
          label: "Avg Comments per Thread",
          value:
            typeof data.summary.avg_comments_per_thread === "number"
              ? data.summary.avg_comments_per_thread.toFixed(1)
              : "-",
        },
        {
          label: "Total Threads Analyzed",
          value: data.summary.total_threads_analyzed,
        },
        {
          label: "Resolution Rate",
          value:
            typeof data.summary.resolution_rate === "number"
              ? `${data.summary.resolution_rate.toFixed(1)}%`
              : "-",
        },
      ]
    : [];

  // Column definitions for Comment Threads
  const threadColumns: readonly ColumnDef<CommentThread>[] = [
    {
      key: "pr_number",
      label: "PR#",
      sortable: true,
      render: (item) => (
        <a
          href={`https://github.com/${item.repository}/pull/${String(item.pr_number)}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          #{item.pr_number}
        </a>
      ),
      getValue: (item) => item.pr_number,
    },
    {
      key: "repository",
      label: "Repository",
      sortable: true,
      getValue: (item) => item.repository,
    },
    {
      key: "file_path",
      label: "File Path",
      sortable: true,
      render: (item) => (
        <span className="truncate max-w-xs block" title={item.file_path ?? undefined}>
          {item.file_path ?? "-"}
        </span>
      ),
      getValue: (item) => item.file_path ?? "",
    },
    {
      key: "comment_count",
      label: "Comments",
      align: "right",
      sortable: true,
      getValue: (item) => item.comment_count,
    },
    {
      key: "resolution_time_hours",
      label: "Resolution Time",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.resolution_time_hours),
      getValue: (item) => item.resolution_time_hours ?? 0,
    },
    {
      key: "time_to_first_response_hours",
      label: "Time to First Response",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.time_to_first_response_hours),
      getValue: (item) => item.time_to_first_response_hours ?? 0,
    },
    {
      key: "time_from_can_be_merged_hours",
      label: "Time from Can-be-Merged",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.time_from_can_be_merged_hours),
      getValue: (item) => item.time_from_can_be_merged_hours ?? 0,
    },
    {
      key: "resolver",
      label: "Resolver",
      sortable: true,
      getValue: (item) => item.resolver ?? "",
      render: (item) => item.resolver ?? "-",
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
          aria-label={`View PR story for #${String(item.pr_number)}`}
        >
          <History className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Comment Resolution</h2>
      </div>

      {/* Summary Section */}
      <CollapsibleSection
        title="Summary Metrics"
        actions={<DownloadButtons data={threads} filename="comment-resolution-threads" />}
      >
        <div className="space-y-4">
          <KPICards items={summaryKPIs} isLoading={isLoading} columns={3} />
        </div>
      </CollapsibleSection>

      {/* Comment Threads Table */}
      <CollapsibleSection title="Comment Threads">
        <div className="space-y-4">
          <DataTable
            columns={threadColumns}
            data={threads}
            isLoading={isLoading}
            keyExtractor={(item) => item.thread_node_id}
            emptyMessage="No comment threads available"
          />
          {data?.pagination && (
            <div className="flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} to{" "}
                {Math.min(page * pageSize, data.pagination.total)} of {data.pagination.total}{" "}
                threads
              </div>
              <PaginationControls
                currentPage={page}
                totalPages={Math.max(1, data.pagination.total_pages)}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={(size: number) => {
                  setPageSize(size);
                  setPage(1); // Reset to first page
                }}
              />
            </div>
          )}
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
