import { useState, useMemo, useCallback } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MultiSelect } from "@/components/ui/multi-select";
import { CollapsibleSection } from "@/components/shared/collapsible-section";
import { useFilters } from "@/hooks/use-filters";
import type { TimeRange } from "@/types/api";

interface FilterPanelProps {
  readonly repositorySuggestions?: readonly string[];
  readonly userSuggestions?: readonly string[];
  readonly onRefresh?: () => void;
}

export function FilterPanel({
  repositorySuggestions = [],
  userSuggestions = [],
  onRefresh,
}: FilterPanelProps): React.ReactElement {
  const {
    filters,
    setTimeRange,
    setRepositories,
    setUsers,
    setExcludeUsers,
    setExcludeMaintainers,
  } = useFilters();

  const [customStartTime, setCustomStartTime] = useState("");
  const [customEndTime, setCustomEndTime] = useState("");
  const [isCustomMode, setIsCustomMode] = useState(false);

  const formatDateForInput = useCallback((isoString: string): string => {
    const date = new Date(isoString);
    const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return localDate.toISOString().slice(0, 16);
  }, []);

  // Derive input values from filters when not in custom mode
  const startTimeInput = useMemo(() => {
    if (isCustomMode) return customStartTime;
    return filters.timeRange.start_time ? formatDateForInput(filters.timeRange.start_time) : "";
  }, [isCustomMode, customStartTime, filters.timeRange.start_time, formatDateForInput]);

  const endTimeInput = useMemo(() => {
    if (isCustomMode) return customEndTime;
    return filters.timeRange.end_time ? formatDateForInput(filters.timeRange.end_time) : "";
  }, [isCustomMode, customEndTime, filters.timeRange.end_time, formatDateForInput]);

  const handleQuickRangeChange = (value: string): void => {
    setIsCustomMode(false);
    const now = new Date();
    const start = new Date();

    switch (value) {
      case "1h":
        start.setHours(now.getHours() - 1);
        break;
      case "24h":
        start.setHours(now.getHours() - 24);
        break;
      case "7d":
        start.setDate(now.getDate() - 7);
        break;
      case "30d":
        start.setDate(now.getDate() - 30);
        break;
      default:
        start.setDate(now.getDate() - 7);
    }

    const timeRange: TimeRange = {
      start_time: start.toISOString(),
      end_time: now.toISOString(),
    };

    setTimeRange(timeRange, value);
  };

  const handleStartTimeChange = (value: string): void => {
    setIsCustomMode(true);
    setCustomStartTime(value);
  };

  const handleEndTimeChange = (value: string): void => {
    setIsCustomMode(true);
    setCustomEndTime(value);
  };

  const handleCustomTimeBlur = (): void => {
    if (customStartTime && customEndTime) {
      const start = new Date(customStartTime);
      const end = new Date(customEndTime);

      // Validate that start time is before end time
      if (start.getTime() >= end.getTime()) {
        // Swap values if start is after or equal to end
        setCustomStartTime(end.toISOString().slice(0, 16));
        setCustomEndTime(start.toISOString().slice(0, 16));
        return;
      }

      const timeRange: TimeRange = {
        start_time: start.toISOString(),
        end_time: end.toISOString(),
      };
      setTimeRange(timeRange, "custom");
    }
  };

  return (
    <CollapsibleSection title="Filters & Controls" defaultOpen={true}>
      <div className="flex flex-nowrap items-end gap-2 overflow-x-auto pb-4">
        <div className="flex-1 space-y-1" style={{ minWidth: "140px" }}>
          <Label htmlFor="quick-range" className="text-xs">
            Quick Range
          </Label>
          <Select value={filters.quickRange} onValueChange={handleQuickRangeChange}>
            <SelectTrigger id="quick-range" className="h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1h">Last Hour</SelectItem>
              <SelectItem value="24h">Last 24 Hours</SelectItem>
              <SelectItem value="7d">Last 7 Days</SelectItem>
              <SelectItem value="30d">Last 30 Days</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="flex-1 space-y-1" style={{ minWidth: "210px" }}>
          <Label htmlFor="start-time" className="text-xs">
            Start Time
          </Label>
          <Input
            id="start-time"
            type="datetime-local"
            value={startTimeInput}
            onChange={(e) => {
              handleStartTimeChange(e.target.value);
            }}
            onBlur={handleCustomTimeBlur}
            className="h-9"
          />
        </div>

        <div className="flex-1 space-y-1" style={{ minWidth: "210px" }}>
          <Label htmlFor="end-time" className="text-xs">
            End Time
          </Label>
          <Input
            id="end-time"
            type="datetime-local"
            value={endTimeInput}
            onChange={(e) => {
              handleEndTimeChange(e.target.value);
            }}
            onBlur={handleCustomTimeBlur}
            className="h-9"
          />
        </div>

        <div className="flex-1 space-y-1" style={{ minWidth: "200px" }}>
          <Label htmlFor="repositories" className="text-xs">
            Repositories
          </Label>
          <MultiSelect
            id="repositories"
            placeholder="Select repositories..."
            value={filters.repositories}
            onChange={(repos) => {
              setRepositories(repos);
            }}
            suggestions={repositorySuggestions}
          />
        </div>

        <div className="flex-1 space-y-1" style={{ minWidth: "180px" }}>
          <Label htmlFor="users" className="text-xs">
            Users
          </Label>
          <MultiSelect
            id="users"
            placeholder="Select users..."
            value={filters.users}
            onChange={(users) => {
              setUsers(users);
            }}
            suggestions={userSuggestions}
          />
        </div>

        <div className="flex-1 space-y-1" style={{ minWidth: "180px" }}>
          <Label htmlFor="exclude-users" className="text-xs">
            Exclude Users
          </Label>
          <MultiSelect
            id="exclude-users"
            placeholder="Select users to exclude..."
            value={filters.excludeUsers}
            onChange={(users) => {
              setExcludeUsers(users);
            }}
            suggestions={userSuggestions}
          />
        </div>

        <div className="flex-shrink-0 space-y-1" style={{ minWidth: "150px" }}>
          <Label className="text-xs invisible">Toggle</Label>
          <div className="flex items-center h-9 space-x-2">
            <Checkbox
              id="exclude-maintainers"
              checked={filters.excludeMaintainers}
              onCheckedChange={(checked) => {
                setExcludeMaintainers(checked === true);
              }}
            />
            <Label
              htmlFor="exclude-maintainers"
              className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70 cursor-pointer"
            >
              Exclude Maintainers
            </Label>
          </div>
        </div>

        <div className="flex-shrink-0 space-y-1">
          <Label className="text-xs invisible">Actions</Label>
          <Button
            variant="default"
            onClick={() => {
              onRefresh?.();
            }}
            className="h-9 bg-blue-600 hover:bg-blue-700 text-white"
            size="sm"
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>
    </CollapsibleSection>
  );
}
