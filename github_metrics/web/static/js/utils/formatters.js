/**
 * Shared Formatting Utilities
 *
 * Common formatting functions used across metrics modules.
 */

/**
 * Format hours for display in human-readable format
 */
export function formatHours(hours) {
    if (hours === null || hours === undefined) {
        return 'N/A';
    }

    const num = parseFloat(hours);
    if (isNaN(num)) {
        return 'N/A';
    }

    // Less than 1 hour: show minutes
    if (num < 1) {
        const minutes = Math.round(num * 60);
        return `${minutes}m`;
    }

    // 1-24 hours: show hours
    if (num < 24) {
        return `${num.toFixed(1)}h`;
    }

    // 24-168 hours (1 week): show days and hours
    if (num < 168) {
        const days = Math.floor(num / 24);
        const remainingHours = Math.round(num % 24);
        return remainingHours > 0 ? `${days}d ${remainingHours}h` : `${days}d`;
    }

    // 168+ hours: show weeks and days
    const weeks = Math.floor(num / 168);
    const remainingDays = Math.floor((num % 168) / 24);
    return remainingDays > 0 ? `${weeks}w ${remainingDays}d` : `${weeks}w`;
}

/**
 * Format timestamp for display
 */
export function formatTimestamp(timestamp) {
    try {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(diff / 3600000);
        const days = Math.floor(diff / 86400000);

        if (minutes < 1) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        if (days < 7) return `${days}d ago`;

        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
        return timestamp;
    }
}

/**
 * Escape HTML to prevent XSS
 */
export function escapeHtml(text) {
    if (!text) return '';
    // Use shared utility if available
    if (window.MetricsUtils?.escapeHTML) {
        return window.MetricsUtils.escapeHTML(text);
    }
    // Fallback: use DOM createElement approach
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
