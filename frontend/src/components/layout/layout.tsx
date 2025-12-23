import { useMemo } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "./app-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import { SettingsTrigger } from "@/components/settings/settings-trigger";
import { FilterPanel } from "@/components/dashboard/filter-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Outlet } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useRepositories, useContributors, useSummary, useExcludeUsers } from "@/hooks/use-api";
import { useFilters } from "@/hooks/use-filters";

// Format trend indicator with arrow and percentage
function formatTrend(trend: number): { text: string; className: string } {
  if (trend > 0) {
    return {
      text: `↑ ${trend.toFixed(1)}% vs last period`,
      className: "text-green-600 dark:text-green-400",
    };
  } else if (trend < 0) {
    return {
      text: `↓ ${Math.abs(trend).toFixed(1)}% vs last period`,
      className: "text-red-600 dark:text-red-400",
    };
  }
  return {
    text: "→ 0.0% vs last period",
    className: "text-gray-600 dark:text-gray-400",
  };
}

export function Layout(): React.ReactElement {
  const queryClient = useQueryClient();
  const { filters } = useFilters();

  // Combine exclude_users with maintainers if excludeMaintainers is enabled
  const { users: effectiveExcludeUsers, isLoading: isExcludeUsersLoading } = useExcludeUsers(
    filters.excludeUsers,
    filters.excludeMaintainers
  );

  // Fetch summary data for the tooltip
  const { data: summaryData, isLoading: isSummaryDataLoading } = useSummary(filters.timeRange, {
    repositories: filters.repositories,
    users: filters.users,
    exclude_users: effectiveExcludeUsers,
  });

  // Combine loading states - show loading if either summary data or exclude users are loading
  const isSummaryLoading = isSummaryDataLoading || isExcludeUsersLoading;

  // Fetch repositories and contributors for filter suggestions
  // Use a large page size to get all available options
  // TODO: Consider server-side search with autocomplete for large datasets (>1000 repos/contributors)
  // Current approach works for moderate datasets but may need pagination for very large organizations
  const { data: reposData } = useRepositories(filters.timeRange, {}, 1, 1000);
  const { data: contributorsData } = useContributors(filters.timeRange, {}, 1, 1000);

  // Extract unique repository names from repositories data
  const repositoryOptions = useMemo(() => {
    if (!reposData?.repositories) return [];
    return reposData.repositories.map((r) => r.repository).sort();
  }, [reposData]);

  // Extract unique user names from all contributor categories
  const userOptions = useMemo(() => {
    if (!contributorsData) return [];
    const users = new Set<string>();

    contributorsData.pr_creators.data.forEach((c) => {
      users.add(c.user);
    });
    contributorsData.pr_reviewers.data.forEach((c) => {
      users.add(c.user);
    });
    contributorsData.pr_approvers.data.forEach((c) => {
      users.add(c.user);
    });
    contributorsData.pr_lgtm.data.forEach((c) => {
      users.add(c.user);
    });

    return Array.from(users).sort();
  }, [contributorsData]);

  const handleRefresh = (): void => {
    void queryClient.invalidateQueries();
  };

  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <header className="flex h-14 items-center justify-between border-b px-6">
          <div className="flex items-center gap-4">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge
                    variant="default"
                    className="bg-green-600 text-white hover:bg-green-700 cursor-help"
                  >
                    Ready
                  </Badge>
                </TooltipTrigger>
                <TooltipContent className="max-w-sm p-4">
                  {isSummaryLoading ? (
                    <p className="text-sm">Loading...</p>
                  ) : summaryData ? (
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between gap-4">
                        <span className="font-semibold">Total Events:</span>
                        <div className="flex flex-col items-end">
                          <span>{summaryData.summary.total_events.toLocaleString()}</span>
                          <span
                            className={
                              formatTrend(summaryData.summary.total_events_trend).className
                            }
                          >
                            {formatTrend(summaryData.summary.total_events_trend).text}
                          </span>
                        </div>
                      </div>
                      <div className="flex justify-between gap-4">
                        <span className="font-semibold">Success Rate:</span>
                        <div className="flex flex-col items-end">
                          <span>{summaryData.summary.success_rate.toFixed(1)}%</span>
                          <span
                            className={
                              formatTrend(summaryData.summary.success_rate_trend).className
                            }
                          >
                            {formatTrend(summaryData.summary.success_rate_trend).text}
                          </span>
                        </div>
                      </div>
                      <div className="flex justify-between gap-4">
                        <span className="font-semibold">Failed Events:</span>
                        <div className="flex flex-col items-end">
                          <span>{summaryData.summary.failed_events.toLocaleString()}</span>
                          <span
                            className={
                              formatTrend(summaryData.summary.failed_events_trend).className
                            }
                          >
                            {formatTrend(summaryData.summary.failed_events_trend).text}
                          </span>
                        </div>
                      </div>
                      <div className="flex justify-between gap-4">
                        <span className="font-semibold">Avg Duration:</span>
                        <div className="flex flex-col items-end">
                          <span>{summaryData.summary.avg_processing_time_ms.toFixed(0)}ms</span>
                          <span
                            className={
                              formatTrend(summaryData.summary.avg_duration_trend).className
                            }
                          >
                            {formatTrend(summaryData.summary.avg_duration_trend).text}
                          </span>
                        </div>
                      </div>
                      <p className="mt-3 text-xs italic text-muted-foreground border-t pt-2">
                        Trends compare current period stats with the previous equivalent period
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm">No data available</p>
                  )}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <h1 className="text-lg font-semibold">GitHub Metrics Dashboard</h1>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" asChild>
              <a
                href="https://github.com/myk-org/github-metrics"
                target="_blank"
                rel="noopener noreferrer"
                title="GitHub Repository"
              >
                <svg
                  viewBox="0 0 24 24"
                  className="h-5 w-5"
                  fill="currentColor"
                  xmlns="http://www.w3.org/2000/svg"
                  role="img"
                  aria-labelledby="github-icon-title"
                >
                  <title id="github-icon-title">GitHub</title>
                  <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
                </svg>
              </a>
            </Button>
            <SettingsTrigger />
            <ThemeToggle />
          </div>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <div className="mb-6">
            <FilterPanel
              repositorySuggestions={repositoryOptions}
              userSuggestions={userOptions}
              onRefresh={handleRefresh}
            />
          </div>
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
