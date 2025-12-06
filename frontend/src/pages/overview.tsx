import { useState, useMemo, useEffect } from "react";
import { useFilters } from "@/hooks/use-filters";
import { useRepositories, useWebhooks, useUserPRs, usePRStory } from "@/hooks/use-api";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { DataTable, type ColumnDef } from "@/components/shared/data-table";
import { DownloadButtons } from "@/components/shared/download-buttons";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PRStoryModal } from "@/components/pr-story";
import { History } from "lucide-react";
import type { Repository } from "@/types/repositories";
import type { WebhookEvent } from "@/types/webhooks";
import type { UserPR } from "@/types/user-prs";

export function OverviewPage(): React.ReactElement {
  const { filters } = useFilters();
  const [reposPage, setReposPage] = useState(1);
  const [reposPageSize, setReposPageSize] = useState(25);
  const [webhookPage, setWebhookPage] = useState(1);
  const [webhookPageSize, setWebhookPageSize] = useState(10);
  const [prPage, setPrPage] = useState(1);
  const [prPageSize, setPrPageSize] = useState(25);

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

  // Load collapse state from localStorage
  const getStoredState = (key: string, defaultValue: boolean): boolean => {
    if (typeof window === "undefined") {
      return defaultValue;
    }
    const stored = localStorage.getItem(key);
    return stored !== null ? stored === "true" : defaultValue;
  };

  // Separate collapse state for each section
  const [reposExpanded, setReposExpanded] = useState(() =>
    getStoredState("section-top-repositories-collapsed", true)
  );
  const [eventsExpanded, setEventsExpanded] = useState(() =>
    getStoredState("section-recent-events-collapsed", true)
  );
  const [prsExpanded, setPrsExpanded] = useState(() =>
    getStoredState("section-pull-requests-collapsed", true)
  );

  // Persist collapse state to localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("section-top-repositories-collapsed", String(reposExpanded));
    }
  }, [reposExpanded]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("section-recent-events-collapsed", String(eventsExpanded));
    }
  }, [eventsExpanded]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("section-pull-requests-collapsed", String(prsExpanded));
    }
  }, [prsExpanded]);

  // Fetch data
  const { data: repositoriesData, isLoading: reposLoading } = useRepositories(
    filters.timeRange,
    {
      repositories: filters.repositories,
      users: filters.users,
      exclude_users: filters.excludeUsers,
    },
    reposPage,
    reposPageSize
  );

  const { data: webhookData, isLoading: webhooksLoading } = useWebhooks({
    ...(filters.timeRange.start_time && { start_time: filters.timeRange.start_time }),
    ...(filters.timeRange.end_time && { end_time: filters.timeRange.end_time }),
    page: webhookPage,
    page_size: webhookPageSize,
    // Note: Webhooks API uses singular 'repository' and doesn't support user filtering
    ...(filters.repositories.length === 1 ? { repository: filters.repositories[0] } : {}),
  });

  const { data: userPRsData, isLoading: prsLoading } = useUserPRs({
    ...(filters.timeRange.start_time && { start_time: filters.timeRange.start_time }),
    ...(filters.timeRange.end_time && { end_time: filters.timeRange.end_time }),
    page: prPage,
    page_size: prPageSize,
    users: filters.users,
    exclude_users: filters.excludeUsers,
    repositories: filters.repositories,
  });

  // Calculate percentages for repositories
  const repositoriesWithPercentages = useMemo(() => {
    if (!repositoriesData?.repositories) {
      return [];
    }

    const total = repositoriesData.repositories.reduce((sum, repo) => sum + repo.total_events, 0);

    if (total === 0) {
      return repositoriesData.repositories;
    }

    return repositoriesData.repositories.map((repo) => ({
      ...repo,
      percentage: (repo.total_events / total) * 100,
    }));
  }, [repositoriesData]);

  // Column definitions for repositories
  const repoColumns: readonly ColumnDef<Repository>[] = [
    {
      key: "repository",
      label: "Repository",
      sortable: true,
      render: (item) => (
        <a
          href={`https://github.com/${item.repository}`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          {item.repository}
        </a>
      ),
    },
    {
      key: "total_events",
      label: "Events",
      align: "right",
      sortable: true,
      getValue: (item) => item.total_events,
    },
    {
      key: "percentage",
      label: "%",
      align: "right",
      sortable: true,
      render: (item) => (item.percentage !== null ? `${item.percentage.toFixed(1)}%` : "N/A"),
      getValue: (item) => item.percentage ?? 0,
    },
  ];

  // Column definitions for webhooks
  const webhookColumns: readonly ColumnDef<WebhookEvent>[] = [
    {
      key: "created_at",
      label: "Time",
      sortable: true,
      render: (item) => new Date(item.created_at).toLocaleString(),
    },
    {
      key: "repository",
      label: "Repository",
      sortable: true,
    },
    {
      key: "event_type",
      label: "Event",
      sortable: true,
    },
    {
      key: "status",
      label: "Status",
      align: "center",
      sortable: true,
      render: (item) => (
        <Badge
          variant={item.status === "success" ? "default" : "destructive"}
          className={`min-w-[70px] justify-center ${item.status === "success" ? "bg-green-600 hover:bg-green-700" : ""}`}
        >
          {item.status}
        </Badge>
      ),
    },
  ];

  // Column definitions for PRs
  const prColumns: readonly ColumnDef<UserPR>[] = [
    {
      key: "number",
      label: "PR #",
      sortable: true,
      render: (item) => (
        <a
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary hover:underline"
        >
          #{item.number}
        </a>
      ),
      getValue: (item) => item.number,
    },
    {
      key: "title",
      label: "Title",
      sortable: true,
    },
    {
      key: "owner",
      label: "Owner",
      sortable: true,
    },
    {
      key: "repository",
      label: "Repository",
      sortable: true,
    },
    {
      key: "state",
      label: "State",
      align: "center",
      sortable: true,
      render: (item) => {
        const variant = item.merged
          ? "default"
          : item.state === "open"
            ? "secondary"
            : "destructive";
        const text = item.merged ? "merged" : item.state;
        const className = item.merged ? "bg-green-600 hover:bg-green-700" : "";
        return (
          <Badge variant={variant} className={`min-w-[70px] justify-center ${className}`}>
            {text}
          </Badge>
        );
      },
    },
    {
      key: "created_at",
      label: "Created",
      sortable: true,
      render: (item) => new Date(item.created_at).toLocaleDateString(),
    },
    {
      key: "updated_at",
      label: "Updated",
      sortable: true,
      render: (item) => new Date(item.updated_at).toLocaleDateString(),
    },
    {
      key: "commits_count",
      label: "Commits",
      align: "right",
      sortable: true,
      getValue: (item) => item.commits_count,
    },
    {
      key: "actions",
      label: "Timeline",
      align: "center",
      sortable: false,
      render: (item) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            handleOpenPRStory(item.repository, item.number);
          }}
          aria-label={`View PR story for PR #${String(item.number)}`}
        >
          <History className="h-4 w-4" />
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Two-column grid for Top Repositories and Recent Events */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
        {/* Top Repositories */}
        <CollapsibleSection
          key="top-repositories"
          title="Top Repositories"
          isExpanded={reposExpanded}
          onToggle={() => {
            setReposExpanded(!reposExpanded);
          }}
          actions={<DownloadButtons data={repositoriesWithPercentages} filename="repositories" />}
        >
          <DataTable
            columns={repoColumns}
            data={repositoriesWithPercentages}
            isLoading={reposLoading}
            keyExtractor={(item) => item.repository}
            emptyMessage="No repositories found"
          />
          {repositoriesData && (
            <div className="mt-4 flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(reposPage - 1) * reposPageSize + 1} to{" "}
                {Math.min(reposPage * reposPageSize, repositoriesData.pagination.total)} of{" "}
                {repositoriesData.pagination.total} repositories
              </div>
              <PaginationControls
                currentPage={reposPage}
                totalPages={Math.max(1, repositoriesData.pagination.total_pages)}
                pageSize={reposPageSize}
                onPageChange={setReposPage}
                onPageSizeChange={(size: number) => {
                  setReposPageSize(size);
                  setReposPage(1); // Reset to first page
                }}
              />
            </div>
          )}
        </CollapsibleSection>

        {/* Recent Events */}
        <CollapsibleSection
          key="recent-events"
          title="Recent Events"
          isExpanded={eventsExpanded}
          onToggle={() => {
            setEventsExpanded(!eventsExpanded);
          }}
          actions={<DownloadButtons data={webhookData?.data ?? []} filename="webhook-events" />}
        >
          <DataTable
            columns={webhookColumns}
            data={webhookData?.data}
            isLoading={webhooksLoading}
            keyExtractor={(item) => item.delivery_id}
            emptyMessage="No webhook events found"
          />
          {webhookData && (
            <div className="mt-4 flex justify-between items-center">
              <div className="text-sm text-muted-foreground">
                Showing {(webhookPage - 1) * webhookPageSize + 1} to{" "}
                {Math.min(webhookPage * webhookPageSize, webhookData.pagination.total)} of{" "}
                {webhookData.pagination.total} events
              </div>
              <PaginationControls
                currentPage={webhookPage}
                totalPages={Math.max(1, webhookData.pagination.total_pages)}
                pageSize={webhookPageSize}
                onPageChange={setWebhookPage}
                onPageSizeChange={(size: number) => {
                  setWebhookPageSize(size);
                  setWebhookPage(1); // Reset to first page
                }}
              />
            </div>
          )}
        </CollapsibleSection>
      </div>

      {/* Pull Requests */}
      <CollapsibleSection
        key="pull-requests"
        title="Pull Requests"
        isExpanded={prsExpanded}
        onToggle={() => {
          setPrsExpanded(!prsExpanded);
        }}
        actions={<DownloadButtons data={userPRsData?.data ?? []} filename="pull-requests" />}
      >
        <DataTable
          columns={prColumns}
          data={userPRsData?.data}
          isLoading={prsLoading}
          keyExtractor={(item) => `${item.repository}-${item.number.toString()}`}
          emptyMessage="No pull requests found"
        />
        {userPRsData && (
          <div className="mt-4 flex justify-between items-center">
            <div className="text-sm text-muted-foreground">
              Showing {(prPage - 1) * prPageSize + 1} to{" "}
              {Math.min(prPage * prPageSize, userPRsData.pagination.total)} of{" "}
              {userPRsData.pagination.total} pull requests
            </div>
            <PaginationControls
              currentPage={prPage}
              totalPages={Math.max(1, userPRsData.pagination.total_pages)}
              pageSize={prPageSize}
              onPageChange={setPrPage}
              onPageSizeChange={(size: number) => {
                setPrPageSize(size);
                setPrPage(1); // Reset to first page
              }}
            />
          </div>
        )}
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
