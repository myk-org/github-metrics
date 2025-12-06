import { useMemo, useState } from "react";
import { Filter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

interface EventTypeFilterProps {
  readonly eventTypes: readonly string[];
  readonly selectedTypes: ReadonlySet<string>;
  readonly onSelectionChange: (selectedTypes: Set<string>) => void;
}

// Event type icons matching legacy implementation
const EVENT_TYPE_ICONS: Record<string, string> = {
  pr_opened: "🔀",
  pr_closed: "❌",
  pr_merged: "🟣",
  pr_reopened: "🔄",
  commit: "📝",
  review_approved: "✅",
  review_changes: "🔄",
  review_comment: "💬",
  comment: "💬",
  review_requested: "👁️",
  ready_for_review: "👁️",
  label_added: "🏷️",
  label_removed: "🏷️",
  verified: "🛡️",
  approved_label: "✅",
  lgtm: "👍",
  check_run: "▶️",
  check_run_completed: "▶️",
  review_commented: "💬",
  converted_to_draft: "📄",
};

// Event type labels matching legacy implementation
const EVENT_TYPE_LABELS: Record<string, string> = {
  pr_opened: "PR Opened",
  pr_closed: "PR Closed",
  pr_merged: "Merged",
  pr_reopened: "Reopened",
  commit: "Commit",
  review_approved: "Approved",
  review_changes: "Changes Requested",
  review_comment: "Review Comment",
  comment: "Comment",
  review_requested: "Review Requested",
  ready_for_review: "Ready for Review",
  label_added: "Label Added",
  label_removed: "Label Removed",
  verified: "Verified",
  approved_label: "Approved",
  lgtm: "LGTM",
  check_run: "Check Run",
  check_run_completed: "Check Run Completed",
  review_commented: "Review Comment",
  converted_to_draft: "Converted to Draft",
};

export function EventTypeFilter({
  eventTypes,
  selectedTypes,
  onSelectionChange,
}: EventTypeFilterProps): React.ReactElement {
  const [open, setOpen] = useState(false);

  const sortedEventTypes = useMemo(() => {
    return [...eventTypes].sort();
  }, [eventTypes]);

  const handleSelectAll = (): void => {
    const allTypes = new Set(eventTypes);
    onSelectionChange(allTypes);
  };

  const handleSelectNone = (): void => {
    onSelectionChange(new Set());
  };

  const handleToggle = (eventType: string): void => {
    const newSelection = new Set(selectedTypes);
    if (newSelection.has(eventType)) {
      newSelection.delete(eventType);
    } else {
      newSelection.add(eventType);
    }
    onSelectionChange(newSelection);
  };

  const toggleText = useMemo(() => {
    const selectedCount = selectedTypes.size;
    const totalCount = eventTypes.length;
    if (selectedCount === totalCount) {
      return "All Events";
    }
    if (selectedCount === 0) {
      return "None";
    }
    return `${String(selectedCount)}/${String(totalCount)}`;
  }, [selectedTypes.size, eventTypes.length]);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-8 gap-2">
          <Filter className="h-4 w-4" />
          <span className="text-xs">{toggleText}</span>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-64 p-0" align="end">
        <Command>
          <div className="flex gap-2 p-2 border-b">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-7 text-xs"
              onClick={handleSelectAll}
            >
              All
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 h-7 text-xs"
              onClick={handleSelectNone}
            >
              None
            </Button>
          </div>
          <CommandList>
            <CommandEmpty>No event types found.</CommandEmpty>
            <CommandGroup>
              {sortedEventTypes.map((eventType) => {
                const isSelected = selectedTypes.has(eventType);
                const icon = EVENT_TYPE_ICONS[eventType] || "●";
                const label = EVENT_TYPE_LABELS[eventType] || eventType.replace(/_/g, " ");

                return (
                  <CommandItem
                    key={eventType}
                    onSelect={() => {
                      handleToggle(eventType);
                    }}
                    className="flex items-center gap-2 cursor-pointer"
                  >
                    <Checkbox
                      checked={isSelected}
                      className="pointer-events-none"
                      aria-hidden="true"
                    />
                    <span className="text-sm">{icon}</span>
                    <Label className="flex-1 cursor-pointer text-sm">{label}</Label>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
