import { createContext } from "react";
import type { TimeRange } from "@/types/api";

export interface FilterState {
  readonly timeRange: TimeRange;
  readonly quickRange: string;
  readonly repositories: readonly string[];
  readonly users: readonly string[];
  readonly excludeUsers: readonly string[];
  readonly excludeMaintainers: boolean;
}

export interface FilterContextType {
  readonly filters: FilterState;
  readonly setTimeRange: (range: TimeRange, quickRange: string) => void;
  readonly setRepositories: (repos: readonly string[]) => void;
  readonly setUsers: (users: readonly string[]) => void;
  readonly setExcludeUsers: (users: readonly string[]) => void;
  readonly setExcludeMaintainers: (exclude: boolean) => void;
  readonly resetFilters: () => void;
}

export const FilterContext = createContext<FilterContextType | undefined>(undefined);
