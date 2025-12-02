/**
 * Turnaround Metrics Module
 *
 * Handles loading and displaying review turnaround metrics on the Contributors page.
 *
 * Features:
 * - Loads data when Contributors page is shown
 * - Displays KPI cards with summary metrics
 * - Populates repository and reviewer tables
 * - Handles loading/error states
 * - Supports table sorting
 */

import { apiClient } from './api-client.js';

class TurnaroundMetrics {
    constructor() {
        console.log('[Turnaround] Constructor called');
        this.data = null;
        this.loadingElement = document.getElementById('turnaround-loading');
        this.errorElement = document.getElementById('turnaround-error');
        this.contentElement = document.getElementById('turnaround-content');

        // KPI elements
        this.kpiFirstReview = document.getElementById('kpi-first-review');
        this.kpiApproval = document.getElementById('kpi-approval');
        this.kpiLifecycle = document.getElementById('kpi-lifecycle');
        this.kpiTotalPrs = document.getElementById('kpi-total-prs');

        // Table bodies
        this.repoTableBody = document.getElementById('turnaround-by-repo-body');
        this.reviewerTableBody = document.getElementById('turnaround-by-reviewer-body');

        this.initialize();
    }

    /**
     * Initialize turnaround metrics
     */
    initialize() {
        console.log('[Turnaround] Initializing turnaround metrics');

        // Listen for page navigation to Contributors
        this.setupPageChangeListener();

        // Set up table sorting
        this.setupTableSorting();

        // Set up download buttons
        this.setupDownloadButtons();

        // Check if we should load metrics (handles direct navigation to #contributors)
        this.checkAndLoadMetrics();
    }

    /**
     * Check if we should load metrics and load them if conditions are met
     */
    checkAndLoadMetrics() {
        const hash = window.location.hash; // Full hash including #
        const currentHash = hash.slice(1) || 'overview'; // Remove # and default to overview

        console.log('[Turnaround] checkAndLoadMetrics - full hash:', hash, 'parsed:', currentHash);

        if (currentHash !== 'contributors') {
            console.log('[Turnaround] Not on contributors page, skipping initial load. Hash is:', currentHash);
            return;
        }

        // Check if time filters are ready
        const startTimeInput = document.getElementById('startTime');
        const endTimeInput = document.getElementById('endTime');

        console.log('[Turnaround] startTime:', startTimeInput?.value, 'endTime:', endTimeInput?.value);

        if (startTimeInput && startTimeInput.value && endTimeInput && endTimeInput.value) {
            console.log('[Turnaround] Time filters ready, loading metrics');
            this.loadMetrics();
        } else {
            console.log('[Turnaround] Time filters not ready, waiting...');
            // Retry after a short delay
            setTimeout(() => this.checkAndLoadMetrics(), 100);
        }
    }

    /**
     * Set up listener for page changes
     */
    setupPageChangeListener() {
        // Listen for hash changes - load metrics directly when navigating to contributors
        window.addEventListener('hashchange', () => {
            const hash = window.location.hash.slice(1);
            if (hash === 'contributors') {
                console.log('[Turnaround] Navigated to contributors page, loading metrics');
                this.loadMetrics();
            }
        });

        // Listen for time filter changes - always reload data when time changes
        // Listen for time filter updates from dashboard (custom event)
        document.addEventListener('timeFiltersUpdated', () => {
            const hash = window.location.hash.slice(1);
            if (hash === 'contributors') {
                console.log('[Turnaround] Time filters updated, refreshing metrics');
                this.loadMetrics();
            }
        });

        // Listen for repository filter changes with debounce
        let repoFilterTimeout = null;
        document.addEventListener('input', (e) => {
            if (e.target.id === 'repositoryFilter') {
                clearTimeout(repoFilterTimeout);
                repoFilterTimeout = setTimeout(() => {
                    const hash = window.location.hash.slice(1);
                    if (hash === 'contributors') {
                        console.log('[Turnaround] Repository filter changed, refreshing metrics');
                        this.loadMetrics();
                    }
                }, 300);
            }
        });

        // Listen for user filter changes with debounce
        let userFilterTimeout = null;
        document.addEventListener('input', (e) => {
            if (e.target.id === 'userFilter') {
                clearTimeout(userFilterTimeout);
                userFilterTimeout = setTimeout(() => {
                    const hash = window.location.hash.slice(1);
                    if (hash === 'contributors') {
                        console.log('[Turnaround] User filter changed, refreshing metrics');
                        this.loadMetrics();
                    }
                }, 300);
            }
        });
    }

