import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import type { MetricsSummary, TrendDataPoint, TurnaroundMetrics } from "@/types/metrics";
import type { WebhookEvent } from "@/types/webhooks";
import type { ContributorMetrics } from "@/types/contributors";
import type { RepositoriesResponse } from "@/types/repositories";
import type { PaginatedResponse, TimeRange } from "@/types/api";
import type { UserPRsResponse } from "@/types/user-prs";
import type { TeamDynamicsResponse } from "@/types/team-dynamics";
import type { PRStory } from "@/types/pr-story";
import type { CrossTeamData } from "@/types/cross-team";
import type { MaintainersResponse } from "@/types/maintainers";

const API_BASE = "/api/metrics";

type QueryParamValue = string | number | boolean | undefined;

async function fetchApi<T>(
  endpoint: string,
  params?: Record<string, QueryParamValue> | URLSearchParams
): Promise<T> {
  const url = new URL(`${API_BASE}${endpoint}`, window.location.origin);

  if (params instanceof URLSearchParams) {
    // Use URLSearchParams directly for proper array serialization
    url.search = params.toString();
  } else if (params) {
    // Legacy record-based params
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        const stringValue =
          typeof value === "number" || typeof value === "boolean" ? String(value) : value;
        url.searchParams.set(key, stringValue);
      }
    });
  }

  const response = await fetch(url.toString());

  if (!response.ok) {
    const statusCode = String(response.status);
    let errorMessage = `API error: ${statusCode}`;
    try {
      const errorBody = (await response.json()) as { detail?: string };
      if (errorBody.detail) {
        errorMessage = errorBody.detail;
      }
    } catch {
      // Ignore JSON parse errors, use default message
    }
    throw new Error(errorMessage);
  }

  return response.json() as Promise<T>;
}

// Query keys factory
export const queryKeys = {
  summary: (
    timeRange?: TimeRange,
    repositories?: readonly string[],
    users?: readonly string[],
    excludeUsers?: readonly string[]
  ) => ["metrics", "summary", timeRange, repositories, users, excludeUsers] as const,
  webhooks: (params?: WebhookParams) =>
    [
      "metrics",
      "webhooks",
      params?.start_time ?? null,
      params?.end_time ?? null,
      params?.page ?? null,
      params?.page_size ?? null,
      params?.repository ?? null,
      params?.event_type ?? null,
    ] as const,
  repositories: (
    timeRange?: TimeRange,
    repositories?: readonly string[],
    users?: readonly string[],
    excludeUsers?: readonly string[],
    page?: number,
    pageSize?: number
  ) =>
    [
      "metrics",
      "repositories",
      timeRange,
      repositories,
      users,
      excludeUsers,
      page,
      pageSize,
    ] as const,
  contributors: (
    timeRange?: TimeRange,
    repositories?: readonly string[],
    users?: readonly string[],
    excludeUsers?: readonly string[],
    page?: number,
    pageSize?: number
  ) =>
    [
      "metrics",
      "contributors",
      timeRange,
      repositories,
      users,
      excludeUsers,
      page,
      pageSize,
    ] as const,
  trends: (timeRange?: TimeRange, bucket?: string) =>
    ["metrics", "trends", timeRange, bucket] as const,
  turnaround: (
    timeRange?: TimeRange,
    repositories?: readonly string[],
    users?: readonly string[],
    excludeUsers?: readonly string[]
  ) => ["metrics", "turnaround", timeRange, repositories, users, excludeUsers] as const,
  userPrs: (params?: UserPRParams) =>
    [
      "metrics",
      "user-prs",
      params?.start_time ?? null,
      params?.end_time ?? null,
      params?.page ?? null,
      params?.page_size ?? null,
      params?.role ?? null,
      params?.repositories ?? null,
      params?.users ?? null,
      params?.exclude_users ?? null,
    ] as const,
  teamDynamics: (
    timeRange?: TimeRange,
    repositories?: readonly string[],
    users?: readonly string[],
    excludeUsers?: readonly string[],
    page?: number,
    pageSize?: number
  ) =>
    [
      "metrics",
      "team-dynamics",
      timeRange,
      repositories,
      users,
      excludeUsers,
      page,
      pageSize,
    ] as const,
  prStory: (repository: string, prNumber: number) =>
    ["metrics", "pr-story", repository, prNumber] as const,
  crossTeamReviews: (
    timeRange?: TimeRange,
    repositories?: readonly string[],
    users?: readonly string[],
    excludeUsers?: readonly string[],
    page?: number,
    pageSize?: number
  ) =>
    [
      "metrics",
      "cross-team-reviews",
      timeRange,
      repositories,
      users,
      excludeUsers,
      page,
      pageSize,
    ] as const,
  maintainers: () => ["metrics", "maintainers"] as const,
};

