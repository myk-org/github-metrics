import { useFilters } from "@/hooks/use-filters";
import { RepositoriesTable } from "@/components/dashboard";

export function RepositoriesPage(): React.ReactElement {
  const { filters } = useFilters();

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Repositories</h2>
      <RepositoriesTable
        timeRange={filters.timeRange}
        repositories={filters.repositories}
        users={filters.users}
        excludeUsers={filters.excludeUsers}
      />
    </div>
  );
}