    /**
     * Load turnaround metrics from API
     */
    async loadMetrics() {
        console.log('[Turnaround] Loading turnaround metrics');

        // Show loading state
        this.showLoading();

        try {
            // Get time filter values from the shared control panel
            const filters = this.getTimeFilters();
            console.log('[Turnaround] Using filters:', filters);

            // Fetch data from API with filters
            const response = await apiClient.fetchTurnaroundMetrics(filters);

            // Check for errors
            if (response.error) {
                this.showError(`Failed to load metrics: ${response.detail || response.error}`);
                return;
            }

            // Store data
            this.data = response;

            // Debug logging
            console.log('[Turnaround] Response received:', {
                hasSummary: !!response.summary,
                repositoryCount: response.by_repository?.length || 0,
                reviewerCount: response.by_reviewer?.length || 0
            });

            // Update UI
            this.updateKPIs(response.summary);
            this.updateRepositoryTable(response.by_repository || []);
            this.updateReviewerTable(response.by_reviewer || []);

            // Show content
            this.showContent();

        } catch (error) {
            console.error('[Turnaround] Error loading metrics:', error);
            this.showError(`Unexpected error: ${error.message}`);
        }
    }

    /**
     * Get time filter values from the shared control panel
     */
    getTimeFilters() {
        const startTimeInput = document.getElementById('startTime');
        const endTimeInput = document.getElementById('endTime');
        const repoInput = document.getElementById('repositoryFilter');
        const userInput = document.getElementById('userFilter');

        const filters = {};

        // Convert datetime-local input to ISO 8601 format
        if (startTimeInput && startTimeInput.value) {
            const startDate = new Date(startTimeInput.value);
            filters.start_time = startDate.toISOString();
        }

        if (endTimeInput && endTimeInput.value) {
            const endDate = new Date(endTimeInput.value);
            filters.end_time = endDate.toISOString();
        }

        // Add repository filter
        if (repoInput && repoInput.value) {
            filters.repository = repoInput.value;
        }

        // Add user filter
        if (userInput && userInput.value) {
            filters.user = userInput.value;
        }

        return filters;
    }

    /**
     * Update KPI cards with summary data
     */
    updateKPIs(summary) {
        if (!summary) {
            console.warn('[Turnaround] No summary data available');
            return;
        }

        // Update KPI values
        this.kpiFirstReview.textContent = this.formatHours(summary.avg_time_to_first_review_hours);
        this.kpiApproval.textContent = this.formatHours(summary.avg_time_to_approval_hours);
        this.kpiLifecycle.textContent = this.formatHours(summary.avg_pr_lifecycle_hours);
        this.kpiTotalPrs.textContent = summary.total_prs_analyzed || 0;
    }

    /**
     * Update repository table with data
     */
    updateRepositoryTable(repositories) {
        if (!this.repoTableBody) {
            console.warn('[Turnaround] Repository table body not found');
            return;
        }

        // Clear existing rows
        this.repoTableBody.innerHTML = '';

        // Handle empty data
        if (!repositories || repositories.length === 0) {
            this.repoTableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-secondary);">No data available</td></tr>';
            return;
        }