interface WebhookParams {
  readonly start_time?: string;
  readonly end_time?: string;
  readonly page?: number;
  readonly page_size?: number;
  readonly repository?: string;
  readonly event_type?: string;
}

interface UserPRParams {
  readonly start_time?: string;
  readonly end_time?: string;
  readonly page?: number;
  readonly page_size?: number;
  readonly users?: readonly string[];
  readonly exclude_users?: readonly string[];
  readonly repositories?: readonly string[];
  readonly role?: string;
}

interface FilterParams {
  readonly repositories?: readonly string[];
  readonly users?: readonly string[];
  readonly exclude_users?: readonly string[];
}

// Helper to append array values to URLSearchParams
function appendArrayParam(params: URLSearchParams, key: string, values?: readonly string[]): void {
  if (values && values.length > 0) {
    values.forEach((value) => {
      params.append(key, value);
    });
  }
}

// Helper to build filter params with proper array serialization
function buildFilterParams(timeRange?: TimeRange, filters?: FilterParams): URLSearchParams {
  const params = new URLSearchParams();

  if (timeRange?.start_time) params.set("start_time", timeRange.start_time);
  if (timeRange?.end_time) params.set("end_time", timeRange.end_time);

  // Only add array filters if they have actual values (length > 0)
  appendArrayParam(params, "repositories", filters?.repositories);
  appendArrayParam(params, "users", filters?.users);
  appendArrayParam(params, "exclude_users", filters?.exclude_users);

  return params;
}

// Hooks
export function useSummary(timeRange?: TimeRange, filters?: FilterParams, enabled: boolean = true) {
  return useQuery<MetricsSummary>({
    queryKey: queryKeys.summary(
      timeRange,
      filters?.repositories,
      filters?.users,
      filters?.exclude_users
    ),
    queryFn: () => fetchApi<MetricsSummary>("/summary", buildFilterParams(timeRange, filters)),
    enabled,
  });
}

export function useWebhooks(params?: WebhookParams) {
  // Build URLSearchParams with proper type safety
  const urlParams = new URLSearchParams();

  if (params?.start_time) urlParams.set("start_time", params.start_time);
  if (params?.end_time) urlParams.set("end_time", params.end_time);
  if (params?.page) urlParams.set("page", String(params.page));
  if (params?.page_size) urlParams.set("page_size", String(params.page_size));
  if (params?.repository) urlParams.set("repository", params.repository);
  if (params?.event_type) urlParams.set("event_type", params.event_type);

  return useQuery<PaginatedResponse<WebhookEvent>>({
    queryKey: queryKeys.webhooks(params),
    queryFn: () => fetchApi<PaginatedResponse<WebhookEvent>>("/webhooks", urlParams),
  });
}

export function useRepositories(
  timeRange?: TimeRange,
  filters?: FilterParams,
  page: number = 1,
  pageSize: number = 10,
  enabled: boolean = true
) {
  const params = buildFilterParams(timeRange, filters);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));

  return useQuery<RepositoriesResponse>({
    queryKey: queryKeys.repositories(
      timeRange,
      filters?.repositories,
      filters?.users,
      filters?.exclude_users,
      page,
      pageSize
    ),
    queryFn: () => fetchApi<RepositoriesResponse>("/repositories", params),
    enabled,
  });
}

export function useContributors(
  timeRange?: TimeRange,
  filters?: FilterParams,
  page: number = 1,
  pageSize: number = 10,
  enabled: boolean = true
) {
  const params = buildFilterParams(timeRange, filters);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));

  return useQuery<ContributorMetrics>({
    queryKey: queryKeys.contributors(
      timeRange,
      filters?.repositories,
      filters?.users,
      filters?.exclude_users,
      page,
      pageSize
    ),
    queryFn: () => fetchApi<ContributorMetrics>("/contributors", params),
    enabled,
  });
}

export function useTrends(timeRange?: TimeRange, bucket: string = "hour") {
  const params = buildFilterParams(timeRange);
  params.set("bucket", bucket);

  return useQuery<readonly TrendDataPoint[]>({
    queryKey: queryKeys.trends(timeRange, bucket),
    queryFn: () => fetchApi<readonly TrendDataPoint[]>("/trends", params),
  });
}

