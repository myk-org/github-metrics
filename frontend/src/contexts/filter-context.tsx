import { useState, useCallback, type ReactNode } from "react";
import type { TimeRange } from "@/types/api";
import {
  FilterContext,
  type FilterState,
  type FilterContextType,
} from "./filter-context-definition";

export type { FilterState, FilterContextType };

function getDefaultTimeRange(): TimeRange {
  const endTime = new Date().toISOString();
  const startTime = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  return { start_time: startTime, end_time: endTime };
}

interface FilterProviderProps {
  readonly children: ReactNode;
}

export function FilterProvider({ children }: FilterProviderProps): React.ReactElement {
  const [filters, setFilters] = useState<FilterState>({
    timeRange: getDefaultTimeRange(),
    quickRange: "7d",
    repositories: [],
    users: [],
    excludeUsers: [],
  });

  const setTimeRange = useCallback((range: TimeRange, quickRange: string): void => {
    setFilters((prev) => ({ ...prev, timeRange: range, quickRange }));
  }, []);

  const setRepositories = useCallback((repos: readonly string[]): void => {
    setFilters((prev) => {
      const newFilters = { ...prev, repositories: repos };
      return newFilters;
    });
  }, []);

  const setUsers = useCallback((users: readonly string[]): void => {
    setFilters((prev) => {
      const newFilters = { ...prev, users };
      return newFilters;
    });
  }, []);

  const setExcludeUsers = useCallback((users: readonly string[]): void => {
    setFilters((prev) => ({ ...prev, excludeUsers: users }));
  }, []);

  const resetFilters = useCallback((): void => {
    setFilters({
      timeRange: getDefaultTimeRange(),
      quickRange: "7d",
      repositories: [],
      users: [],
      excludeUsers: [],
    });
  }, []);

  return (
    <FilterContext.Provider
      value={{
        filters,
        setTimeRange,
        setRepositories,
        setUsers,
        setExcludeUsers,
        resetFilters,
      }}
    >
      {children}
    </FilterContext.Provider>
  );
}
