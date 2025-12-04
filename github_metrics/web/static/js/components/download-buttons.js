/**
 * Reusable DownloadButtons Component
 *
 * Provides CSV and JSON download functionality for dashboard data.
 * Handles CSV sanitization to prevent formula injection.
 *
 * Usage:
 *   const downloadButtons = new DownloadButtons({
 *     container: document.getElementById('download-container'),
 *     section: 'pull-requests',
 *     getData: () => this.data.pull_requests
 *   });
 *
 * Container HTML Example:
 *   <div id="download-container"></div>
 *
 * Features:
 *   - CSV download with formula injection prevention
 *   - JSON download with pretty printing
 *   - Array field handling (joins with semicolons in CSV)
 *   - Auto-generated filenames with timestamps
 *   - Blob download pattern for browser compatibility
 *
 * CSV Sanitization:
 *   - Escapes double quotes by doubling them
 *   - Prefixes dangerous characters (=, +, -, @) with single quote
 *   - Wraps fields containing commas in quotes
 *   - Handles arrays by joining with semicolons
 */

export class DownloadButtons {
    // Delay before revoking object URL (allows time for download to start)
    static URL_REVOKE_DELAY_MS = 100;

    /**
     * Initialize the download buttons component.
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.container - Container element to render buttons into
     * @param {string} options.section - Section name for filenames (e.g., 'pull-requests')
     * @param {Function} options.getData - Function that returns data array to download
     */
    constructor(options) {
        this.container = options.container;
        this.section = options.section || 'data';
        this.getData = options.getData || (() => []);

        this.render();
        this.bindEvents();
    }

    /**
     * Render download buttons into container.
     */
    render() {
        if (!this.container) {
            console.warn('[DownloadButtons] Container element not found');
            return;
        }

        this.container.innerHTML = `
            <div class="download-buttons">
                <button class="download-btn csv-btn" data-format="csv">
                    📥 CSV
                </button>
                <button class="download-btn json-btn" data-format="json">
                    📥 JSON
                </button>
            </div>
        `;
    }

    /**
     * Bind click events to download buttons.
     */
    bindEvents() {
        if (!this.container) return;

        const csvBtn = this.container.querySelector('.csv-btn');
        const jsonBtn = this.container.querySelector('.json-btn');

        if (csvBtn) {
            csvBtn.addEventListener('click', () => this.handleDownload('csv'));
        }

        if (jsonBtn) {
            jsonBtn.addEventListener('click', () => this.handleDownload('json'));
        }
    }

    /**
     * Handle download button click.
     * @param {string} format - Download format ('csv' or 'json')
     */
    handleDownload(format) {
        let data;
        try {
            data = this.getData();
        } catch (error) {
            console.error('[DownloadButtons] Error retrieving data:', error);

            window.alert('Failed to retrieve data for download. Please try again.');
            return;
        }

        if (!data || data.length === 0) {
            console.warn('[DownloadButtons] No data available for download');
            return;
        }

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const filename = `${this.section}_${timestamp}`;

        if (format === 'csv') {
            this.downloadCSV(data, filename);
        } else if (format === 'json') {
            this.downloadJSON(data, filename);
        }
    }

    /**
     * Sanitize CSV values to prevent formula injection.
     * Escapes quotes and prefixes dangerous characters with single quote.
     * @param {*} value - Value to sanitize
     * @returns {string} Sanitized value
     */
    sanitizeCSVValue(value) {
        const str = String(value || '');
        // Escape quotes by doubling them
        const escaped = str.replace(/"/g, '""');
        // Prefix dangerous characters with single quote to prevent formula injection
        if (/^[=+\-@]/.test(escaped)) {
            return "'" + escaped;
        }
        return escaped;
    }

    /**
     * Download data as CSV.
     * @param {Array} data - Array of objects to download
     * @param {string} filename - Base filename (without extension)
     */
    downloadCSV(data, filename) {
        if (!data || data.length === 0) {
            console.warn('[DownloadButtons] No data to download');
            return;
        }

        // Get headers from first object
        const headers = Object.keys(data[0]);
        const csvRows = [];

        // Add header row
        csvRows.push(headers.join(','));

        // Add data rows
        data.forEach(row => {
            const values = headers.map(header => {
                const value = row[header];

                // Handle arrays (e.g., repositories_reviewed, labels)
                if (Array.isArray(value)) {
                    const arrayStr = value.join('; ');
                    return `"${this.sanitizeCSVValue(arrayStr)}"`;
                }

                // Sanitize and escape quotes, wrap in quotes if contains comma or if sanitized
                const sanitized = this.sanitizeCSVValue(value);
                const needsQuotes = sanitized.includes(',') || sanitized !== String(value || '');
                return needsQuotes ? `"${sanitized}"` : sanitized;
            });
            csvRows.push(values.join(','));
        });

        // Create blob and download
        const csvContent = csvRows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        this.downloadBlob(blob, `${filename}.csv`);
    }

    /**
     * Download data as JSON.
     * @param {Array} data - Array of objects to download
     * @param {string} filename - Base filename (without extension)
     */
    downloadJSON(data, filename) {
        const jsonContent = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
        this.downloadBlob(blob, `${filename}.json`);
    }

    /**
     * Download blob as file.
     * Creates temporary link, triggers download, and cleans up.
     * @param {Blob} blob - Blob to download
     * @param {string} filename - Filename with extension
     */
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        // Delay URL.revokeObjectURL to ensure download starts
        setTimeout(() => URL.revokeObjectURL(url), DownloadButtons.URL_REVOKE_DELAY_MS);
    }
}
