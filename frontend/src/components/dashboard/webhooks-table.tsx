import { useState } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { PaginationControls } from "@/components/shared/pagination-controls";
import { useWebhooks } from "@/hooks/use-api";
import type { TimeRange } from "@/types/api";

interface WebhooksTableProps {
  readonly timeRange?: TimeRange;
  readonly pageSize?: number;
  readonly repositories?: readonly string[];
}

export function WebhooksTable({
  timeRange,
  pageSize: initialPageSize = 25,
  repositories,
}: WebhooksTableProps): React.ReactElement {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(initialPageSize);

  // Note: Webhooks API uses singular 'repository' and doesn't support user filtering
  // We only apply repository filter if a single repository is selected
  const { data, isLoading, error } = useWebhooks({
    ...timeRange,
    page,
    page_size: pageSize,
    ...(repositories && repositories.length === 1 ? { repository: repositories[0] } : {}),
  });

  if (error) {
    return (
      <div className="text-destructive" role="alert">
        Failed to load webhooks: {error.message}
      </div>
    );
  }

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const totalPages = data?.pagination.total_pages ?? 0;

  return (
    <div className="space-y-4">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Event Type</TableHead>
            <TableHead>Repository</TableHead>
            <TableHead>Sender</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Processing Time</TableHead>
            <TableHead>Created At</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading ? (
            // Loading skeleton rows
            Array.from({ length: pageSize }).map((_, i) => (
              <TableRow key={i}>
                {Array.from({ length: 6 }).map((_, j) => (
                  <TableCell key={j}>
                    <Skeleton className="h-4 w-full" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : data?.data.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
                No webhook events found
              </TableCell>
            </TableRow>
          ) : (
            data?.data.map((webhook) => (
              <TableRow key={webhook.delivery_id}>
                <TableCell className="font-medium">{webhook.event_type}</TableCell>
                <TableCell>{webhook.repository}</TableCell>
                <TableCell>{webhook.sender}</TableCell>
                <TableCell>
                  <Badge
                    variant={webhook.status === "success" ? "default" : "destructive"}
                    className="min-w-[70px] justify-center"
                  >
                    {webhook.status}
                  </Badge>
                </TableCell>
                <TableCell>{webhook.processing_time_ms}ms</TableCell>
                <TableCell>{formatDate(webhook.created_at)}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {/* Pagination */}
      {data && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {(page - 1) * pageSize + 1} to{" "}
            {Math.min(page * pageSize, data.pagination.total)} of {data.pagination.total} events
          </div>
          <PaginationControls
            currentPage={page}
            totalPages={Math.max(1, totalPages)}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={(size: number) => {
              setPageSize(size);
              setPage(1); // Reset to first page
            }}
          />
        </div>
      )}
    </div>
  );
}
