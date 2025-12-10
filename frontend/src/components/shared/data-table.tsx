import { useState } from "react";
import type { ReactNode, ReactElement } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface ColumnDef<T> {
  readonly key: string;
  readonly label: string;
  readonly sortable?: boolean;
  readonly align?: "left" | "center" | "right";
  readonly render?: (item: T) => ReactNode;
  readonly getValue?: (item: T) => string | number;
}

interface DataTableProps<T> {
  readonly columns: readonly ColumnDef<T>[];
  readonly data: readonly T[] | undefined;
  readonly isLoading: boolean;
  readonly keyExtractor: (item: T) => string | number;
  readonly onRowClick?: (item: T) => void;
  readonly emptyMessage?: string;
  readonly skeletonRows?: number;
}

type SortDirection = "asc" | "desc" | null;

const getAlignClass = (align: ColumnDef<unknown>["align"]): string => {
  if (align === "right") return "text-right";
  if (align === "center") return "text-center";
  return "";
};

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  isLoading,
  keyExtractor,
  onRowClick,
  emptyMessage = "No data available",
  skeletonRows = 5,
}: DataTableProps<T>): ReactElement {
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>(null);

  const handleSort = (columnKey: string): void => {
    if (sortColumn === columnKey) {
      // Cycle through: asc -> desc -> null
      if (sortDirection === "asc") {
        setSortDirection("desc");
      } else if (sortDirection === "desc") {
        setSortColumn(null);
        setSortDirection(null);
      }
    } else {
      setSortColumn(columnKey);
      setSortDirection("asc");
    }
  };

  const getSortedData = (): readonly T[] => {
    // Ensure data is always an array - explicitly type as T[]
    const safeData: readonly T[] = Array.isArray(data) ? data : [];

    if (safeData.length === 0 || !sortColumn || !sortDirection) {
      return safeData;
    }

    const column = columns.find((c) => c.key === sortColumn);
    if (!column) {
      return safeData;
    }

    const getValue = column.getValue ?? ((item: T) => item[column.key]);

    return [...safeData].sort((a: T, b: T) => {
      const aVal = getValue(a);
      const bVal = getValue(b);

      if (typeof aVal === "number" && typeof bVal === "number") {
        return sortDirection === "asc" ? aVal - bVal : bVal - aVal;
      }

      const aStr = String(aVal);
      const bStr = String(bVal);
      const comparison = aStr.localeCompare(bStr);
      return sortDirection === "asc" ? comparison : -comparison;
    });
  };

  const sortedData = getSortedData();

  if (isLoading) {
    return (
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((column) => (
              <TableHead key={column.key} className={getAlignClass(column.align)}>
                {column.label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {Array.from({ length: skeletonRows }).map((_, i) => (
            <TableRow key={i}>
              {columns.map((column) => (
                <TableCell key={column.key}>
                  <Skeleton className="h-4 w-full" />
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((column) => (
            <TableHead
              key={column.key}
              className={getAlignClass(column.align)}
              aria-sort={
                column.sortable !== false
                  ? sortColumn === column.key
                    ? sortDirection === "asc"
                      ? "ascending"
                      : sortDirection === "desc"
                        ? "descending"
                        : "none"
                    : "none"
                  : undefined
              }
            >
              {column.sortable !== false ? (
                <Button
                  variant="ghost"
                  onClick={() => {
                    handleSort(column.key);
                  }}
                  className="h-auto p-0 font-semibold hover:bg-transparent"
                  aria-label={
                    sortColumn === column.key
                      ? `Sort by ${column.label}, currently ${sortDirection === "asc" ? "ascending" : "descending"}`
                      : `Sort by ${column.label}`
                  }
                >
                  {column.label}
                  <span className="ml-2">
                    {sortColumn === column.key ? (
                      sortDirection === "asc" ? (
                        <ArrowUp className="h-4 w-4" />
                      ) : (
                        <ArrowDown className="h-4 w-4" />
                      )
                    ) : (
                      <ArrowUpDown className="h-4 w-4 opacity-50" />
                    )}
                  </span>
                </Button>
              ) : (
                column.label
              )}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedData.length === 0 ? (
          <TableRow>
            <TableCell colSpan={columns.length} className="text-center text-muted-foreground py-8">
              {emptyMessage}
            </TableCell>
          </TableRow>
        ) : (
          sortedData.map((item) => (
            <TableRow
              key={String(keyExtractor(item))}
              onClick={
                onRowClick
                  ? () => {
                      onRowClick(item);
                    }
                  : undefined
              }
              className={onRowClick ? "cursor-pointer hover:bg-muted/50" : ""}
            >
              {columns.map((column) => (
                <TableCell key={column.key} className={getAlignClass(column.align)}>
                  {column.render
                    ? column.render(item)
                    : (() => {
                        const value = column.getValue ? column.getValue(item) : item[column.key];
                        if (value === null || value === undefined) {
                          return "";
                        }
                        if (typeof value === "object") {
                          return JSON.stringify(value);
                        }
                        if (
                          typeof value === "string" ||
                          typeof value === "number" ||
                          typeof value === "boolean"
                        ) {
                          return String(value);
                        }
                        return "";
                      })()}
                </TableCell>
              ))}
            </TableRow>
          ))
        )}
      </TableBody>
    </Table>
  );
}
