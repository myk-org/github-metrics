import { useState } from "react";
import { useFilters } from "@/hooks/use-filters";
import { useTeamDynamics } from "@/hooks/use-api";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { DataTable, type ColumnDef } from "@/components/shared/data-table";
import { KPICards, type KPIItem } from "@/components/shared/kpi-cards";
import { DownloadButtons } from "@/components/shared/download-buttons";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { UserPRsModal } from "@/components/user-prs";
import { Badge } from "@/components/ui/badge";
import { formatHours } from "@/utils/time-format";
import type {
  WorkloadContributor,
  ReviewerEfficiency,
  ApprovalBottleneck,
  BottleneckAlert,
} from "@/types/team-dynamics";

export function TeamDynamicsPage(): React.ReactElement {
  const { filters } = useFilters();
  // Single page state for all sections since API returns all team dynamics data in one call
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

  // Fetch team dynamics data with server-side pagination
  const { data: teamData, isLoading } = useTeamDynamics(
    filters.timeRange,
    {
      repositories: filters.repositories,
      users: filters.users,
      exclude_users: filters.excludeUsers,
    },
    page,
    pageSize
  );

  // Server-side paginated data for each section
  const workloadData = teamData?.workload.by_contributor ?? [];
  const reviewData = teamData?.review_efficiency.by_reviewer ?? [];
  const bottleneckData = teamData?.bottlenecks.by_approver ?? [];

  // Workload Distribution KPIs
  const workloadKPIs: readonly KPIItem[] = teamData?.workload.summary
    ? [
        {
          label: "Total Contributors",
          value: teamData.workload.summary.total_contributors,
        },
        {
          label: "Avg PRs per Contributor",
          value:
            typeof teamData.workload.summary.avg_prs_per_contributor === "number"
              ? teamData.workload.summary.avg_prs_per_contributor.toFixed(1)
              : "-",
        },
        {
          label: "Top Contributor",
          value: teamData.workload.summary.top_contributor?.user ?? "N/A",
        },
        {
          label: "Workload Gini Coefficient",
          value:
            typeof teamData.workload.summary.workload_gini === "number"
              ? teamData.workload.summary.workload_gini.toFixed(2)
              : "-",
        },
      ]
    : [];

  // Review Efficiency KPIs
  const reviewKPIs: readonly KPIItem[] = teamData?.review_efficiency.summary
    ? [
        {
          label: "Avg Review Time",
          value: formatHours(teamData.review_efficiency.summary.avg_review_time_hours),
        },
        {
          label: "Median Review Time",
          value: formatHours(teamData.review_efficiency.summary.median_review_time_hours),
        },
        {
          label: "Fastest Reviewer",
          value: teamData.review_efficiency.summary.fastest_reviewer?.user ?? "N/A",
        },
        {
          label: "Slowest Reviewer",
          value: teamData.review_efficiency.summary.slowest_reviewer?.user ?? "N/A",
        },
      ]
    : [];

  // Bottleneck Alerts (for display at top of section)
  const bottleneckAlerts: readonly BottleneckAlert[] = teamData?.bottlenecks.alerts ?? [];

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
      label: "Avg Review Time",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_review_time_hours),
      getValue: (item) => item.avg_review_time_hours,
    },
    {
      key: "median_review_time_hours",
      label: "Median Review Time",
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.median_review_time_hours),
      getValue: (item) => item.median_review_time_hours,
    },
    {
      key: "total_reviews",
      label: "Total Reviews",
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
      align: "right",
      sortable: true,
      render: (item) => formatHours(item.avg_approval_hours),
      getValue: (item) => item.avg_approval_hours,
    },
    {
      key: "total_approvals",
      label: "Total Approvals",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_approvals,
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
        actions={<DownloadButtons data={reviewData} filename="review-efficiency" />}
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
