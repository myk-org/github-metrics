import type { ReactElement } from "react";
import { useMemo, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";
import { PRStoryTimeline } from "./pr-story-timeline";
import { EventTypeFilter } from "./event-type-filter";
import type { PRStory } from "@/types/pr-story";

interface PRStoryModalProps {
  readonly isOpen: boolean;
  readonly onClose: () => void;
  readonly prStory: PRStory | undefined;
  readonly isLoading: boolean;
  readonly error: Error | null;
}

interface PRStoryContentProps {
  readonly prStory: PRStory;
}

// Separate component to handle event filtering - keyed by PR to reset state
function PRStoryContent({ prStory }: PRStoryContentProps): ReactElement {
  // Get unique event types from events
  const eventTypes = useMemo(() => {
    return Array.from(new Set(prStory.events.map((event) => event.event_type)));
  }, [prStory]);

  // Track selected event types - initialized with all types
  const [selectedEventTypes, setSelectedEventTypes] = useState<Set<string>>(
    () => new Set(eventTypes)
  );

  // Filter events based on selected types
  const filteredEvents = useMemo(() => {
    if (selectedEventTypes.size === 0) {
      return [];
    }
    return prStory.events.filter((event) => selectedEventTypes.has(event.event_type));
  }, [prStory, selectedEventTypes]);

  return (
    <div className="py-4">
      {/* Summary Toolbar - horizontal layout matching legacy */}
      <div className="flex flex-wrap items-center gap-4 mb-4 pb-3 border-b">
        {/* Summary stats */}
        <div className="flex items-center gap-3 text-sm">
          <div className="flex items-center gap-1">
            <span aria-hidden="true">📝</span>
            <strong>{prStory.summary.total_commits}</strong>
            <span className="text-muted-foreground">
              commit{prStory.summary.total_commits !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span aria-hidden="true">💬</span>
            <strong>{prStory.summary.total_reviews}</strong>
            <span className="text-muted-foreground">
              review{prStory.summary.total_reviews !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span aria-hidden="true">▶️</span>
            <strong>{prStory.summary.total_check_runs}</strong>
            <span className="text-muted-foreground">
              check run{prStory.summary.total_check_runs !== 1 ? "s" : ""}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span aria-hidden="true">💭</span>
            <strong>{prStory.summary.total_comments}</strong>
            <span className="text-muted-foreground">
              comment{prStory.summary.total_comments !== 1 ? "s" : ""}
            </span>
          </div>
        </div>

        {/* Event type filter */}
        <div className="ml-auto">
          <EventTypeFilter
            eventTypes={eventTypes}
            selectedTypes={selectedEventTypes}
            onSelectionChange={setSelectedEventTypes}
          />
        </div>
      </div>

      {/* Timeline */}
      {prStory.events.length === 0 ? (
        <div className="text-center text-muted-foreground py-8">No events found for this PR</div>
      ) : filteredEvents.length > 0 ? (
        <PRStoryTimeline events={filteredEvents} />
      ) : (
        <div className="text-center text-muted-foreground py-8">
          No events match the current filter
        </div>
      )}
    </div>
  );
}

export function PRStoryModal({
  isOpen,
  onClose,
  prStory,
  isLoading,
  error,
}: PRStoryModalProps): ReactElement {
  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) {
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
        <DialogHeader>
          {isLoading ? (
            <>
              <Skeleton className="h-8 w-3/4 mb-2" />
              <Skeleton className="h-4 w-1/2" />
            </>
          ) : prStory ? (
            <>
              <DialogTitle className="flex items-center gap-2 flex-wrap">
                <span>
                  PR #{prStory.pr.number}: {prStory.pr.title}
                </span>
                <a
                  href={`https://github.com/${prStory.pr.repository}/pull/${String(prStory.pr.number)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline inline-flex items-center gap-1"
                  aria-label={`Open PR #${String(prStory.pr.number)} on GitHub`}
                  onClick={(e) => {
                    e.stopPropagation();
                  }}
                >
                  <ExternalLink className="h-4 w-4" aria-hidden="true" />
                </a>
              </DialogTitle>
              <DialogDescription className="flex items-center gap-2 flex-wrap">
                <span className="text-sm">
                  by <strong>{prStory.pr.author}</strong> in{" "}
                  <strong>{prStory.pr.repository}</strong>
                </span>
                <Badge
                  variant={
                    prStory.pr.merged
                      ? "default"
                      : prStory.pr.state === "open"
                        ? "secondary"
                        : "destructive"
                  }
                  className={prStory.pr.merged ? "bg-purple-600 hover:bg-purple-700" : ""}
                >
                  {prStory.pr.merged ? "merged" : prStory.pr.state}
                </Badge>
              </DialogDescription>
            </>
          ) : (
            <DialogTitle>PR Story</DialogTitle>
          )}
        </DialogHeader>

        <div className="flex-1 min-h-0 overflow-auto pr-4">
          {isLoading ? (
            <div className="space-y-4 py-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex gap-4">
                  <Skeleton className="h-10 w-10 rounded-full flex-shrink-0" />
                  <div className="flex-1 space-y-2">
                    <Skeleton className="h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="py-8 text-center text-destructive" role="alert">
              <p className="font-semibold mb-2">Error loading PR story</p>
              <p className="text-sm text-muted-foreground">{error.message}</p>
            </div>
          ) : prStory ? (
            <PRStoryContent
              key={`${prStory.pr.repository}/${String(prStory.pr.number)}`}
              prStory={prStory}
            />
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
