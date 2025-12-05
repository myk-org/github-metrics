import { useState, useMemo, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PRStoryTimeline, EventTypeFilter } from "@/components/pr-story";
import { useUserPRs, usePRStory } from "@/hooks/use-api";
import { useFilters } from "@/hooks/use-filters";
import { cn } from "@/lib/utils";
import { Search, ChevronLeft, ChevronRight } from "lucide-react";
import type { UserPR } from "@/types/user-prs";

interface UserPRsModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly username: string | null;
  readonly category: string | null;
}

function getRoleDescription(category: string | null): string {
  const roleMap: Record<string, string> = {
    pr_creators: "created by",
    pr_reviewers: "reviewed by",
    pr_approvers: "approved by",
    pr_lgtm: "with LGTM by",
  };
  return category ? roleMap[category] || "for" : "for";
}

function getPRStateBadgeVariant(
  state: string,
  merged: boolean
): "default" | "secondary" | "destructive" | "outline" {
  if (merged) return "default"; // Will be styled with purple
  if (state === "open") return "secondary"; // Will be styled with green
  if (state === "closed") return "destructive";
  return "outline";
}

function formatDate(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return timestamp;
  }
}

interface PRListItemProps {
  readonly pr: UserPR;
  readonly isSelected: boolean;
  readonly onClick: () => void;
}

