import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface PaginationControlsProps {
  readonly currentPage: number;
  readonly totalPages: number;
  readonly pageSize?: number;
  readonly onPageChange: (page: number) => void;
  readonly onPageSizeChange?: (size: number) => void;
}

export function PaginationControls({
  currentPage,
  totalPages,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: PaginationControlsProps): React.ReactElement {
  return (
    <div className="flex items-center gap-4">
      {pageSize !== undefined && onPageSizeChange && (
        <Select
          value={String(pageSize)}
          onValueChange={(value) => {
            onPageSizeChange(Number(value));
          }}
        >
          <SelectTrigger className="h-9 w-[140px]" aria-label="Rows per page">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="10">10 per page</SelectItem>
            <SelectItem value="25">25 per page</SelectItem>
            <SelectItem value="50">50 per page</SelectItem>
            <SelectItem value="100">100 per page</SelectItem>
          </SelectContent>
        </Select>
      )}

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            onPageChange(currentPage - 1);
          }}
          disabled={currentPage <= 1}
          aria-label="Previous page"
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <span className="text-sm text-muted-foreground">
          Page {currentPage} of {totalPages}
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            onPageChange(currentPage + 1);
          }}
          disabled={currentPage >= totalPages}
          aria-label="Next page"
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
