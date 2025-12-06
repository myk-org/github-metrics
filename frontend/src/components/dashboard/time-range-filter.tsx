import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import type { TimeRange } from "@/types/api";

interface TimeRangeFilterProps {
  readonly value: string;
  readonly onChange: (range: string, timeRange: TimeRange) => void;
}

interface RangeOption {
  readonly label: string;
  readonly value: string;
  readonly hours: number;
}

const ranges: readonly RangeOption[] = [
  { label: "24h", value: "24h", hours: 24 },
  { label: "7d", value: "7d", hours: 168 },
  { label: "30d", value: "30d", hours: 720 },
  { label: "90d", value: "90d", hours: 2160 },
] as const;

export function TimeRangeFilter({ value, onChange }: TimeRangeFilterProps): React.ReactElement {
  const handleClick = useCallback(
    (range: RangeOption): void => {
      const now = Date.now();
      const endTime = new Date(now).toISOString();
      const startTime = new Date(now - range.hours * 60 * 60 * 1000).toISOString();
      onChange(range.value, { start_time: startTime, end_time: endTime });
    },
    [onChange]
  );

  return (
    <div className="flex gap-2">
      {ranges.map((range) => (
        <Button
          key={range.value}
          variant={value === range.value ? "default" : "outline"}
          size="sm"
          onClick={() => {
            handleClick(range);
          }}
        >
          {range.label}
        </Button>
      ))}
    </div>
  );
}
