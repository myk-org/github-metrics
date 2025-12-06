import React from "react";
import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";

interface DownloadButtonsProps {
  readonly data: readonly unknown[];
  readonly filename: string;
}

function downloadFile(content: string, filename: string, type: string): void {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function DownloadButtons({ data, filename }: DownloadButtonsProps): React.ReactElement {
  const downloadCSV = (): void => {
    if (data.length === 0) return;

    // Validate that first item is a plain object, fallback to safe headers if not
    const firstItem = data[0];
    let headers: string[];
    if (firstItem !== null && typeof firstItem === "object" && !Array.isArray(firstItem)) {
      headers = Object.keys(firstItem as Record<string, unknown>);
    } else {
      // Fallback for primitives: use single "value" header
      headers = ["value"];
    }

    // Escape headers the same way as values
    const csvHeaders = headers
      .map((header) => {
        return header.includes(",") ||
          header.includes('"') ||
          header.includes("\n") ||
          header.includes("\r")
          ? `"${header.replace(/"/g, '""')}"`
          : header;
      })
      .join(",");

    // Convert data to CSV rows
    const csvRows = data.map((row) => {
      return headers
        .map((header) => {
          let value: unknown;
          if (row !== null && typeof row === "object" && !Array.isArray(row)) {
            value = (row as Record<string, unknown>)[header];
          } else {
            // For primitives, use the row value directly
            value = row;
          }

          let stringValue: string;
          if (value === null || value === undefined) {
            stringValue = "";
          } else if (typeof value === "object") {
            stringValue = JSON.stringify(value);
          } else if (
            typeof value === "string" ||
            typeof value === "number" ||
            typeof value === "boolean"
          ) {
            stringValue = String(value);
          } else {
            stringValue = "";
          }
          // Escape quotes and wrap in quotes if contains comma, quote, or newline
          return stringValue.includes(",") ||
            stringValue.includes('"') ||
            stringValue.includes("\n") ||
            stringValue.includes("\r")
            ? `"${stringValue.replace(/"/g, '""')}"`
            : stringValue;
        })
        .join(",");
    });

    const csv = [csvHeaders, ...csvRows].join("\n");
    downloadFile(csv, `github_metrics_${filename}.csv`, "text/csv");
  };

  const downloadJSON = (): void => {
    const json = JSON.stringify(data, null, 2);
    downloadFile(json, `github_metrics_${filename}.json`, "application/json");
  };

  return (
    <div className="flex gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={downloadCSV}
        disabled={data.length === 0}
        title="Download as CSV"
      >
        <Download className="mr-1 h-3 w-3" />
        CSV
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={downloadJSON}
        disabled={data.length === 0}
        title="Download as JSON"
      >
        <Download className="mr-1 h-3 w-3" />
        JSON
      </Button>
    </div>
  );
}
