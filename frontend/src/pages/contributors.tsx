import { useState } from "react";
import { useFilters } from "@/hooks/use-filters";
import { useContributors, useTurnaround, useExcludeUsers } from "@/hooks/use-api";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { DataTable, type ColumnDef } from "@/components/shared/data-table";
import { KPICards, type KPIItem } from "@/components/shared/kpi-cards";
import { DownloadButtons } from "@/components/shared/download-buttons";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { UserPRsModal } from "@/components/user-prs";
import type { PRCreator, PRReviewer, PRApprover, PRLgtm } from "@/types/contributors";
import type { TurnaroundByRepository, TurnaroundByReviewer } from "@/types/metrics";
import { formatHours } from "@/utils/time-format";

export function ContributorsPage(): React.ReactElement {
  const { filters } = useFilters();
  // Single page state for all sections since API returns all contributor types in one call
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);

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

  // Combine exclude_users with maintainers if excludeMaintainers is enabled
  const { users: effectiveExcludeUsers, isLoading: isExcludeUsersLoading } = useExcludeUsers(
    filters.excludeUsers,
    filters.excludeMaintainers
  );

  // Fetch turnaround metrics for KPIs
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

  // Fetch contributor data with server-side pagination
  // Note: The API returns all contributor types in one response with the same pagination params
  const { data: contributorMetrics, isLoading: contributorDataLoading } = useContributors(
    filters.timeRange,
    {
      repositories: filters.repositories,
      users: filters.users,
      exclude_users: effectiveExcludeUsers,
    },
    page,
    pageSize,
    !isExcludeUsersLoading
  );

  // Combine loading states
  const isLoading = contributorDataLoading || isExcludeUsersLoading;

  // Server-side paginated data for each section
  const creatorsData = contributorMetrics?.pr_creators.data ?? [];
  const creatorsPagination = contributorMetrics?.pr_creators.pagination;

  const reviewersData = contributorMetrics?.pr_reviewers.data ?? [];
  const reviewersPagination = contributorMetrics?.pr_reviewers.pagination;

  const approversData = contributorMetrics?.pr_approvers.data ?? [];
  const approversPagination = contributorMetrics?.pr_approvers.pagination;

  const lgtmData = contributorMetrics?.pr_lgtm.data ?? [];
  const lgtmPagination = contributorMetrics?.pr_lgtm.pagination;

  // Build KPI items from turnaround metrics
  const kpiItems: readonly KPIItem[] = turnaround?.summary
    ? [
        {
          label: "Avg Time to First Review",
          value: formatHours(turnaround.summary.avg_time_to_first_review_hours),
          tooltip:
            "Average hours from PR opened to first review. Calculated from pull_request_review webhook events, excluding self-reviews.",
        },
        {
          label: "Avg Time to Approval",
          value: formatHours(turnaround.summary.avg_time_to_approval_hours),
          tooltip:
            "Average hours from PR opened to first approved-* label. Calculated from pull_request labeled webhook events.",
        },
        {
          label: "Avg PR Lifecycle",
          value: formatHours(turnaround.summary.avg_pr_lifecycle_hours),
          tooltip:
            "Average hours from PR opened to closed/merged. Only includes completed PRs. Calculated from pull_request closed webhook events.",
        },
        {
          label: "PRs Analyzed",
          value: turnaround.summary.total_prs_analyzed,
          tooltip:
            "Total PRs opened in the selected time range. Counted from pull_request opened webhook events.",
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
      tooltip: "Average hours from PR opened to first review",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_time_to_first_review_hours),
      getValue: (item) => item.avg_time_to_first_review_hours,
    },
    {
      key: "avg_time_to_approval_hours",
      label: "Approval",
      tooltip: "Average hours from PR opened to first approved-* label",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_time_to_approval_hours),
      getValue: (item) => item.avg_time_to_approval_hours,
    },
    {
      key: "avg_pr_lifecycle_hours",
      label: "Lifecycle",
      tooltip: "Average hours from PR opened to closed/merged (completed PRs only)",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_pr_lifecycle_hours),
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

  // Column definitions for Response Time by Reviewer
  const turnaroundByReviewerColumns: readonly ColumnDef<TurnaroundByReviewer>[] = [
    { key: "reviewer", label: "Reviewer", sortable: true },
    {
      key: "avg_response_time_hours",
      label: "Avg Response",
      tooltip: "Average hours from PR opened to review by this user",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_response_time_hours),
      getValue: (item) => item.avg_response_time_hours,
    },
    {
      key: "total_reviews",
      label: "Reviews",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_reviews,
    },
    {
      key: "repositories_reviewed",
      label: "Repositories",
      sortable: false,
      render: (item) => item.repositories_reviewed.join(", "),
    },
  ];

  // Column definitions for PR Creators
  const creatorsColumns: readonly ColumnDef<PRCreator>[] = [
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
      key: "total_prs",
      label: "Total PRs",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_prs,
    },
    {
      key: "merged_prs",
      label: "Merged",
      align: "right",
      sortable: true,
      getValue: (item) => item.merged_prs,
    },
    {
      key: "closed_prs",
      label: "Closed",
      tooltip: "PRs closed without merge",
      align: "right",
      sortable: true,
      getValue: (item) => item.closed_prs,
    },
    {
      key: "avg_commits_per_pr",
      label: "Avg Commits",
      align: "right",
      sortable: true,
      render: (item) =>
        typeof item.avg_commits_per_pr === "number" ? item.avg_commits_per_pr.toFixed(1) : "N/A",
      getValue: (item) => item.avg_commits_per_pr,
    },
  ];

  // Column definitions for PR Reviewers
  const reviewersColumns: readonly ColumnDef<PRReviewer>[] = [
    {
      key: "user",
      label: "User",
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
      key: "total_reviews",
      label: "Reviews",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_reviews,
    },
    {
      key: "prs_reviewed",
      label: "PRs Reviewed",
      align: "right",
      sortable: true,
      getValue: (item) => item.prs_reviewed,
    },
    {
      key: "avg_reviews_per_pr",
      label: "Avg per PR",
      tooltip: "Average reviews per PR (re-reviews count)",
      align: "right",
      sortable: true,
      render: (item) =>
        typeof item.avg_reviews_per_pr === "number" ? item.avg_reviews_per_pr.toFixed(1) : "N/A",
      getValue: (item) => item.avg_reviews_per_pr,
    },
    {
      key: "cross_team_reviews",
      label: "Cross-Team",
      tooltip: "Reviews on PRs from different sig team",
      align: "right",
      sortable: true,
      getValue: (item) => item.cross_team_reviews,
    },
  ];

  // Column definitions for PR Approvers
  const approversColumns: readonly ColumnDef<PRApprover>[] = [
    {
      key: "user",
      label: "User",
      sortable: true,
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleUserClick(item.user, "pr_approvers");
          }}
          className="text-primary hover:underline cursor-pointer font-medium"
        >
          {item.user}
        </button>
      ),
    },
    {
      key: "total_approvals",
      label: "Approvals",
      tooltip: "Total /approve commands issued",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_approvals,
    },
    {
      key: "prs_approved",
      label: "PRs Approved",
      align: "right",
      sortable: true,
      getValue: (item) => item.prs_approved,
    },
  ];

  // Column definitions for PR LGTM
  const lgtmColumns: readonly ColumnDef<PRLgtm>[] = [
    {
      key: "user",
      label: "User",
      sortable: true,
      render: (item) => (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleUserClick(item.user, "pr_lgtm");
          }}
          className="text-primary hover:underline cursor-pointer font-medium"
        >
          {item.user}
        </button>
      ),
    },
    {
      key: "total_lgtm",
      label: "LGTMs",
      tooltip: "Total /lgtm commands issued",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_lgtm,
    },
    {
      key: "prs_lgtm",
      label: "PRs LGTM'd",
      align: "right",
      sortable: true,
      getValue: (item) => item.prs_lgtm,
    },
  ];

  return (
    <div className="space-y-6">
      {/* Turnaround Metrics KPIs */}
      <KPICards items={kpiItems} isLoading={turnaroundLoading} columns={4} />

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

      {/* Response Time by Reviewer */}
      <CollapsibleSection
        title="Response Time by Reviewer"
        actions={
          <DownloadButtons
            data={turnaround?.by_reviewer ?? []}
            filename="response-time-by-reviewer"
          />
        }
      >
        <DataTable
          columns={turnaroundByReviewerColumns}
          data={turnaround?.by_reviewer ?? []}
          isLoading={turnaroundLoading}
          keyExtractor={(item) => item.reviewer}
          emptyMessage="No response time data by reviewer found"
        />
      </CollapsibleSection>

      {/* PR Creators */}
      <CollapsibleSection
        title="PR Creators"
        actions={<DownloadButtons data={creatorsData} filename="pr-creators" />}
      >
        <DataTable
          columns={creatorsColumns}
          data={creatorsData}
          isLoading={isLoading}
          keyExtractor={(item) => item.user}
          emptyMessage="No PR creators found"
        />
        {creatorsPagination && (
          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-muted-foreground">
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, creatorsPagination.total)} of {creatorsPagination.total}{" "}
              creators
            </div>
            <PaginationControls
              currentPage={page}
              totalPages={Math.max(1, creatorsPagination.total_pages)}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={(size: number) => {
                setPageSize(size);
                setPage(1); // Reset to first page
              }}
            />
          </div>
        )}
      </CollapsibleSection>

      {/* PR Reviewers */}
      <CollapsibleSection
        title="PR Reviewers"
        actions={<DownloadButtons data={reviewersData} filename="pr-reviewers" />}
      >
        <DataTable
          columns={reviewersColumns}
          data={reviewersData}
          isLoading={isLoading}
          keyExtractor={(item) => item.user}
          emptyMessage="No reviewers found"
        />
        {reviewersPagination && (
          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-muted-foreground">
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, reviewersPagination.total)} of {reviewersPagination.total}{" "}
              reviewers
            </div>
            <PaginationControls
              currentPage={page}
              totalPages={Math.max(1, reviewersPagination.total_pages)}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={(size: number) => {
                setPageSize(size);
                setPage(1); // Reset to first page
              }}
            />
          </div>
        )}
      </CollapsibleSection>

      {/* PR Approvers */}
      <CollapsibleSection
        title="PR Approvers"
        actions={<DownloadButtons data={approversData} filename="pr-approvers" />}
      >
        <DataTable
          columns={approversColumns}
          data={approversData}
          isLoading={isLoading}
          keyExtractor={(item) => item.user}
          emptyMessage="No approvers found"
        />
        {approversPagination && (
          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-muted-foreground">
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, approversPagination.total)} of {approversPagination.total}{" "}
              approvers
            </div>
            <PaginationControls
              currentPage={page}
              totalPages={Math.max(1, approversPagination.total_pages)}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={(size: number) => {
                setPageSize(size);
                setPage(1); // Reset to first page
              }}
            />
          </div>
        )}
      </CollapsibleSection>

      {/* PR LGTM */}
      <CollapsibleSection
        title="PR LGTM"
        actions={<DownloadButtons data={lgtmData} filename="pr-lgtm" />}
      >
        <DataTable
          columns={lgtmColumns}
          data={lgtmData}
          isLoading={isLoading}
          keyExtractor={(item) => item.user}
          emptyMessage="No LGTM data found"
        />
        {lgtmPagination && (
          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-muted-foreground">
              Showing {(page - 1) * pageSize + 1} to{" "}
              {Math.min(page * pageSize, lgtmPagination.total)} of {lgtmPagination.total} entries
            </div>
            <PaginationControls
              currentPage={page}
              totalPages={Math.max(1, lgtmPagination.total_pages)}
              pageSize={pageSize}
              onPageChange={setPage}
              onPageSizeChange={(size: number) => {
                setPageSize(size);
                setPage(1); // Reset to first page
              }}
            />
          </div>
        )}
      </CollapsibleSection>

      {/* User PRs Modal */}
      <UserPRsModal
        open={isModalOpen}
        onOpenChange={setIsModalOpen}
        username={selectedUser}
        category={selectedCategory}
      />
    </div>
  );
}
