import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useTurnaround } from "@/hooks/use-api";
import type { TimeRange } from "@/types/api";
import { Clock, CheckCircle, GitMerge, GitPullRequest } from "lucide-react";
import { formatHours } from "@/utils/time-format";

interface TurnaroundCardsProps {
  readonly timeRange?: TimeRange;
  readonly repositories?: readonly string[];
  readonly users?: readonly string[];
  readonly excludeUsers?: readonly string[];
}

interface CardData {
  readonly title: string;
  readonly value: string | number;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly description: string;
}

export function TurnaroundCards({
  timeRange,
  repositories,
  users,
  excludeUsers,
}: TurnaroundCardsProps): React.ReactElement {
  const filters = {
    ...(repositories && repositories.length > 0 && { repositories }),
    ...(users && users.length > 0 && { users }),
    ...(excludeUsers && excludeUsers.length > 0 && { exclude_users: excludeUsers }),
  };

  const { data, isLoading, error } = useTurnaround(timeRange, filters);

  if (error) {
    return (
      <div className="text-destructive" role="alert">
        Failed to load turnaround metrics: {error.message}
      </div>
    );
  }

  const cards: readonly CardData[] = [
    {
      title: "Time to First Review",
      value: data?.summary ? formatHours(data.summary.avg_time_to_first_review_hours) : "-",
      icon: Clock,
      description: "Average time until first review",
    },
    {
      title: "Time to Approval",
      value: data?.summary ? formatHours(data.summary.avg_time_to_approval_hours) : "-",
      icon: CheckCircle,
      description: "Average time until approval",
    },
    {
      title: "PR Lifecycle",
      value: data?.summary ? formatHours(data.summary.avg_pr_lifecycle_hours) : "-",
      icon: GitMerge,
      description: "Average PR lifecycle duration",
    },
    {
      title: "PRs Analyzed",
      value: data?.summary ? data.summary.total_prs_analyzed : 0,
      icon: GitPullRequest,
      description: "Total pull requests",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">{card.value}</div>
                <p className="text-xs text-muted-foreground">{card.description}</p>
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
