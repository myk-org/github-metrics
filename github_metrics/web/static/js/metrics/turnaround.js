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
import { Pagination } from '../components/pagination.js';
import { SortableTable } from '../components/sortable-table.js';
import { DownloadButtons } from '../components/download-buttons.js';
import { Modal } from '../components/modal.js';

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

        // Contributor metrics table bodies
        this.prCreatorsTableBody = document.getElementById('pr-creators-metrics-body');
        this.prReviewersTableBody = document.getElementById('pr-reviewers-metrics-body');
        this.prApproversTableBody = document.getElementById('pr-approvers-metrics-body');
        this.prLgtmTableBody = document.getElementById('pr-lgtm-metrics-body');

        // SortableTable instances
        this.sortableTables = {
            by_repository: null,
            by_reviewer: null,
            pr_creators: null,
            pr_reviewers: null,
            pr_approvers: null,
            pr_lgtm: null
        };

        // Contributor metrics data and pagination state
        this.contributorMetrics = {
            pr_creators: { data: [], pagination: null, currentPage: 1, paginationComponent: null },
            pr_reviewers: { data: [], pagination: null, currentPage: 1, paginationComponent: null },
            pr_approvers: { data: [], pagination: null, currentPage: 1, paginationComponent: null },
            pr_lgtm: { data: [], pagination: null, currentPage: 1, paginationComponent: null }
        };

        // User PRs modal state with pagination
        this.userPrsPagination = {
            username: null,
            category: null,
            allPrs: [], // Store all PRs
            currentPage: 1,
            pageSize: 10,
            paginationComponent: null
        };

        // Filter timeouts for debouncing
        this.filterTimeouts = {
            repo: null,
            user: null
        };

        this.initialize();
    }

    /**
     * Initialize turnaround metrics
     */
    initialize() {
        console.log('[Turnaround] Initializing turnaround metrics');

        // Listen for page navigation to Contributors
        this.setupPageChangeListener();

        // Initialize SortableTable instances
        this.initializeSortableTables();

        // Set up download buttons (using DownloadButtons component)
        this.setupDownloadButtons();

        // Set up contributor metrics pagination
        this.setupContributorPagination();

        // Initialize modal component for user PRs
        this.initializeUserPrsModal();

        // Check if we should load metrics (handles direct navigation to #contributors)
        this.checkAndLoadMetrics();
    }

    /**
     * Initialize the user PRs modal using Modal component
     */
    initializeUserPrsModal() {
        this.userPrsModal = new Modal({
            id: 'userPrsModal',
            onOpen: (data) => {
                console.log('[Turnaround] User PRs modal opened with data:', data);
            },
            onClose: () => {
                console.log('[Turnaround] User PRs modal closed');
            },
            closeOnOverlay: true,
            closeOnEscape: true
        });
    }

    /**
     * Check if we should load metrics and load them if conditions are met
     */
    checkAndLoadMetrics(retryCount = 0) {
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
            // Retry after a short delay with max attempts
            const maxRetries = 50; // 50 retries * 100ms = 5 seconds
            if (retryCount < maxRetries) {
                setTimeout(() => this.checkAndLoadMetrics(retryCount + 1), 100);
            } else {
                console.error('[Turnaround] Max retry attempts reached. Time filters failed to initialize.');
            }
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

        // Listen for repository and user filter changes with debounce
        document.addEventListener('input', (e) => {
            if (e.target.id === 'repositoryFilter') {
                clearTimeout(this.filterTimeouts.repo);
                this.filterTimeouts.repo = setTimeout(() => {
                    const hash = window.location.hash.slice(1);
                    if (hash === 'contributors') {
                        console.log('[Turnaround] Repository filter changed, refreshing metrics');
                        this.loadMetrics();
                    }
                }, 300);
            } else if (e.target.id === 'userFilter') {
                clearTimeout(this.filterTimeouts.user);
                this.filterTimeouts.user = setTimeout(() => {
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

            // Update SortableTable instances with new data
            if (this.sortableTables.by_repository) {
                this.sortableTables.by_repository.update(response.by_repository || []);
            }
            if (this.sortableTables.by_reviewer) {
                this.sortableTables.by_reviewer.update(response.by_reviewer || []);
            }

            // Load contributor metrics (each category separately)
            await this.loadContributorMetrics();

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
        // Use shared utility if available
        if (window.MetricsUtils?.escapeHTML) {
            return window.MetricsUtils.escapeHTML(text);
        }
        // Fallback: use DOM createElement approach
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
     * Initialize SortableTable instances for all tables
     */
    initializeSortableTables() {
        // Table configurations with column types
        const tableConfigs = {
            by_repository: {
                tableId: 'turnaroundByRepoTable',
                columns: {
                    repository: { type: 'string' },
                    avg_time_to_first_review_hours: { type: 'number' },
                    avg_time_to_approval_hours: { type: 'number' },
                    avg_pr_lifecycle_hours: { type: 'number' },
                    total_prs: { type: 'number' }
                }
            },
            by_reviewer: {
                tableId: 'turnaroundByReviewerTable',
                columns: {
                    reviewer: { type: 'string' },
                    avg_response_time_hours: { type: 'number' },
                    total_reviews: { type: 'number' },
                    repositories_reviewed: { type: 'string' }
                }
            },
            pr_creators: {
                tableId: 'prCreatorsMetricsTable',
                columns: {
                    user: { type: 'string' },
                    total_prs: { type: 'number' },
                    merged_prs: { type: 'number' },
                    closed_prs: { type: 'number' },
                    avg_commits_per_pr: { type: 'number' }
                }
            },
            pr_reviewers: {
                tableId: 'prReviewersMetricsTable',
                columns: {
                    user: { type: 'string' },
                    total_reviews: { type: 'number' },
                    prs_reviewed: { type: 'number' },
                    avg_reviews_per_pr: { type: 'number' }
                }
            },
            pr_approvers: {
                tableId: 'prApproversMetricsTable',
                columns: {
                    user: { type: 'string' },
                    total_approvals: { type: 'number' },
                    prs_approved: { type: 'number' }
                }
            },
            pr_lgtm: {
                tableId: 'prLgtmMetricsTable',
                columns: {
                    user: { type: 'string' },
                    total_lgtm: { type: 'number' },
                    prs_lgtm: { type: 'number' }
                }
            }
        };

        Object.keys(tableConfigs).forEach(key => {
            const config = tableConfigs[key];
            const table = document.getElementById(config.tableId);

            if (!table) {
                console.warn(`[Turnaround] Table not found: ${config.tableId}`);
                return;
            }

            // Get initial data
            const data = this.getTableData(key);

            // Initialize SortableTable instance
            this.sortableTables[key] = new SortableTable({
                table: table,
                data: data,
                columns: config.columns,
                onSort: (sortedData, column, direction) => {
                    console.log(`[Turnaround] Table ${key} sorted by ${column} ${direction}`);
                    this.handleTableSorted(key, sortedData);
                }
            });

            console.log(`[Turnaround] SortableTable initialized for ${key}`);
        });
    }

    /**
     * Get table data for a given key
     * @param {string} key - Data key
     * @returns {Array} Table data
     */
    getTableData(key) {
        if (key === 'by_repository') {
            return this.data?.by_repository || [];
        } else if (key === 'by_reviewer') {
            return this.data?.by_reviewer || [];
        } else if (key.startsWith('pr_')) {
            return this.contributorMetrics[key]?.data || [];
        }
        return [];
    }

    /**
     * Handle table sorted callback - update the appropriate table with sorted data
     * @param {string} key - Table key
     * @param {Array} sortedData - Sorted data array
     */
    handleTableSorted(key, sortedData) {
        if (key === 'by_repository') {
            this.updateRepositoryTable(sortedData);
        } else if (key === 'by_reviewer') {
            this.updateReviewerTable(sortedData);
        } else if (key.startsWith('pr_')) {
            // Store sorted data and re-render contributor table
            this.contributorMetrics[key].data = sortedData;
            this.updateContributorTable(key);
        }
    }

    /**
     * Set up download buttons using DownloadButtons component
     */
    setupDownloadButtons() {
        this.downloadButtons = {};

        // Repository table
        const repoContainer = document.querySelector('[data-section="turnaround-by-repo"] .table-controls');
        if (repoContainer) {
            this.downloadButtons.byRepository = new DownloadButtons({
                container: repoContainer,
                section: 'turnaround_by_repository',
                getData: () => this.data?.by_repository || []
            });
        }

        // Reviewer table
        const reviewerContainer = document.querySelector('[data-section="turnaround-by-reviewer"] .table-controls');
        if (reviewerContainer) {
            this.downloadButtons.byReviewer = new DownloadButtons({
                container: reviewerContainer,
                section: 'turnaround_by_reviewer',
                getData: () => this.data?.by_reviewer || []
            });
        }

        // PR Creators
        const creatorsContainer = document.querySelector('[data-section="pr-creators-metrics"] .table-controls');
        if (creatorsContainer) {
            this.downloadButtons.prCreators = new DownloadButtons({
                container: creatorsContainer,
                section: 'pr_creators',
                getData: () => this.contributorMetrics.pr_creators.data
            });
        }

        // PR Reviewers
        const reviewersContainer = document.querySelector('[data-section="pr-reviewers-metrics"] .table-controls');
        if (reviewersContainer) {
            this.downloadButtons.prReviewers = new DownloadButtons({
                container: reviewersContainer,
                section: 'pr_reviewers',
                getData: () => this.contributorMetrics.pr_reviewers.data
            });
        }

        // PR Approvers
        const approversContainer = document.querySelector('[data-section="pr-approvers-metrics"] .table-controls');
        if (approversContainer) {
            this.downloadButtons.prApprovers = new DownloadButtons({
                container: approversContainer,
                section: 'pr_approvers',
                getData: () => this.contributorMetrics.pr_approvers.data
            });
        }

        // PR LGTM
        const lgtmContainer = document.querySelector('[data-section="pr-lgtm-metrics"] .table-controls');
        if (lgtmContainer) {
            this.downloadButtons.prLgtm = new DownloadButtons({
                container: lgtmContainer,
                section: 'pr_lgtm',
                getData: () => this.contributorMetrics.pr_lgtm.data
            });
        }
    }

    /**
     * Load contributor metrics from API
     */
    async loadContributorMetrics() {
        console.log('[Turnaround] Loading contributor metrics');

        // Get filters
        const filters = this.getTimeFilters();

        // Fetch all contributor categories in parallel
        await Promise.all([
            this.loadContributorCategory('pr_creators', filters),
            this.loadContributorCategory('pr_reviewers', filters),
            this.loadContributorCategory('pr_approvers', filters),
            this.loadContributorCategory('pr_lgtm', filters)
        ]);
    }

    /**
     * Load a specific contributor category
     */
    async loadContributorCategory(category, filters = {}) {
        try {
            const page = this.contributorMetrics[category].currentPage;
            const categoryPrefix = this.getCategoryPrefix(category);

            // Get page size from select element (default to 10 if not found)
            const pageSizeSelect = document.querySelector(`.page-size-select[data-section="${categoryPrefix}"]`);
            const pageSize = pageSizeSelect ? parseInt(pageSizeSelect.value, 10) : 10;

            const params = {
                ...filters,
                page: page,
                page_size: pageSize
            };

            console.log(`[Turnaround] Fetching ${category} metrics, page ${page}, page_size ${pageSize}`);

            const response = await apiClient.fetchContributors(
                params.start_time,
                params.end_time,
                pageSize,
                {
                    repository: params.repository,
                    user: params.user,
                    page: params.page,
                    page_size: params.page_size
                }
            );

            if (response.error) {
                console.error(`[Turnaround] Error loading ${category}:`, response.error);
                this.showContributorCategoryError(category, response.detail || response.error);
                return;
            }

            // Store data and pagination
            this.contributorMetrics[category].data = response[category]?.data || [];
            this.contributorMetrics[category].pagination = response[category]?.pagination || null;

            console.log(`[Turnaround] ${category} loaded:`, {
                count: this.contributorMetrics[category].data.length,
                pagination: this.contributorMetrics[category].pagination
            });

            // Update table
            this.updateContributorTable(category);
            this.updateContributorPagination(category);

            // Update SortableTable instance with new data
            if (this.sortableTables[category]) {
                this.sortableTables[category].update(this.contributorMetrics[category].data);
            }

        } catch (error) {
            console.error(`[Turnaround] Error loading ${category}:`, error);
            this.showContributorCategoryError(category, error.message);
        }
    }

    /**
     * Update contributor table with data
     */
    updateContributorTable(category) {
        const tableBodyMap = {
            pr_creators: this.prCreatorsTableBody,
            pr_reviewers: this.prReviewersTableBody,
            pr_approvers: this.prApproversTableBody,
            pr_lgtm: this.prLgtmTableBody
        };

        const tableBody = tableBodyMap[category];
        if (!tableBody) {
            console.warn(`[Turnaround] Table body not found for ${category}`);
            return;
        }

        const data = this.contributorMetrics[category].data;

        // Clear existing rows
        tableBody.innerHTML = '';

        // Handle empty data
        if (!data || data.length === 0) {
            const colspan = category === 'pr_creators' ? 5 : category === 'pr_reviewers' ? 4 : 3;
            tableBody.innerHTML = `<tr><td colspan="${colspan}" style="text-align: center; padding: 20px; color: var(--text-secondary);">No data available</td></tr>`;
            return;
        }

        // Populate table based on category
        data.forEach(item => {
            const row = document.createElement('tr');

            if (category === 'pr_creators') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${this.escapeHtml(item.user)}" data-category="${category}">${this.escapeHtml(item.user)}</a></td>
                    <td>${item.total_prs || 0}</td>
                    <td>${item.merged_prs || 0}</td>
                    <td>${item.closed_prs || 0}</td>
                    <td>${item.avg_commits_per_pr ? parseFloat(item.avg_commits_per_pr).toFixed(1) : '0.0'}</td>
                `;
            } else if (category === 'pr_reviewers') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${this.escapeHtml(item.user)}" data-category="${category}">${this.escapeHtml(item.user)}</a></td>
                    <td>${item.total_reviews || 0}</td>
                    <td>${item.prs_reviewed || 0}</td>
                    <td>${item.avg_reviews_per_pr ? parseFloat(item.avg_reviews_per_pr).toFixed(1) : '0.0'}</td>
                `;
            } else if (category === 'pr_approvers') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${this.escapeHtml(item.user)}" data-category="${category}">${this.escapeHtml(item.user)}</a></td>
                    <td>${item.total_approvals || 0}</td>
                    <td>${item.prs_approved || 0}</td>
                `;
            } else if (category === 'pr_lgtm') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${this.escapeHtml(item.user)}" data-category="${category}">${this.escapeHtml(item.user)}</a></td>
                    <td>${item.total_lgtm || 0}</td>
                    <td>${item.prs_lgtm || 0}</td>
                `;
            }

            tableBody.appendChild(row);
        });

        // Set up click handlers for usernames
        this.setupUsernameClickHandlers(tableBody);
    }

    /**
     * Set up click handlers for usernames
     */
    setupUsernameClickHandlers(tableBody) {
        const usernameLinks = tableBody.querySelectorAll('.clickable-username');
        console.log(`[Turnaround] Setting up click handlers for ${usernameLinks.length} username links`);
        usernameLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                console.log('[Turnaround] Username link clicked:', e.currentTarget);
                console.log('[Turnaround] data-username value:', e.currentTarget.dataset.username);
                e.preventDefault();
                e.stopPropagation(); // Prevent dashboard.js global handler from firing
                const username = e.currentTarget.dataset.username;
                const category = e.currentTarget.dataset.category;
                if (username) {
                    console.log(`[Turnaround] Opening PRs modal for: ${username}, category: ${category}`);
                    this.showUserPrsModal(username, category);
                } else {
                    console.warn('[Turnaround] No username found in dataset');
                }
            });
        });
    }

    /**
     * Show modal with user's PRs
     */
    async showUserPrsModal(username, category = 'pr_creators') {
        console.log(`[Turnaround] Opening PRs modal for ${username}, category: ${category}`);

        // Store username and category
        this.userPrsPagination.username = username;
        this.userPrsPagination.category = category;

        // Open modal with username data
        this.userPrsModal.open({ username, category });

        // Set username in title (count and role will be added after data loads)
        this.userPrsModal.setTitle(username);

        // Show loading state
        this.userPrsModal.showLoading('Loading user PRs...');

        // Load all PRs
        await this.loadUserPrsPage();
    }

    /**
     * Load all user PRs from the API
     */
    async loadUserPrsPage() {
        const { username, category } = this.userPrsPagination;

        try {
            const filters = this.getTimeFilters();

            // First, fetch with minimal page size to get total count
            const countParams = {
                user: username,
                role: category,
                page: 1,
                page_size: 1
            };

            if (filters.repository) {
                countParams.repository = filters.repository;
            }

            const countData = await apiClient.fetchUserPRs(
                filters.start_time,
                filters.end_time,
                countParams
            );

            if (countData.error) {
                throw new Error(countData.detail || countData.error);
            }

            const totalItems = countData.pagination?.total || 0;

            // Update title with PR count and role description
            const roleText = this.getRoleDescription(category);
            this.userPrsModal.setTitle(`PRs ${roleText} ${username} (${totalItems})`);

            if (totalItems === 0) {
                this.userPrsModal.setBody('<div class="empty-state">No PRs found for this user in the selected time range.</div>');
                return;
            }

            // Now fetch all PRs using the total count
            const allParams = {
                user: username,
                role: category,
                page: 1,
                page_size: totalItems
            };

            if (filters.repository) {
                allParams.repository = filters.repository;
            }

            const allData = await apiClient.fetchUserPRs(
                filters.start_time,
                filters.end_time,
                allParams
            );

            if (allData.error) {
                throw new Error(allData.detail || allData.error);
            }

            // Store all PRs in state
            this.userPrsPagination.allPrs = allData.data || [];
            this.userPrsPagination.currentPage = 1;

            // Render PRs with pagination
            this.renderUserPrsWithPagination();

        } catch (error) {
            console.error('[Turnaround] Error loading user PRs:', error);
            this.userPrsModal.setBody(`<div class="error-message">Failed to load PRs: ${this.escapeHtml(error.message)}</div>`);
        }
    }

    /**
     * Render user PRs with pagination
     */
    renderUserPrsWithPagination() {
        const { allPrs, currentPage, pageSize } = this.userPrsPagination;

        // Calculate pagination
        const totalItems = allPrs.length;
        const startIdx = (currentPage - 1) * pageSize;
        const endIdx = Math.min(startIdx + pageSize, totalItems);
        const prsOnPage = allPrs.slice(startIdx, endIdx);

        // Render current page of PRs
        const prsListHtml = this.renderUserPrsListHtml(prsOnPage);
        this.userPrsModal.setBody(prsListHtml);

        // Set up delegated click listener for PR items
        const listPanel = document.querySelector('#userPrsModal .user-prs-list-panel');
        if (listPanel) {
            // Remove existing listener if any (to prevent duplicates)
            listPanel.removeEventListener('click', this._prItemClickHandler);

            // Create bound handler if not exists
            if (!this._prItemClickHandler) {
                this._prItemClickHandler = (e) => {
                    const prItem = e.target.closest('.user-pr-item');
                    if (prItem) {
                        const prId = prItem.dataset.prId;
                        const repo = prItem.dataset.repo;
                        const prNumber = parseInt(prItem.dataset.prNumber, 10);
                        if (prId && repo && prNumber) {
                            this.selectPr(prId, repo, prNumber);
                        }
                    }
                };
            }

            // Add delegated click listener
            listPanel.addEventListener('click', this._prItemClickHandler);
        }

        // Set up pagination component
        const paginationContainer = document.querySelector('#userPrsModal .user-prs-pagination');
        if (paginationContainer) {
            // Destroy existing pagination component if it exists
            if (this.userPrsPagination.paginationComponent) {
                this.userPrsPagination.paginationComponent = null;
            }

            // Create new pagination component
            this.userPrsPagination.paginationComponent = new Pagination({
                container: paginationContainer,
                pageSize: pageSize,
                pageSizeOptions: [10, 25, 50, 100],
                onPageChange: (page) => {
                    this.userPrsPagination.currentPage = page;
                    this.renderUserPrsWithPagination();
                },
                onPageSizeChange: (newPageSize) => {
                    this.userPrsPagination.pageSize = newPageSize;
                    this.userPrsPagination.currentPage = 1;
                    this.renderUserPrsWithPagination();
                }
            });

            // Update pagination state
            this.userPrsPagination.paginationComponent.update({
                total: totalItems,
                page: currentPage,
                pageSize: pageSize
            });
        }
    }

    /**
     * Get role description for modal title
     */
    getRoleDescription(category) {
        const roleMap = {
            pr_creators: 'created by',
            pr_reviewers: 'reviewed by',
            pr_approvers: 'approved by',
            pr_lgtm: 'with LGTM by'
        };
        return roleMap[category] || 'for';
    }

    /**
     * Render list of user PRs in two-panel layout
     * Returns HTML string for modal body
     */
    renderUserPrsListHtml(prs) {
        if (!prs || prs.length === 0) {
            return '<div class="empty-state">No PRs found on this page.</div>';
        }

        // Create PR list items - use global index from allPrs to maintain unique IDs
        const { currentPage, pageSize } = this.userPrsPagination;
        const startIdx = (currentPage - 1) * pageSize;

        const listPanelHtml = prs.map((pr, localIndex) => {
            const globalIndex = startIdx + localIndex;
            const stateClass = pr.merged ? 'merged' : pr.state === 'closed' ? 'closed' : 'open';
            const stateLabel = pr.merged ? 'merged' : pr.state;
            const prId = `user-pr-${globalIndex}`;

            return `
                <div class="user-pr-item" data-pr-id="${prId}" data-repo="${this.escapeHtml(pr.repository)}" data-pr-number="${pr.number}">
                    <div class="user-pr-header">
                        <div class="user-pr-title">
                            <span class="pr-number">#${pr.number}</span>
                            <span class="pr-title">${this.escapeHtml(pr.title)}</span>
                        </div>
                        <div class="user-pr-meta">
                            <span class="pr-state pr-state-${stateClass}">${stateLabel}</span>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        // Build the two-panel layout with pagination controls
        return `
            <div class="user-prs-container">
                <div class="user-prs-list-panel">
                    <div class="user-prs-list-content">
                        ${listPanelHtml}
                    </div>
                    <div class="user-prs-pagination"></div>
                </div>
                <div class="user-prs-story-panel">
                    <div class="empty-state">Select a PR to view its timeline</div>
                </div>
            </div>
        `;
    }

    /**
     * Select a PR and show its timeline in the right panel
     */
    async selectPr(prId, repository, prNumber) {
        // Remove selection from all PR items
        const allPrItems = document.querySelectorAll('#userPrsModal .user-pr-item');
        allPrItems.forEach(item => item.classList.remove('selected'));

        // Add selection to clicked item
        const selectedItem = document.querySelector(`#userPrsModal .user-pr-item[data-pr-id="${prId}"]`);
        if (selectedItem) {
            selectedItem.classList.add('selected');
        }

        // Get the story panel
        const storyPanel = document.querySelector('#userPrsModal .user-prs-story-panel');
        if (!storyPanel) return;

        // Show loading state
        storyPanel.innerHTML = '<div class="pr-story-loading">Loading PR timeline...</div>';

        // Load PR story
        await this.loadPrStoryToPanel(repository, prNumber, storyPanel);
    }

    /**
     * Load and render PR story timeline to the story panel
     */
    async loadPrStoryToPanel(repository, prNumber, storyPanel) {
        try {
            const response = await fetch(`/api/metrics/pr-story/${encodeURIComponent(repository)}/${prNumber}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // Render PR story timeline
            storyPanel.innerHTML = `<div class="pr-story-content">${this.renderPrStoryTimeline(data)}</div>`;

        } catch (error) {
            console.error(`[Turnaround] Error loading PR story for ${repository}#${prNumber}:`, error);
            storyPanel.innerHTML = `<div class="error-message">Failed to load PR timeline: ${this.escapeHtml(error.message)}</div>`;
        }
    }

    /**
     * Render PR story timeline
     */
    renderPrStoryTimeline(storyData) {
        const { events, summary } = storyData;

        if (!events || events.length === 0) {
            return '<div class="empty-state">No timeline events found for this PR.</div>';
        }

        // Summary header
        const summaryHtml = `
            <div class="pr-story-summary">
                <span>📝 ${summary.total_commits} commits</span>
                <span>💬 ${summary.total_reviews} reviews</span>
                <span>▶️ ${summary.total_check_runs} check runs</span>
                <span>💭 ${summary.total_comments} comments</span>
            </div>
        `;

        // Timeline events
        const eventsHtml = events.map(event => this.renderTimelineEvent(event)).join('');

        return `
            ${summaryHtml}
            <div class="pr-timeline">
                ${eventsHtml}
            </div>
        `;
    }

    /**
     * Render a single timeline event
     */
    renderTimelineEvent(event) {
        const eventConfig = this.getEventConfig(event.event_type);
        const icon = eventConfig.icon;
        const label = eventConfig.label;

        let descriptionHtml = '';
        if (event.description) {
            descriptionHtml = `<div class="timeline-event-description">${this.escapeHtml(event.description)}</div>`;
        }

        const timeStr = this.formatTimestamp(event.timestamp);

        return `
            <div class="timeline-event-item">
                <div class="timeline-event-marker"></div>
                <div class="timeline-event-content">
                    <div class="timeline-event-header">
                        <span class="timeline-event-icon">${icon}</span>
                        <span class="timeline-event-title">${this.escapeHtml(label)}</span>
                        <span class="timeline-event-time">${timeStr}</span>
                    </div>
                    ${descriptionHtml}
                </div>
            </div>
        `;
    }

    /**
     * Get event configuration (icon, label)
     */
    getEventConfig(eventType) {
        const configs = {
            pr_opened: { icon: '🔀', label: 'PR Opened' },
            pr_closed: { icon: '❌', label: 'PR Closed' },
            pr_merged: { icon: '🟣', label: 'Merged' },
            pr_reopened: { icon: '🔄', label: 'Reopened' },
            commit: { icon: '📝', label: 'Commit' },
            review_approved: { icon: '✅', label: 'Approved' },
            review_changes: { icon: '🔄', label: 'Changes Requested' },
            review_comment: { icon: '💬', label: 'Review Comment' },
            comment: { icon: '💬', label: 'Comment' },
            review_requested: { icon: '👁️', label: 'Review Requested' },
            ready_for_review: { icon: '👁️', label: 'Ready for Review' },
            label_added: { icon: '🏷️', label: 'Label Added' },
            label_removed: { icon: '🏷️', label: 'Label Removed' },
            verified: { icon: '🛡️', label: 'Verified' },
            approved_label: { icon: '✅', label: 'Approved' },
            lgtm: { icon: '👍', label: 'LGTM' },
            check_run: { icon: '▶️', label: 'Check Run' }
        };

        return configs[eventType] || { icon: '●', label: eventType };
    }

    /**
     * Format timestamp for display
     */
    formatTimestamp(timestamp) {
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
     * Format date for PR list
     */
    formatDate(timestamp) {
        try {
            const date = new Date(timestamp);
            return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        } catch {
            return timestamp;
        }
    }

    /**
     * Update pagination controls for a contributor category
     */
    updateContributorPagination(category) {
        const pagination = this.contributorMetrics[category].pagination;
        const paginationComponent = this.contributorMetrics[category].paginationComponent;

        if (!pagination || !paginationComponent) {
            return;
        }

        // Update the pagination component with new state
        paginationComponent.update({
            total: pagination.total,
            page: pagination.page,
            pageSize: pagination.page_size
        });
    }

    /**
     * Get category prefix for element IDs
     */
    getCategoryPrefix(category) {
        const prefixMap = {
            pr_creators: 'prCreators',
            pr_reviewers: 'prReviewers',
            pr_approvers: 'prApprovers',
            pr_lgtm: 'prLgtm'
        };
        return prefixMap[category] || category;
    }

    /**
     * Show error for a specific contributor category
     */
    showContributorCategoryError(category, message) {
        const tableBodyMap = {
            pr_creators: this.prCreatorsTableBody,
            pr_reviewers: this.prReviewersTableBody,
            pr_approvers: this.prApproversTableBody,
            pr_lgtm: this.prLgtmTableBody
        };

        const tableBody = tableBodyMap[category];
        if (!tableBody) {
            return;
        }

        const colspan = category === 'pr_creators' ? 5 : category === 'pr_reviewers' ? 4 : 3;
        tableBody.innerHTML = `<tr><td colspan="${colspan}" style="text-align: center; padding: 20px; color: var(--error-color);">Error: ${this.escapeHtml(message)}</td></tr>`;
    }

    /**
     * Set up pagination controls for contributor metrics
     */
    setupContributorPagination() {
        const categories = ['pr_creators', 'pr_reviewers', 'pr_approvers', 'pr_lgtm'];

        categories.forEach(category => {
            const categoryPrefix = this.getCategoryPrefix(category);
            const container = document.getElementById(`${categoryPrefix}-pagination`);

            if (!container) {
                console.warn(`[Turnaround] Pagination container not found for ${category}`);
                return;
            }

            // Initialize Pagination component
            this.contributorMetrics[category].paginationComponent = new Pagination({
                container: container,
                pageSize: 10,
                pageSizeOptions: [10, 25, 50, 100],
                onPageChange: (page) => {
                    this.contributorMetrics[category].currentPage = page;
                    this.loadContributorCategory(category, this.getTimeFilters());
                },
                onPageSizeChange: () => {
                    this.contributorMetrics[category].currentPage = 1;
                    this.loadContributorCategory(category, this.getTimeFilters());
                }
            });
        });
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
