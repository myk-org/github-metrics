import { useFilters } from "@/hooks/use-filters";
import { WebhooksTable } from "@/components/dashboard";

export function WebhooksPage(): React.ReactElement {
  const { filters } = useFilters();

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Webhook Events</h2>
      <WebhooksTable
        pageSize={25}
        timeRange={filters.timeRange}
        repositories={filters.repositories}
      />
    </div>
  );
}