        // Populate table
        repositories.forEach(repo => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${this.escapeHtml(repo.repository)}</td>
                <td>${this.formatHours(repo.avg_time_to_first_review_hours)}</td>
                <td>${this.formatHours(repo.avg_time_to_approval_hours)}</td>
                <td>${this.formatHours(repo.avg_pr_lifecycle_hours)}</td>
                <td>${repo.total_prs}</td>
            `;
            this.repoTableBody.appendChild(row);
        });
    }

    /**
     * Update reviewer table with data
     */
    updateReviewerTable(reviewers) {
        if (!this.reviewerTableBody) {
            console.warn('[Turnaround] Reviewer table body not found');
            return;
        }

        // Clear existing rows
        this.reviewerTableBody.innerHTML = '';

        // Handle empty data
        if (!reviewers || reviewers.length === 0) {
            this.reviewerTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: var(--text-secondary);">No data available</td></tr>';
            return;
        }

        // Populate table
        reviewers.forEach(reviewer => {
            const row = document.createElement('tr');
            const repos = Array.isArray(reviewer.repositories_reviewed)
                ? reviewer.repositories_reviewed.join(', ')
                : reviewer.repositories_reviewed || '';

            row.innerHTML = `
                <td>${this.escapeHtml(reviewer.reviewer)}</td>
                <td>${this.formatHours(reviewer.avg_response_time_hours)}</td>
                <td>${reviewer.total_reviews}</td>
                <td title="${this.escapeHtml(repos)}">${this.truncateText(repos, 50)}</td>
            `;
            this.reviewerTableBody.appendChild(row);
        });
    }

    /**
     * Format hours for display in human-readable format
     */
    formatHours(hours) {
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
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Truncate text with ellipsis
     */
    truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return this.escapeHtml(text);
        return this.escapeHtml(text.substring(0, maxLength) + '...');
    }

    /**
     * Show loading state
     */
    showLoading() {
        if (this.loadingElement) this.loadingElement.style.display = 'flex';
        if (this.errorElement) this.errorElement.style.display = 'none';
        if (this.contentElement) this.contentElement.style.display = 'none';
    }

    /**
     * Show error state
     */
    showError(message) {
        if (this.errorElement) {
            const errorMessage = this.errorElement.querySelector('.error-message');
            if (errorMessage) {
                errorMessage.textContent = message;
            }
            this.errorElement.style.display = 'block';
        }
        if (this.loadingElement) this.loadingElement.style.display = 'none';
        if (this.contentElement) this.contentElement.style.display = 'none';
    }

    /**
     * Show content
     */
    showContent() {
        if (this.contentElement) this.contentElement.style.display = 'block';
        if (this.loadingElement) this.loadingElement.style.display = 'none';
        if (this.errorElement) this.errorElement.style.display = 'none';
    }

    /**
     * Set up table sorting
     */
    setupTableSorting() {
        // Repository table
        const repoTable = document.getElementById('turnaroundByRepoTable');
        if (repoTable) {
            this.setupTableSortingForTable(repoTable, 'by_repository');
        }

        // Reviewer table
        const reviewerTable = document.getElementById('turnaroundByReviewerTable');
        if (reviewerTable) {
            this.setupTableSortingForTable(reviewerTable, 'by_reviewer');
        }
    }

    /**
     * Set up sorting for a specific table
     */
    setupTableSortingForTable(table, dataKey) {
        const headers = table.querySelectorAll('th.sortable');
        headers.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                this.sortTable(table, dataKey, column);
            });
        });
    }

    /**
     * Sort table by column
     */
    sortTable(table, dataKey, column) {
        if (!this.data || !this.data[dataKey]) {
            return;
        }

        const headers = table.querySelectorAll('th.sortable');
        const clickedHeader = Array.from(headers).find(h => h.dataset.column === column);

        // Determine sort direction
        let direction = 'asc';
        if (clickedHeader.classList.contains('sort-asc')) {
            direction = 'desc';
        } else if (clickedHeader.classList.contains('sort-desc')) {
            direction = 'asc';
        }

        // Clear all sort indicators
        headers.forEach(h => {
            h.classList.remove('sort-asc', 'sort-desc');
        });

        // Set new sort indicator
        clickedHeader.classList.add(direction === 'asc' ? 'sort-asc' : 'sort-desc');

        // Sort data
        const sortedData = [...this.data[dataKey]].sort((a, b) => {
            const aVal = a[column];
            const bVal = b[column];

            // Handle null/undefined
            if (aVal === null || aVal === undefined) return 1;
            if (bVal === null || bVal === undefined) return -1;

            // Compare values
            if (typeof aVal === 'number' && typeof bVal === 'number') {
                return direction === 'asc' ? aVal - bVal : bVal - aVal;
            } else {
                const aStr = String(aVal).toLowerCase();
                const bStr = String(bVal).toLowerCase();
                return direction === 'asc'
                    ? aStr.localeCompare(bStr)
                    : bStr.localeCompare(aStr);
            }
        });

        // Update table
        if (dataKey === 'by_repository') {
            this.updateRepositoryTable(sortedData);
        } else if (dataKey === 'by_reviewer') {
            this.updateReviewerTable(sortedData);
        }
    }

    /**
     * Set up download buttons
     */
    setupDownloadButtons() {
        // Repository download buttons
        const repoButtons = document.querySelectorAll('[data-section="turnaroundByRepo"]');
        repoButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const format = e.currentTarget.dataset.format;
                this.downloadData('by_repository', 'turnaround_by_repository', format);
            });
        });

        // Reviewer download buttons
        const reviewerButtons = document.querySelectorAll('[data-section="turnaroundByReviewer"]');
        reviewerButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const format = e.currentTarget.dataset.format;
                this.downloadData('by_reviewer', 'turnaround_by_reviewer', format);
            });
        });
    }

    /**
     * Download data as CSV or JSON
     */
    downloadData(dataKey, filename, format) {
        if (!this.data || !this.data[dataKey]) {
            console.warn('[Turnaround] No data available for download');
            return;
        }

        const data = this.data[dataKey];

        if (format === 'csv') {
            this.downloadCSV(data, filename);
        } else if (format === 'json') {
            this.downloadJSON(data, filename);
        }
    }

    /**
     * Sanitize CSV values to prevent formula injection
     */
    sanitizeCSVValue(value) {
        const str = String(value || '');
        const escaped = str.replace(/"/g, '""');
        // Prefix dangerous characters with single quote
        if (/^[=+\-@]/.test(escaped)) {
            return "'" + escaped;
        }
        return escaped;
    }

    /**
     * Download data as CSV
     */
    downloadCSV(data, filename) {
        if (!data || data.length === 0) {
            console.warn('[Turnaround] No data to download');
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
                // Handle arrays (e.g., repositories_reviewed)
                if (Array.isArray(value)) {
                    const arrayStr = value.join('; ');
                    return `"${this.sanitizeCSVValue(arrayStr)}"`;
                }
                // Sanitize and escape quotes and wrap in quotes if contains comma
                const sanitized = this.sanitizeCSVValue(value);
                return sanitized.includes(',') ? `"${sanitized}"` : sanitized;
            });
            csvRows.push(values.join(','));
        });

        // Create blob and download
        const csvContent = csvRows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        this.downloadBlob(blob, `${filename}.csv`);
    }

    /**
     * Download data as JSON
     */
    downloadJSON(data, filename) {
        const jsonContent = JSON.stringify(data, null, 2);
        const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
        this.downloadBlob(blob, `${filename}.json`);
    }

    /**
     * Download blob as file
     */
    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
}

// Initialize turnaround metrics when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.turnaroundMetrics = new TurnaroundMetrics();
    });
} else {
    window.turnaroundMetrics = new TurnaroundMetrics();
}

// Export for module usage
export { TurnaroundMetrics };
