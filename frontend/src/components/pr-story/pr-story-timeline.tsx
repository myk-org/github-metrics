import { useState } from "react";
import {
  GitPullRequest,
  XCircle,
  GitMerge,
  GitCommit,
  CheckCircle,
  AlertCircle,
  MessageSquare,
  Tag,
  Play,
  FileText,
  Calendar,
  AlertTriangle,
  RotateCw,
  Eye,
  Shield,
  ThumbsUp,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { formatRelativeTime, formatAbsoluteTime } from "@/utils/time-format";
import type { PRStoryEvent, PREventType } from "@/types/pr-story";

interface PRStoryTimelineProps {
  readonly events: readonly PRStoryEvent[];
}

interface EventConfig {
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly color: string;
  readonly bgColor: string;
  readonly label: string;
}

const EVENT_CONFIG: Record<PREventType, EventConfig> = {
  pr_opened: {
    icon: GitPullRequest,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "PR Opened",
  },
  pr_closed: {
    icon: XCircle,
    color: "text-red-600",
    bgColor: "bg-red-100 dark:bg-red-900",
    label: "PR Closed",
  },
  pr_merged: {
    icon: GitMerge,
    color: "text-purple-600",
    bgColor: "bg-purple-100 dark:bg-purple-900",
    label: "Merged",
  },
  pr_reopened: {
    icon: RotateCw,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "Reopened",
  },
  commit: {
    icon: GitCommit,
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    label: "Commit",
  },
  review_approved: {
    icon: CheckCircle,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900",
    label: "Approved",
  },
  review_changes: {
    icon: AlertCircle,
    color: "text-red-600",
    bgColor: "bg-red-100 dark:bg-red-900",
    label: "Changes Requested",
  },
  review_commented: {
    icon: MessageSquare,
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    label: "Review Comment",
  },
  review_comment: {
    icon: MessageSquare,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "Review Comment",
  },
  comment: {
    icon: MessageSquare,
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    label: "Comment",
  },
  review_requested: {
    icon: Eye,
    color: "text-yellow-600",
    bgColor: "bg-yellow-100 dark:bg-yellow-900",
    label: "Review Requested",
  },
  label_added: {
    icon: Tag,
    color: "text-yellow-600",
    bgColor: "bg-yellow-100 dark:bg-yellow-900",
    label: "Label Added",
  },
  label_removed: {
    icon: Tag,
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    label: "Label Removed",
  },
  verified: {
    icon: Shield,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900",
    label: "Verified",
  },
  approved_label: {
    icon: CheckCircle,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900",
    label: "Approved",
  },
  lgtm: {
    icon: ThumbsUp,
    color: "text-green-600",
    bgColor: "bg-green-100 dark:bg-green-900",
    label: "LGTM",
  },
  check_run: {
    icon: Play,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "Check Run",
  },
  check_run_completed: {
    icon: Play,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "Check Run Completed",
  },
  ready_for_review: {
    icon: Eye,
    color: "text-blue-600",
    bgColor: "bg-blue-100 dark:bg-blue-900",
    label: "Ready for Review",
  },
  converted_to_draft: {
    icon: FileText,
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    label: "Converted to Draft",
  },
};

function getEventConfig(eventType: string): EventConfig {
  // Try exact match first
  if (eventType in EVENT_CONFIG) {
    return EVENT_CONFIG[eventType as PREventType];
  }

  // Fallback to generic config
  return {
    icon: Calendar,
    color: "text-gray-600",
    bgColor: "bg-gray-100 dark:bg-gray-800",
    label: eventType.replace(/_/g, " "),
  };
}

interface TimelineEventProps {
  readonly event: PRStoryEvent;
  readonly isLast: boolean;
}

function TimelineEvent({ event, isLast }: TimelineEventProps): React.ReactElement {
  const config = getEventConfig(event.event_type);
  const Icon = config.icon;
  const [isExpanded, setIsExpanded] = useState(false);

  const hasChildren = event.children && event.children.length > 0;

  return (
    <div className="flex gap-4">
      {/* Timeline icon and line */}
      <div className="flex flex-col items-center">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-full ${config.bgColor}`}
        >
          <Icon className={`h-5 w-5 ${config.color}`} />
        </div>
        {!isLast && <div className="w-0.5 flex-1 bg-border mt-2" />}
      </div>

      {/* Event content */}
      <div className="flex-1 pb-6">
        {hasChildren ? (
          <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
            <div className="flex items-center gap-2 mb-1">
              <CollapsibleTrigger asChild>
                <Button variant="ghost" size="sm" className="p-0 h-auto hover:bg-transparent">
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4" />
                  )}
                </Button>
              </CollapsibleTrigger>
              <span className="font-semibold">
                {event.children.length} {config.label}
                {event.children.length !== 1 ? "s" : ""}
                {event.commit && ` @ ${event.commit.substring(0, 7)}`}
              </span>
              <span className="text-sm text-muted-foreground ml-auto">
                {formatRelativeTime(event.timestamp)}
              </span>
            </div>
            <div className="text-xs text-muted-foreground mb-2">
              {formatAbsoluteTime(event.timestamp)}
            </div>

            <CollapsibleContent>
              <div className="mt-3 space-y-2 pl-6 border-l-2 border-border">
                {event.children.map((checkRun, checkIndex) => (
                  <div
                    key={`${checkRun.name}-${checkIndex.toString()}`}
                    className="flex items-center justify-between gap-2 p-2 bg-muted rounded-md"
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      {checkRun.conclusion === "failure" ? (
                        <AlertTriangle className="h-4 w-4 text-destructive flex-shrink-0" />
                      ) : checkRun.conclusion === "success" ? (
                        <CheckCircle className="h-4 w-4 text-green-600 flex-shrink-0" />
                      ) : (
                        <Play className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                      )}
                      <span className="text-sm font-medium truncate">{checkRun.name}</span>
                    </div>
                    <Badge
                      variant={getCheckRunBadgeVariant(checkRun.conclusion)}
                      className="flex-shrink-0"
                    >
                      {checkRun.conclusion}
                    </Badge>
                  </div>
                ))}
              </div>
            </CollapsibleContent>
          </Collapsible>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold">{config.label}</span>
              <span className="text-sm text-muted-foreground ml-auto">
                {formatRelativeTime(event.timestamp)}
              </span>
            </div>
            <div className="text-xs text-muted-foreground mb-2">
              {formatAbsoluteTime(event.timestamp)}
            </div>

            {event.description && (
              <p className="text-sm text-muted-foreground mb-2">{event.description}</p>
            )}

            {event.body && (
              <div className="mt-2 p-3 bg-muted rounded-md text-sm">
                <p className="whitespace-pre-wrap break-words">{event.body}</p>
                {event.truncated && (
                  <p className="text-muted-foreground italic mt-2">
                    (Message truncated - full content available on GitHub)
                  </p>
                )}
              </div>
            )}

            {event.commit && (
              <div className="mt-2">
                <code className="text-xs bg-muted px-2 py-1 rounded">{event.commit}</code>
              </div>
            )}

            {event.url && (
              <a
                href={event.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline mt-2 inline-block"
              >
                View on GitHub →
              </a>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function getCheckRunBadgeVariant(
  conclusion: string
): "default" | "secondary" | "destructive" | "outline" {
  switch (conclusion) {
    case "success":
      return "default";
    case "failure":
      return "destructive";
    case "skipped":
    case "cancelled":
      return "secondary";
    default:
      return "outline";
  }
}

export function PRStoryTimeline({ events }: PRStoryTimelineProps): React.ReactElement {
  return (
    <div className="space-y-4">
      {events.map((event, index) => (
        <TimelineEvent
          key={`${event.event_type}-${event.timestamp}-${index.toString()}`}
          event={event}
          isLast={index === events.length - 1}
        />
      ))}
    </div>
  );
}