function PRListItem({ pr, isSelected, onClick }: PRListItemProps): React.ReactElement {
  const stateLabel = pr.merged ? "merged" : pr.state;
  const badgeVariant = getPRStateBadgeVariant(pr.state, pr.merged);

  return (
    <div
      className={cn(
        "cursor-pointer border-b last:border-b-0 transition-colors",
        isSelected
          ? "bg-muted border-l-4 border-l-primary"
          : "hover:bg-muted/50 border-l-4 border-l-transparent"
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-4 p-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-sm font-bold text-primary">#{pr.number}</span>
            <h3 className="text-sm font-semibold truncate">{pr.title}</h3>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{pr.repository}</span>
            <span>•</span>
            <span>{formatDate(pr.created_at)}</span>
          </div>
        </div>
        <div className="flex-shrink-0">
          <Badge
            variant={badgeVariant}
            className={
              pr.merged
                ? "bg-purple-600 hover:bg-purple-700"
                : pr.state === "open"
                  ? "bg-green-600 hover:bg-green-700"
                  : ""
            }
          >
            {stateLabel}
          </Badge>
        </div>
      </div>
    </div>
  );
}

export function UserPRsModal({
  open,
  onOpenChange,
  username,
  category,
}: UserPRsModalProps): React.ReactElement {
  const { filters } = useFilters();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [selectedPR, setSelectedPR] = useState<{ repository: string; number: number } | null>(null);
  const [selectedEventTypes, setSelectedEventTypes] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  // Fetch user PRs when modal is open
  const { data, isLoading } = useUserPRs(
    open && username && filters.timeRange.start_time && filters.timeRange.end_time
      ? {
          start_time: filters.timeRange.start_time,
          end_time: filters.timeRange.end_time,
          users: [username],
          ...(category ? { role: category } : {}),
          ...(filters.repositories.length > 0 ? { repositories: filters.repositories } : {}),
          page,
          page_size: pageSize,
        }
      : undefined
  );

  // Fetch PR story when a PR is selected
  const { data: prStoryData, isLoading: isPRStoryLoading } = usePRStory(
    selectedPR?.repository ?? "",
    selectedPR?.number ?? 0,
    Boolean(selectedPR)
  );

  // Extract unique event types from PR story
  const eventTypes = useMemo(() => {
    if (!prStoryData) return [];
    const types = new Set(prStoryData.events.map((event) => event.event_type));
    return Array.from(types);
  }, [prStoryData]);

  // Initialize selected event types when PR changes
  useEffect(() => {
    if (eventTypes.length > 0) {
      setSelectedEventTypes(new Set(eventTypes));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPR?.repository, selectedPR?.number]);

  // Filter events based on selected event types
  const filteredEvents = useMemo(() => {
    if (!prStoryData) return [];
    if (selectedEventTypes.size === 0) return prStoryData.events;
    return prStoryData.events.filter((event) => selectedEventTypes.has(event.event_type));
  }, [prStoryData, selectedEventTypes]);

  // Filter PRs based on search query
  const filteredPRs = useMemo(() => {
    if (!data?.data || !searchQuery.trim()) return data?.data ?? [];
    const query = searchQuery.toLowerCase();
    return data.data.filter(
      (pr) =>
        pr.title.toLowerCase().includes(query) ||
        String(pr.number).includes(query) ||
        pr.repository.toLowerCase().includes(query)
    );
  }, [data?.data, searchQuery]);

  const roleText = getRoleDescription(category);
  const totalPRs = data?.pagination.total ?? 0;
  const displayedPRs = searchQuery.trim() ? filteredPRs.length : totalPRs;

  const handlePRClick = (pr: UserPR): void => {
    setSelectedPR({ repository: pr.repository, number: pr.number });
    // Reset event type filter when selecting a new PR
    setSelectedEventTypes(new Set());
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="w-[90vw] max-w-[1500px] h-[85vh] flex flex-col p-0"
        style={{ resize: "both", overflow: "hidden", minWidth: "900px", minHeight: "500px" }}
      >
        <DialogHeader className="px-6 pt-6 pb-4 border-b">
          <DialogTitle>
            PRs {roleText} {username} ({displayedPRs})
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-1 min-h-0 overflow-hidden">
          {/* Left Panel - PR List */}
          <div className="w-[45%] border-r flex flex-col min-h-0">
            {/* Search Input */}
            <div className="p-3 border-b flex-shrink-0">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search PRs..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                  }}
                  className="pl-9"
                />
              </div>
            </div>

            <div className="flex-1 overflow-y-auto min-h-0">
              {isLoading ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-sm text-muted-foreground">Loading user PRs...</div>
                </div>
              ) : !data || data.data.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-sm text-muted-foreground">
                    No PRs found for this user in the selected time range.
                  </div>
                </div>
              ) : filteredPRs.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-sm text-muted-foreground">
                    No PRs match the search query.
                  </div>
                </div>
              ) : (
                <div className="space-y-0">
                  {filteredPRs.map((pr) => (
                    <PRListItem
                      key={`${pr.repository}-${String(pr.number)}`}
                      pr={pr}
                      isSelected={Boolean(
                        selectedPR &&
                          selectedPR.repository === pr.repository &&
                          selectedPR.number === pr.number
                      )}
                      onClick={() => {
                        handlePRClick(pr);
                      }}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Pagination Controls */}
            {data && data.pagination.total > 0 && !searchQuery.trim() && (
              <div className="border-t p-3 flex-shrink-0 bg-background">
                <div className="flex flex-col gap-2">
                  {/* Page size selector */}
                  <Select
                    value={String(pageSize)}
                    onValueChange={(value) => {
                      setPageSize(Number(value));
                      setPage(1);
                    }}
                  >
                    <SelectTrigger className="h-8 w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="10">10 per page</SelectItem>
                      <SelectItem value="25">25 per page</SelectItem>
                      <SelectItem value="50">50 per page</SelectItem>
                    </SelectContent>
                  </Select>

                  {/* Navigation controls */}
                  <div className="flex items-center justify-between">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setPage(page - 1);
                      }}
                      disabled={page <= 1}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      Prev
                    </Button>
                    <span className="text-xs text-muted-foreground">
                      Page {page} of {data.pagination.total_pages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setPage(page + 1);
                      }}
                      disabled={page >= data.pagination.total_pages}
                    >
                      Next
                      <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Panel - PR Story Timeline */}
          <div className="w-[55%] flex flex-col min-h-0">
            {!selectedPR ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-sm text-muted-foreground">
                  Select a PR to view its timeline
                </div>
              </div>
            ) : isPRStoryLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-sm text-muted-foreground">Loading PR timeline...</div>
              </div>
            ) : !prStoryData ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-sm text-destructive">Failed to load PR timeline</div>
              </div>
            ) : (
              <>
                {/* PR Story Toolbar */}
                <div className="border-b p-4 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2 min-w-0 flex-1">
                    <span className="font-mono font-bold text-primary">
                      #{prStoryData.pr.number}
                    </span>
                    <h3 className="font-semibold truncate">{prStoryData.pr.title}</h3>
                  </div>
                  <EventTypeFilter
                    eventTypes={eventTypes}
                    selectedTypes={selectedEventTypes}
                    onSelectionChange={setSelectedEventTypes}
                  />
                </div>

                {/* PR Story Summary */}
                <div className="border-b p-4">
                  <div className="flex items-center gap-4 text-xs text-muted-foreground flex-wrap">
                    <span>
                      <strong>{prStoryData.summary.total_commits}</strong> commits
                    </span>
                    <span>•</span>
                    <span>
                      <strong>{prStoryData.summary.total_reviews}</strong> reviews
                    </span>
                    <span>•</span>
                    <span>
                      <strong>{prStoryData.summary.total_check_runs}</strong> check runs
                    </span>
                    <span>•</span>
                    <span>
                      <strong>{prStoryData.summary.total_comments}</strong> comments
                    </span>
                  </div>
                </div>

                {/* PR Story Timeline */}
                <div className="flex-1 overflow-y-auto p-4">
                  {filteredEvents.length === 0 ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="text-sm text-muted-foreground">
                        No events match the selected filters
                      </div>
                    </div>
                  ) : (
                    <PRStoryTimeline events={filteredEvents} />
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
