import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useFilters } from "@/hooks/use-filters";
import { useTrends } from "@/hooks/use-api";
import { useDateFormat } from "@/hooks/use-date-format";
import { formatDateTime } from "@/utils/time-format";
import { TrendingUp } from "lucide-react";

export function TrendsPage(): React.ReactElement {
  const { filters } = useFilters();
  const { data, isLoading, error } = useTrends(filters.timeRange);
  const { dateFormat } = useDateFormat();

  if (error) {
    return <div className="text-destructive">Failed to load trends: {error.message}</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Trends</h2>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Event Trends
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <Skeleton className="h-64 w-full" />
          ) : data && data.length > 0 ? (
            <div className="space-y-2">
              {data.map((point, index) => (
                <div
                  key={index}
                  className="flex justify-between items-center py-2 border-b last:border-0"
                >
                  <span className="text-sm text-muted-foreground">
                    {formatDateTime(point.timestamp, dateFormat)}
                  </span>
                  <span className="font-medium">{point.count} events</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">No trend data available</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
