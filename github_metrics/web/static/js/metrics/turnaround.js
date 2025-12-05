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
import { formatHours, formatTimestamp, escapeHtml } from '../utils/formatters.js';
import { renderPrStoryTimeline } from '../components/pr-timeline.js';

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
            currentPagePrs: [], // Store current page PRs only
            currentPage: 1,
            pageSize: 10,
            totalItems: 0,
            totalPages: 0,
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
            } else if (e.target.id === 'userFilter' || e.target.id === 'excludeUserFilter') {
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
        const userFilterGroup = document.getElementById('user-filter-group');
        const excludeUserFilterGroup = document.getElementById('exclude-user-filter-group');

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

        // Get users array from multi-select combo box
        if (userFilterGroup && userFilterGroup._comboBox) {
            const users = userFilterGroup._comboBox.getSelectedValues();
            if (users && users.length > 0) {
                filters.users = users;
            }
        } else {
            // Fallback for plain input
            const userInput = document.getElementById('userFilter');
            if (userInput && userInput.value) {
                filters.users = [userInput.value];
            }
        }

        // Get exclude_users array
        if (excludeUserFilterGroup && excludeUserFilterGroup._comboBox) {
            const excludeUsers = excludeUserFilterGroup._comboBox.getSelectedValues();
            if (excludeUsers && excludeUsers.length > 0) {
                filters.exclude_users = excludeUsers;
            }
        } else {
            const excludeUserInput = document.getElementById('excludeUserFilter');
            if (excludeUserInput && excludeUserInput.value) {
                filters.exclude_users = [excludeUserInput.value];
            }
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
        this.kpiFirstReview.textContent = formatHours(summary.avg_time_to_first_review_hours);
        this.kpiApproval.textContent = formatHours(summary.avg_time_to_approval_hours);
        this.kpiLifecycle.textContent = formatHours(summary.avg_pr_lifecycle_hours);
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
                <td>${escapeHtml(repo.repository)}</td>
                <td>${formatHours(repo.avg_time_to_first_review_hours)}</td>
                <td>${formatHours(repo.avg_time_to_approval_hours)}</td>
                <td>${formatHours(repo.avg_pr_lifecycle_hours)}</td>
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
                <td>${escapeHtml(reviewer.reviewer)}</td>
                <td>${formatHours(reviewer.avg_response_time_hours)}</td>
                <td>${reviewer.total_reviews}</td>
                <td title="${escapeHtml(repos)}">${this.truncateText(repos, 50)}</td>
            `;
            this.reviewerTableBody.appendChild(row);
        });
    }

    /**
     * Truncate text with ellipsis
     */
    truncateText(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return escapeHtml(text);
        return escapeHtml(text.substring(0, maxLength) + '...');
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

            // Get page size from the Pagination instance associated with this category
            const paginationComponent = this.contributorMetrics[category].paginationComponent;
            const pageSize = paginationComponent?.pageSize || 10;

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
                    <td><a href="#" class="clickable-username" data-username="${escapeHtml(item.user)}" data-category="${category}">${escapeHtml(item.user)}</a></td>
                    <td>${item.total_prs || 0}</td>
                    <td>${item.merged_prs || 0}</td>
                    <td>${item.closed_prs || 0}</td>
                    <td>${item.avg_commits_per_pr ? parseFloat(item.avg_commits_per_pr).toFixed(1) : '0.0'}</td>
                `;
            } else if (category === 'pr_reviewers') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${escapeHtml(item.user)}" data-category="${category}">${escapeHtml(item.user)}</a></td>
                    <td>${item.total_reviews || 0}</td>
                    <td>${item.prs_reviewed || 0}</td>
                    <td>${item.avg_reviews_per_pr ? parseFloat(item.avg_reviews_per_pr).toFixed(1) : '0.0'}</td>
                `;
            } else if (category === 'pr_approvers') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${escapeHtml(item.user)}" data-category="${category}">${escapeHtml(item.user)}</a></td>
                    <td>${item.total_approvals || 0}</td>
                    <td>${item.prs_approved || 0}</td>
                `;
            } else if (category === 'pr_lgtm') {
                row.innerHTML = `
                    <td><a href="#" class="clickable-username" data-username="${escapeHtml(item.user)}" data-category="${category}">${escapeHtml(item.user)}</a></td>
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
     * Load user PRs from the API (server-side pagination)
     */
    async loadUserPrsPage() {
        const { username, category, currentPage, pageSize } = this.userPrsPagination;

        try {
            const filters = this.getTimeFilters();

            // Fetch current page from API
            const params = {
                user: username,
                role: category,
                page: currentPage,
                page_size: pageSize
            };

            if (filters.repository) {
                params.repository = filters.repository;
            }

            const data = await apiClient.fetchUserPRs(
                filters.start_time,
                filters.end_time,
                params
            );

            if (data.error) {
                throw new Error(data.detail || data.error);
            }

            // Store pagination metadata
            this.userPrsPagination.totalItems = data.pagination?.total || 0;
            this.userPrsPagination.totalPages = data.pagination?.total_pages || 0;
            this.userPrsPagination.currentPagePrs = data.data || [];

            // Update title with PR count and role description
            const roleText = this.getRoleDescription(category);
            this.userPrsModal.setTitle(`PRs ${roleText} ${username} (${this.userPrsPagination.totalItems})`);

            if (this.userPrsPagination.totalItems === 0) {
                this.userPrsModal.setBody('<div class="empty-state">No PRs found for this user in the selected time range.</div>');
                return;
            }

            // Render PRs with pagination
            this.renderUserPrsWithPagination();

        } catch (error) {
            console.error('[Turnaround] Error loading user PRs:', error);
            this.userPrsModal.setBody(`<div class="error-message">Failed to load PRs: ${escapeHtml(error.message)}</div>`);
        }
    }

    /**
     * Render user PRs with server-side pagination
     */
    renderUserPrsWithPagination() {
        const { currentPagePrs, totalItems, currentPage, pageSize } = this.userPrsPagination;

        // Render current page PRs with pagination controls
        const prsListHtml = this.renderUserPrsListHtml(currentPagePrs);
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

        // Initialize or update pagination component
        const paginationContainer = document.querySelector('#userPrsModal .user-prs-pagination');
        if (paginationContainer && totalItems > 0) {
            // Destroy existing pagination component if it exists
            if (this.userPrsPagination.paginationComponent) {
                this.userPrsPagination.paginationComponent.destroy();
            }

            // Create new pagination component
            this.userPrsPagination.paginationComponent = new Pagination({
                container: paginationContainer,
                pageSize: pageSize,
                total: totalItems,
                page: currentPage,
                pageSizeOptions: [10, 25, 50, 100],
                onPageChange: (page) => {
                    this.userPrsPagination.currentPage = page;
                    this.loadUserPrsPage();
                },
                onPageSizeChange: (newPageSize) => {
                    this.userPrsPagination.pageSize = newPageSize;
                    this.userPrsPagination.currentPage = 1;
                    this.loadUserPrsPage();
                }
            });

            // Initialize pagination state - constructor ignores these values
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
            return '<div class="empty-state">No PRs found.</div>';
        }

        // Create PR list items - use index to maintain unique IDs
        const listPanelHtml = prs.map((pr, index) => {
            const stateClass = pr.merged ? 'merged' : pr.state === 'closed' ? 'closed' : 'open';
            const stateLabel = pr.merged ? 'merged' : pr.state;
            const prId = `user-pr-${index}`;

            return `
                <div class="user-pr-item" data-pr-id="${prId}" data-repo="${escapeHtml(pr.repository)}" data-pr-number="${pr.number}">
                    <div class="user-pr-header">
                        <div class="user-pr-title">
                            <span class="pr-number">#${pr.number}</span>
                            <span class="pr-title">${escapeHtml(pr.title)}</span>
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
            const data = await apiClient.fetchPRStory(repository, prNumber);

            if (data.error) {
                throw new Error(data.detail || data.error);
            }

            // Render PR story timeline (using shared component)
            storyPanel.innerHTML = `<div class="pr-story-content">${renderPrStoryTimeline(data)}</div>`;

        } catch (error) {
            console.error(`[Turnaround] Error loading PR story for ${repository}#${prNumber}:`, error);
            storyPanel.innerHTML = `<div class="error-message">Failed to load PR timeline: ${escapeHtml(error.message)}</div>`;
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
        tableBody.innerHTML = `<tr><td colspan="${colspan}" style="text-align: center; padding: 20px; color: var(--error-color);">Error: ${escapeHtml(message)}</td></tr>`;
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

            // Initialize with empty state - will be updated when data loads
            this.contributorMetrics[category].paginationComponent.update({
                total: 0,
                page: 1,
                pageSize: 10
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
