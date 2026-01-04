import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { HelpCircle } from "lucide-react";

export interface KPIItem {
  readonly label: string;
  readonly value: string | number;
  readonly unit?: string;
  readonly trend?: {
    readonly value: number;
    readonly label: string;
  };
  readonly warning?: string;
  readonly tooltip?: string;
}

interface KPICardsProps {
  readonly items: readonly KPIItem[];
  readonly isLoading?: boolean;
  readonly columns?: 2 | 3 | 4 | 5 | 6;
}

export function KPICards({
  items,
  isLoading = false,
  columns = 4,
}: KPICardsProps): React.ReactElement {
  const gridCols = {
    2: "grid-cols-1 md:grid-cols-2",
    3: "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
    4: "grid-cols-1 md:grid-cols-2 lg:grid-cols-4",
    5: "grid-cols-1 md:grid-cols-2 xl:grid-cols-5",
    6: "grid-cols-1 md:grid-cols-2 xl:grid-cols-6",
  }[columns];

  if (isLoading) {
    return (
      <div className={`grid gap-4 ${gridCols}`}>
        {Array.from({ length: columns }).map((_, i) => (
          <Card key={i}>
            <CardHeader className="pb-2">
              <Skeleton className="h-4 w-24" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <TooltipProvider>
      <div className={`grid gap-4 ${gridCols}`}>
        {items.map((item) => (
          <Card key={item.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-1.5">
                {item.label}
                {item.tooltip && (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="h-3.5 w-3.5 text-muted-foreground/60 hover:text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs text-left">
                      <p>{item.tooltip}</p>
                    </TooltipContent>
                  </Tooltip>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-bold">
                  {typeof item.value === "number" ? item.value.toLocaleString() : item.value}
                </span>
                {item.unit && <span className="text-sm text-muted-foreground">{item.unit}</span>}
              </div>
              {item.trend && (
                <div
                  className={`text-xs mt-1 ${item.trend.value >= 0 ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400"}`}
                >
                  {item.trend.value >= 0 ? "↑" : "↓"} {Math.abs(item.trend.value)}%{" "}
                  {item.trend.label}
                </div>
              )}
              {item.warning && (
                <div className="text-xs mt-1 text-amber-600 dark:text-amber-400">
                  Warning: {item.warning}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </TooltipProvider>
  );
}