export function useTurnaround(
  timeRange?: TimeRange,
  filters?: FilterParams,
  enabled: boolean = true
) {
  return useQuery<TurnaroundMetrics>({
    queryKey: queryKeys.turnaround(
      timeRange,
      filters?.repositories,
      filters?.users,
      filters?.exclude_users
    ),
    queryFn: () =>
      fetchApi<TurnaroundMetrics>("/turnaround", buildFilterParams(timeRange, filters)),
    enabled,
  });
}

export function useUserPRs(params?: UserPRParams, enabled: boolean = true) {
  // Build URLSearchParams with proper array serialization
  const urlParams = new URLSearchParams();

  if (params?.start_time) urlParams.set("start_time", params.start_time);
  if (params?.end_time) urlParams.set("end_time", params.end_time);
  if (params?.page) urlParams.set("page", String(params.page));
  if (params?.page_size) urlParams.set("page_size", String(params.page_size));
  if (params?.role) urlParams.set("role", params.role);

  // Handle array params - use helper function
  appendArrayParam(urlParams, "repositories", params?.repositories);
  appendArrayParam(urlParams, "users", params?.users);
  appendArrayParam(urlParams, "exclude_users", params?.exclude_users);

  return useQuery<UserPRsResponse>({
    queryKey: queryKeys.userPrs(params),
    queryFn: () => fetchApi<UserPRsResponse>("/user-prs", urlParams),
    enabled,
  });
}

export function useTeamDynamics(
  timeRange?: TimeRange,
  filters?: FilterParams,
  page: number = 1,
  pageSize: number = 25,
  enabled: boolean = true
) {
  const params = buildFilterParams(timeRange, filters);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));

  return useQuery<TeamDynamicsResponse>({
    queryKey: queryKeys.teamDynamics(
      timeRange,
      filters?.repositories,
      filters?.users,
      filters?.exclude_users,
      page,
      pageSize
    ),
    queryFn: () => fetchApi<TeamDynamicsResponse>("/team-dynamics", params),
    enabled,
  });
}

export function usePRStory(repository: string, prNumber: number, enabled: boolean = true) {
  return useQuery<PRStory>({
    queryKey: queryKeys.prStory(repository, prNumber),
    queryFn: () =>
      fetchApi<PRStory>(`/pr-story/${encodeURIComponent(repository)}/${String(prNumber)}`),
    enabled,
  });
}

export function useCrossTeamReviews(
  timeRange?: TimeRange,
  filters?: FilterParams,
  page: number = 1,
  pageSize: number = 25,
  enabled: boolean = true
) {
  const params = buildFilterParams(timeRange, filters);
  params.set("page", String(page));
  params.set("page_size", String(pageSize));

  return useQuery<CrossTeamData>({
    queryKey: queryKeys.crossTeamReviews(
      timeRange,
      filters?.repositories,
      filters?.users,
      filters?.exclude_users,
      page,
      pageSize
    ),
    queryFn: () => fetchApi<CrossTeamData>("/cross-team-reviews", params),
    enabled,
  });
}

export function useMaintainers() {
  return useQuery<MaintainersResponse>({
    queryKey: queryKeys.maintainers(),
    queryFn: () => fetchApi<MaintainersResponse>("/maintainers"),
    staleTime: 1000 * 60 * 5, // 5 minutes - maintainers don't change often
  });
}

/**
 * Helper hook to merge exclude_users with maintainers when excludeMaintainers is true.
 * This ensures that maintainers are filtered out from API results when requested.
 *
 * @param excludeUsers - The base list of users to exclude
 * @param excludeMaintainers - Whether to also exclude all maintainers
 * @returns Object with combined list of users to exclude (deduplicated) and loading state
 */
export function useExcludeUsers(
  excludeUsers: readonly string[],
  excludeMaintainers: boolean
): { readonly users: readonly string[]; readonly isLoading: boolean } {
  const { data: maintainersData, isLoading: isMaintainersLoading } = useMaintainers();

  const users = useMemo(() => {
    // If not excluding maintainers, just return the base exclude list
    if (!excludeMaintainers) {
      return excludeUsers;
    }

    // If excluding maintainers but data not loaded yet, return empty array
    // The isLoading flag will prevent dependent queries from firing
    if (!maintainersData) {
      return [];
    }

    // Merge and deduplicate
    const combined = new Set([...excludeUsers, ...maintainersData.all_maintainers]);
    return Array.from(combined);
  }, [excludeUsers, excludeMaintainers, maintainersData]);

  // Only show loading when we're trying to exclude maintainers but data isn't ready
  const isLoading = excludeMaintainers && isMaintainersLoading;

  return { users, isLoading };
}
