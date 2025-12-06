import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useSummary } from "@/hooks/use-api";
import type { TimeRange } from "@/types/api";
import { Webhook, CheckCircle, XCircle, GitPullRequest, FolderGit2, Users } from "lucide-react";

interface SummaryCardsProps {
  readonly timeRange?: TimeRange;
}

interface CardData {
  readonly title: string;
  readonly value: number | string;
  readonly icon: React.ComponentType<{ className?: string }>;
  readonly color: string;
}

export function SummaryCards({ timeRange }: SummaryCardsProps): React.ReactElement {
  const { data: summary, isLoading, error } = useSummary(timeRange);

  if (error) {
    // Log detailed error for debugging
    console.error("Failed to load summary:", error);

    // Show sanitized message in production
    return <div className="text-destructive">Failed to load summary. Please try again.</div>;
  }

  const summaryData = summary?.summary;
  const repoCount = summary?.top_repositories.length ?? 0;

  const cards: readonly CardData[] = [
    {
      title: "Total Events",
      value: summaryData?.total_events ?? 0,
      icon: Webhook,
      color: "text-blue-500",
    },
    {
      title: "Successful",
      value: summaryData?.successful_events ?? 0,
      icon: CheckCircle,
      color: "text-green-500",
    },
    {
      title: "Failed",
      value: summaryData?.failed_events ?? 0,
      icon: XCircle,
      color: "text-red-500",
    },
    {
      title: "Success Rate",
      value:
        typeof summaryData?.success_rate === "number"
          ? `${summaryData.success_rate.toFixed(1)}%`
          : "0.0%",
      icon: GitPullRequest,
      color: "text-purple-500",
    },
    {
      title: "Repositories",
      value: repoCount,
      icon: FolderGit2,
      color: "text-orange-500",
    },
    {
      title: "Event Types",
      value: Object.keys(summary?.event_type_distribution ?? {}).length,
      icon: Users,
      color: "text-cyan-500",
    },
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
            <card.icon className={`h-4 w-4 ${card.color}`} />
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-8 w-20" />
            ) : (
              <div className="text-2xl font-bold">{card.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
