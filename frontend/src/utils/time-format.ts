import type { DateFormat } from "@/context/date-format-context";

/**
 * Format hours into human-readable format.
 *
 * @param hours - Number of hours to format (accepts string for API backwards compatibility)
 * @returns Formatted string (e.g., "6m", "2.4h", "2.1d")
 *          Negative values are prefixed with "-" (e.g., "-30m" means 30 minutes early)
 *
 * @example
 * formatHours(0.1) // "6m"
 * formatHours(2.4) // "2.4h"
 * formatHours(39.4) // "1.6d"
 * formatHours(-1) // "-1.0h" (resolved 1 hour before CI check)
 * formatHours(-0.5) // "-30m" (resolved 30 minutes early)
 * formatHours(null) // "-"
 */
export function formatHours(hours: number | string | null | undefined): string {
  // Handle string numbers from API (defensive, for backwards compatibility)
  const numericHours = typeof hours === "string" ? parseFloat(hours) : hours;

  if (typeof numericHours !== "number" || Number.isNaN(numericHours)) {
    return "-";
  }

  // Handle negative values - show as negative time
  const isNegative = numericHours < 0;
  const absHours = Math.abs(numericHours);
  const prefix = isNegative ? "-" : "";

  if (absHours < 1) {
    const minutes = Math.round(absHours * 60);
    return `${prefix}${String(minutes)}m`;
  }
  if (absHours < 24) {
    const formattedHours = absHours.toFixed(1);
    return `${prefix}${formattedHours}h`;
  }
  const days = (absHours / 24).toFixed(1);
  return `${prefix}${days}d`;
}

/**
 * Format timestamp into relative time (e.g., "2 hours ago", "3 days ago").
 *
 * @param timestamp - ISO timestamp string
 * @returns Relative time string
 *
 * @example
 * formatRelativeTime("2024-01-01T12:00:00Z") // "2 hours ago"
 * formatRelativeTime("2024-01-01T00:00:00Z") // "3 days ago"
 */
export function formatRelativeTime(timestamp: string): string {
  const now = new Date();
  const then = new Date(timestamp);
  const diffMs = now.getTime() - then.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);
  const diffWeek = Math.floor(diffDay / 7);
  const diffMonth = Math.floor(diffDay / 30);
  const diffYear = Math.floor(diffDay / 365);

  if (diffYear > 0) {
    return `${String(diffYear)} year${diffYear > 1 ? "s" : ""} ago`;
  }
  if (diffMonth > 0) {
    return `${String(diffMonth)} month${diffMonth > 1 ? "s" : ""} ago`;
  }
  if (diffWeek > 0) {
    return `${String(diffWeek)} week${diffWeek > 1 ? "s" : ""} ago`;
  }
  if (diffDay > 0) {
    return `${String(diffDay)} day${diffDay > 1 ? "s" : ""} ago`;
  }
  if (diffHour > 0) {
    return `${String(diffHour)} hour${diffHour > 1 ? "s" : ""} ago`;
  }
  if (diffMin > 0) {
    return `${String(diffMin)} minute${diffMin > 1 ? "s" : ""} ago`;
  }
  return "just now";
}

/**
 * Format timestamp into absolute time for display.
 *
 * @param timestamp - ISO timestamp string
 * @returns Formatted absolute timestamp
 *
 * @example
 * formatAbsoluteTime("2024-01-01T12:00:00Z") // "Jan 1, 2024, 12:00 PM"
 */
export function formatAbsoluteTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

/**
 * Format timestamp into date string respecting user's date format preference.
 */
export function formatDate(timestamp: string, dateFormat: DateFormat = "MM/DD"): string {
  const date = new Date(timestamp);
  const locale = dateFormat === "DD/MM" ? "en-GB" : "en-US";
  return date.toLocaleDateString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Format timestamp into date+time string respecting user's date format preference.
 */
export function formatDateTime(timestamp: string, dateFormat: DateFormat = "MM/DD"): string {
  const date = new Date(timestamp);
  const locale = dateFormat === "DD/MM" ? "en-GB" : "en-US";
  return date.toLocaleString(locale, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}
