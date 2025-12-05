import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useRepositories } from "@/hooks/use-api";
import type { TimeRange } from "@/types/api";
import { FolderGit2 } from "lucide-react";

interface RepositoriesTableProps {
  readonly timeRange?: TimeRange;
  readonly repositories?: readonly string[];
  readonly users?: readonly string[];
  readonly excludeUsers?: readonly string[];
}

export function RepositoriesTable({
  timeRange,
  repositories: repoFilter,
  users,
  excludeUsers,
}: RepositoriesTableProps): React.ReactElement {
  const filters = {
    ...(repoFilter && repoFilter.length > 0 && { repositories: repoFilter }),
    ...(users && users.length > 0 && { users }),
    ...(excludeUsers && excludeUsers.length > 0 && { exclude_users: excludeUsers }),
  };

  const { data, isLoading, error } = useRepositories(timeRange, filters);

  if (error) {
    return <div className="text-destructive">Failed to load repositories: {error.message}</div>;
  }

  const repositories = data?.repositories ?? [];

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Repository</TableHead>
          <TableHead className="text-right">Events</TableHead>
          <TableHead className="text-right">Percentage</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => (
            <TableRow key={i}>
              {Array.from({ length: 3 }).map((_, j) => (
                <TableCell key={j}>
                  <Skeleton className="h-4 w-full" />
                </TableCell>
              ))}
            </TableRow>
          ))
        ) : repositories.length === 0 ? (
          <TableRow>
            <TableCell colSpan={3} className="text-center text-muted-foreground">
              No repositories found
            </TableCell>
          </TableRow>
        ) : (
          repositories.map((repo) => {
            const percentage = repo.percentage !== null ? `${repo.percentage.toFixed(1)}%` : "N/A";
            return (
              <TableRow key={repo.repository}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <FolderGit2 className="h-4 w-4 text-muted-foreground" />
                    <span className="font-medium">{repo.repository}</span>
                  </div>
                </TableCell>
                <TableCell className="text-right">{repo.total_events}</TableCell>
                <TableCell className="text-right">{percentage}</TableCell>
              </TableRow>
            );
          })
        )}
      </TableBody>
    </Table>
  );
}
