import { useState } from "react";
import { useFilters } from "@/hooks/use-filters";
import { useDateFormat } from "@/hooks/use-date-format";
import { useTeamDynamics, useCrossTeamReviews, usePRStory, useExcludeUsers } from "@/hooks/use-api";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { DataTable, type ColumnDef } from "@/components/shared/data-table";
import { KPICards, type KPIItem } from "@/components/shared/kpi-cards";
import { DownloadButtons } from "@/components/shared/download-buttons";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { UserPRsModal } from "@/components/user-prs";
import { PRStoryModal } from "@/components/pr-story/pr-story-modal";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { History } from "lucide-react";
import { formatHours, formatDate } from "@/utils/time-format";
import type {
  WorkloadContributor,
  ReviewerEfficiency,
  ApprovalBottleneck,
  BottleneckAlert,
} from "@/types/team-dynamics";
import type { CrossTeamReviewRow } from "@/types/cross-team";

const MAX_MIN_REVIEWS = 100;

export function TeamDynamicsPage(): React.ReactElement {
  const { filters } = useFilters();
  const { dateFormat } = useDateFormat();
  // Single page state for all sections since API returns all team dynamics data in one call
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [minReviews, setMinReviews] = useState(5);

  // Modal state for user PRs
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Handler to open modal with user PRs
  const handleUserClick = (username: string, category: string): void => {
    setSelectedUser(username);
    setSelectedCategory(category);
    setIsModalOpen(true);
  };

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

  // Combine exclude_users with maintainers if excludeMaintainers is enabled
  const { users: effectiveExcludeUsers, isLoading: isExcludeUsersLoading } = useExcludeUsers(
    filters.excludeUsers,
    filters.excludeMaintainers
  );

  // Fetch team dynamics data with server-side pagination
  const { data: teamData, isLoading: teamDataLoading } = useTeamDynamics(
    filters.timeRange,
    {
      repositories: filters.repositories,
      users: filters.users,
      exclude_users: effectiveExcludeUsers,
    },
    page,
    pageSize,
    minReviews,
    !isExcludeUsersLoading
  );

  // Combine loading states
  const isLoading = teamDataLoading || isExcludeUsersLoading;

  // Fetch cross-team reviews data with separate pagination
  const [crossTeamPage, setCrossTeamPage] = useState(1);
  const [crossTeamPageSize, setCrossTeamPageSize] = useState(25);

  const { data: crossTeamData, isLoading: crossTeamDataLoading } = useCrossTeamReviews(
    filters.timeRange,
    {
      repositories: filters.repositories,
      users: filters.users,
      exclude_users: effectiveExcludeUsers,
    },
    crossTeamPage,
    crossTeamPageSize,
    !isExcludeUsersLoading
  );

  // Combine loading states
  const isCrossTeamLoading = crossTeamDataLoading || isExcludeUsersLoading;

  // Server-side paginated data for each section
  const workloadData = teamData?.workload.by_contributor ?? [];
  const reviewData = teamData?.review_efficiency.by_reviewer ?? [];
  const bottleneckData = teamData?.bottlenecks.by_approver ?? [];
  const crossTeamReviewsData: readonly CrossTeamReviewRow[] = (crossTeamData?.data ??
    []) as readonly CrossTeamReviewRow[];

  // Workload Distribution KPIs
  const workloadKPIs: readonly KPIItem[] = teamData?.workload.summary
    ? [
        {
          label: "Total Contributors",
          value: teamData.workload.summary.total_contributors,
          tooltip:
            "Unique users who created PRs in the time range. Counted from pull_request opened webhook events.",
        },
        {
          label: "Avg PRs per Contributor",
          value:
            typeof teamData.workload.summary.avg_prs_per_contributor === "number"
              ? teamData.workload.summary.avg_prs_per_contributor.toFixed(1)
              : "-",
          tooltip:
            "Average PRs created per contributor. Calculated as total PRs / total contributors.",
        },
        {
          label: "Top Contributor",
          value: teamData.workload.summary.top_contributor?.user ?? "N/A",
          tooltip: "User who created the most PRs in the time range. Shows username with PR count.",
        },
        {
          label: "Workload Gini Coefficient",
          value:
            typeof teamData.workload.summary.workload_gini === "number"
              ? teamData.workload.summary.workload_gini.toFixed(2)
              : "-",
          tooltip:
            "Gini coefficient (0-1) measuring workload distribution. 0 = perfectly equal, 1 = one person does all work. Calculated from PR counts per contributor.",
        },
      ]
    : [];

  // Review Efficiency KPIs
  const reviewKPIs: readonly KPIItem[] = teamData?.review_efficiency.summary
    ? [
        {
          label: "Avg Review Time",
          value: formatHours(teamData.review_efficiency.summary.avg_review_time_hours),
          tooltip:
            "Average hours from PR opened to first review. Calculated from pull_request_review webhook events.",
        },
        {
          label: "Median Review Time",
          value: formatHours(teamData.review_efficiency.summary.median_review_time_hours),
          tooltip:
            "Median hours to first review (50th percentile). Less affected by outliers than average.",
        },
        {
          label: "Fastest Reviewer",
          value: teamData.review_efficiency.summary.fastest_reviewer?.user ?? "N/A",
          tooltip:
            "Reviewer with lowest average response time. Requires minimum review threshold to qualify.",
          ...(teamData.review_efficiency.summary.fastest_reviewer?.low_sample_size && {
            warning: `Sample size: ${String(teamData.review_efficiency.summary.fastest_reviewer.total_reviews)} reviews (below ${String(teamData.review_efficiency.summary.min_reviews_threshold)} threshold)`,
          }),
        },
        {
          label: "Slowest Reviewer",
          value: teamData.review_efficiency.summary.slowest_reviewer?.user ?? "N/A",
          tooltip:
            "Reviewer with highest average response time. Requires minimum review threshold to qualify.",
          ...(teamData.review_efficiency.summary.slowest_reviewer?.low_sample_size && {
            warning: `Sample size: ${String(teamData.review_efficiency.summary.slowest_reviewer.total_reviews)} reviews (below ${String(teamData.review_efficiency.summary.min_reviews_threshold)} threshold)`,
          }),
        },
      ]
    : [];

  // Bottleneck Alerts (for display at top of section)
  const bottleneckAlerts: readonly BottleneckAlert[] = teamData?.bottlenecks.alerts ?? [];

  // Cross-Team Collaboration KPIs
  const crossTeamKPIs: readonly KPIItem[] = crossTeamData?.summary
    ? [
        {
          label: "Total Cross-Team Reviews",
          value: crossTeamData.summary.total_cross_team_reviews,
          tooltip:
            "Reviews where reviewer's team differs from PR's sig label. Calculated from pull_request_review events matched with sig-* labels.",
        },
        {
          label: "Top Reviewer Team",
          value:
            Object.entries(crossTeamData.summary.by_reviewer_team).sort(
              ([, a], [, b]) => b - a
            )[0]?.[0] ?? "N/A",
          tooltip:
            "Team that performed the most cross-team reviews. Based on reviewer's sig-* label membership.",
        },
        {
          label: "Top PR Team",
          value:
            Object.entries(crossTeamData.summary.by_pr_team).sort(
              ([, a], [, b]) => b - a
            )[0]?.[0] ?? "N/A",
          tooltip:
            "Team whose PRs received the most cross-team reviews. Based on PR's sig-* label.",
        },
      ]
    : [];

  // Column definitions for Workload Distribution
  const workloadColumns: readonly ColumnDef<WorkloadContributor>[] = [
    {
      key: "user",
      label: "User",
      sortable: true,
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleUserClick(item.user, "pr_creators");
          }}
          className="text-primary hover:underline cursor-pointer font-medium"
        >
          {item.user}
        </button>
      ),
    },
    {
      key: "prs_created",
      label: "PRs Created",
      align: "right",
      sortable: true,
      getValue: (item) => item.prs_created,
    },
    {
      key: "prs_reviewed",
      label: "PRs Reviewed",
      align: "right",
      sortable: true,
      getValue: (item) => item.prs_reviewed,
    },
    {
      key: "prs_approved",
      label: "PRs Approved",
      align: "right",
      sortable: true,
      getValue: (item) => item.prs_approved,
    },
  ];

  // Column definitions for Review Efficiency
  const reviewColumns: readonly ColumnDef<ReviewerEfficiency>[] = [
    {
      key: "user",
      label: "Reviewer",
      sortable: true,
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleUserClick(item.user, "pr_reviewers");
          }}
          className="text-primary hover:underline cursor-pointer font-medium"
        >
          {item.user}
        </button>
      ),
    },
    {
      key: "avg_review_time_hours",
      label: "Avg Time",
      tooltip: "Average hours from PR opened to this reviewer's review",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_review_time_hours),
      getValue: (item) => item.avg_review_time_hours,
    },
    {
      key: "median_review_time_hours",
      label: "Median Time",
      tooltip: "Median review response time (50th percentile)",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.median_review_time_hours),
      getValue: (item) => item.median_review_time_hours,
    },
    {
      key: "total_reviews",
      label: "Reviews",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_reviews,
    },
  ];

  // Column definitions for Approval Bottlenecks
  const bottleneckColumns: readonly ColumnDef<ApprovalBottleneck>[] = [
    {
      key: "approver",
      label: "Approver",
      sortable: true,
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleUserClick(item.approver, "pr_approvers");
          }}
          className="text-primary hover:underline cursor-pointer font-medium"
        >
          {item.approver}
        </button>
      ),
    },
    {
      key: "avg_approval_hours",
      label: "Avg Approval Time",
      tooltip: "Average hours from PR opened to approval by this user",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_approval_hours),
      getValue: (item) => item.avg_approval_hours,
    },
    {
      key: "total_approvals",
      label: "Approvals",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_approvals,
    },
  ];

  // Column definitions for Cross-Team Reviews
  const crossTeamColumns: readonly ColumnDef<CrossTeamReviewRow>[] = [
    {
      key: "pr_number",
      label: "PR",
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
      key: "reviewer",
      label: "Reviewer",
      tooltip: "User who reviewed a PR from different team",
      sortable: true,
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleUserClick(item.reviewer, "pr_reviewers");
          }}
          className="text-primary hover:underline cursor-pointer font-medium"
        >
          {item.reviewer}
        </button>
      ),
      getValue: (item) => item.reviewer,
    },
    {
      key: "reviewer_team",
      label: "Reviewer Team",
      sortable: true,
      getValue: (item) => item.reviewer_team,
    },
    {
      key: "pr_sig_label",
      label: "PR Team",
      tooltip: "sig-* label on the PR being reviewed",
      sortable: true,
      getValue: (item) => item.pr_sig_label,
    },
    {
      key: "review_type",
      label: "Review Type",
      tooltip: "Type of review: approved, changes_requested, commented, or lgtm",
      sortable: true,
      getValue: (item) => item.review_type,
    },
    {
      key: "created_at",
      label: "Date",
      sortable: true,
      render: (item) => formatDate(item.created_at, dateFormat),
      getValue: (item) => item.created_at,
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
        <h2 className="text-2xl font-bold">Team Dynamics</h2>
      </div>

      {/* Workload Distribution */}
      <CollapsibleSection
        title="Workload Distribution"
        actions={<DownloadButtons data={workloadData} filename="workload-distribution" />}
      >
        <div className="space-y-4">
          <KPICards items={workloadKPIs} isLoading={isLoading} columns={4} />
          <DataTable
            columns={workloadColumns}
            data={workloadData}
            isLoading={isLoading}
            keyExtractor={(item) => item.user}
            emptyMessage="No workload data available"
          />
          {teamData?.workload.pagination && (
            <div className="flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} to{" "}
                {Math.min(page * pageSize, teamData.workload.pagination.total)} of{" "}
                {teamData.workload.pagination.total} contributors
              </div>
              <PaginationControls
                currentPage={page}
                totalPages={Math.max(1, teamData.workload.pagination.total_pages)}
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

      {/* Review Efficiency */}
      <CollapsibleSection
        title="Review Efficiency"
        actions={
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Label
                htmlFor="min-reviews"
                className="text-sm text-muted-foreground whitespace-nowrap"
              >
                Min Reviews:
              </Label>
              <Input
                id="min-reviews"
                type="number"
                min={1}
                max={MAX_MIN_REVIEWS}
                step={1}
                value={minReviews}
                onChange={(e) => {
                  setMinReviews(
                    Math.min(MAX_MIN_REVIEWS, Math.max(1, Number(e.target.value) || 1))
                  );
                  setPage(1);
                }}
                className="w-20 h-8"
              />
            </div>
            <DownloadButtons data={reviewData} filename="review-efficiency" />
          </div>
        }
      >
        <div className="space-y-4">
          <KPICards items={reviewKPIs} isLoading={isLoading} columns={4} />
          <DataTable
            columns={reviewColumns}
            data={reviewData}
            isLoading={isLoading}
            keyExtractor={(item) => item.user}
            emptyMessage="No review efficiency data available"
          />
          {teamData?.review_efficiency.pagination && (
            <div className="flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} to{" "}
                {Math.min(page * pageSize, teamData.review_efficiency.pagination.total)} of{" "}
                {teamData.review_efficiency.pagination.total} reviewers
              </div>
              <PaginationControls
                currentPage={page}
                totalPages={Math.max(1, teamData.review_efficiency.pagination.total_pages)}
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

      {/* Approval Bottlenecks */}
      <CollapsibleSection
        title="Approval Bottlenecks"
        actions={<DownloadButtons data={bottleneckData} filename="approval-bottlenecks" />}
      >
        <div className="space-y-4">
          {/* Bottleneck Alerts */}
          {bottleneckAlerts.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Active Alerts</h4>
              <div className="grid gap-2">
                {bottleneckAlerts.map((alert) => (
                  <div
                    key={alert.approver}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <div className="flex items-center gap-3">
                      <Badge variant={alert.severity === "critical" ? "destructive" : "secondary"}>
                        {alert.severity}
                      </Badge>
                      <span className="font-medium">{alert.approver}</span>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {formatHours(alert.avg_approval_hours)} avg approval time,{" "}
                      {alert.team_pending_count} pending
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <DataTable
            columns={bottleneckColumns}
            data={bottleneckData}
            isLoading={isLoading}
            keyExtractor={(item) => item.approver}
            emptyMessage="No bottleneck data available"
          />
          {teamData?.bottlenecks.pagination && (
            <div className="flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} to{" "}
                {Math.min(page * pageSize, teamData.bottlenecks.pagination.total)} of{" "}
                {teamData.bottlenecks.pagination.total} approvers
              </div>
              <PaginationControls
                currentPage={page}
                totalPages={Math.max(1, teamData.bottlenecks.pagination.total_pages)}
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

      {/* Cross-Team Collaboration */}
      <CollapsibleSection
        title="Cross-Team Collaboration"
        actions={
          <DownloadButtons data={crossTeamReviewsData} filename="cross-team-collaboration" />
        }
      >
        <div className="space-y-4">
          <KPICards items={crossTeamKPIs} isLoading={isCrossTeamLoading} columns={3} />
          <DataTable
            columns={crossTeamColumns}
            data={crossTeamReviewsData}
            isLoading={isCrossTeamLoading}
            keyExtractor={(item) =>
              `${item.repository}-${String(item.pr_number)}-${item.reviewer}-${item.created_at}`
            }
            emptyMessage="No cross-team review data available"
          />
          {crossTeamData?.pagination && (
            <div className="flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(crossTeamPage - 1) * crossTeamPageSize + 1} to{" "}
                {Math.min(crossTeamPage * crossTeamPageSize, crossTeamData.pagination.total)} of{" "}
                {crossTeamData.pagination.total} cross-team reviews
              </div>
              <PaginationControls
                currentPage={crossTeamPage}
                totalPages={Math.max(1, crossTeamData.pagination.total_pages)}
                pageSize={crossTeamPageSize}
                onPageChange={setCrossTeamPage}
                onPageSizeChange={(size: number) => {
                  setCrossTeamPageSize(size);
                  setCrossTeamPage(1); // Reset to first page
                }}
              />
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* User PRs Modal */}
      <UserPRsModal
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        username={selectedUser}
        category={selectedCategory}
      />

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
