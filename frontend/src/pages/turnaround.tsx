import { useFilters } from "@/hooks/use-filters";
import { TurnaroundCards } from "@/components/dashboard";

export function TurnaroundPage(): React.ReactElement {
  const { filters } = useFilters();

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Turnaround Metrics</h2>
      <TurnaroundCards
        timeRange={filters.timeRange}
        repositories={filters.repositories}
        users={filters.users}
        excludeUsers={filters.excludeUsers}
      />
    </div>
  );
}
