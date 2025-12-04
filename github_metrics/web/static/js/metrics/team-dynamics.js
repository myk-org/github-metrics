/**
 * Team Dynamics Module
 *
 * Handles loading and displaying team dynamics metrics on the Team Dynamics page.
 *
 * Features:
 * - Loads data when Team Dynamics page is shown
 * - Displays KPI cards with summary metrics
 * - Populates workload, review efficiency, and bottleneck tables
 * - Handles loading/error states
 * - Supports table sorting and pagination
 * - Shows alert cards for critical bottlenecks
 */

import { apiClient } from './api-client.js';
import { Pagination } from '../components/pagination.js';
import { SortableTable } from '../components/sortable-table.js';
import { DownloadButtons } from '../components/download-buttons.js';
import { Modal } from '../components/modal.js';
import { formatHours, formatTimestamp, escapeHtml } from '../utils/formatters.js';
import { renderPrStoryTimeline } from '../components/pr-timeline.js';

class TeamDynamics {
    constructor() {
        console.log('[TeamDynamics] Constructor called');
        this.data = null;
        this.destroyed = false;
        this._retryTimer = null;
        this.loadingElement = document.getElementById('team-dynamics-loading');
        this.errorElement = document.getElementById('team-dynamics-error');
        this.contentElement = document.getElementById('team-dynamics-content');

        // Filter timeouts for debouncing
        this.filterTimeouts = {
            repo: null,
            user: null
        };

        // Workload KPI elements
        this.kpiTotalContributors = document.getElementById('kpi-active-contributors');
        this.kpiAvgPrsPerContributor = document.getElementById('kpi-avg-prs-per-user');
        this.kpiTopContributor = document.getElementById('kpi-top-contributor');
        this.kpiWorkloadGini = document.getElementById('kpi-gini-coefficient');

        // Review efficiency KPI elements
        this.kpiAvgReviewTime = document.getElementById('kpi-avg-review-time');
        this.kpiMedianReviewTime = document.getElementById('kpi-median-review-time');
        this.kpiFastestReviewer = document.getElementById('kpi-fastest-reviewer');
        this.kpiSlowestReviewer = document.getElementById('kpi-slowest-reviewer');

        // Table bodies
        this.workloadTableBody = document.getElementById('workload-table-body');
        this.reviewEfficiencyTableBody = document.getElementById('review-efficiency-table-body');
        this.bottlenecksTableBody = document.getElementById('approvers-table-body');

        // Bottleneck alerts container
        this.bottleneckAlertsContainer = document.getElementById('approval-alerts-container');

        // SortableTable instances
        this.sortableTables = {
            workload: null,
            reviewEfficiency: null,
            bottlenecks: null
        };

        // Pagination state
        this.paginationState = {
            workload: { currentPage: 1, paginationComponent: null },
            reviewEfficiency: { currentPage: 1, paginationComponent: null },
            bottlenecks: { currentPage: 1, paginationComponent: null }
        };

        // User PRs modal state
        this.DEFAULT_PAGE_SIZE = 50;
        this.userPrsState = {
            username: null,
            category: null,
            page: 1
        };

        // Event listener references for cleanup
        this.hashChangeHandler = null;
        this.timeFiltersUpdatedHandler = null;
        this.inputHandler = null;

        this.initialize();
    }

    /**
     * Initialize team dynamics module
     */
    initialize() {
        console.log('[TeamDynamics] Initializing team dynamics module');

        // Listen for page navigation to Team Dynamics
        this.setupPageChangeListener();

        // Initialize SortableTable instances
        this.initializeSortableTables();

        // Set up download buttons
        this.setupDownloadButtons();

        // Set up pagination
        this.setupPagination();

        // Initialize modal component for user PRs
        this.initializeUserPrsModal();

        // Check if we should load metrics (handles direct navigation to #team-dynamics)
        this.checkAndLoadMetrics();
    }

    /**
     * Initialize the user PRs modal using Modal component
     */
    initializeUserPrsModal() {
        this.userPrsModal = new Modal({
            id: 'userPrsModal',
            onOpen: (data) => {
                console.log('[TeamDynamics] User PRs modal opened with data:', data);
            },
            onClose: () => {
                console.log('[TeamDynamics] User PRs modal closed');
            },
            closeOnOverlay: true,
            closeOnEscape: true
        });
    }

    /**
     * Check if we should load metrics and load them if conditions are met
     */
    checkAndLoadMetrics(retryCount = 0) {
        const hash = window.location.hash;
        const currentHash = hash.slice(1) || 'overview';

        console.log('[TeamDynamics] checkAndLoadMetrics - full hash:', hash, 'parsed:', currentHash);

        if (currentHash !== 'team-dynamics') {
            console.log('[TeamDynamics] Not on team-dynamics page, skipping initial load. Hash is:', currentHash);
            return;
        }

        // Check if time filters are ready
        const startTimeInput = document.getElementById('startTime');
        const endTimeInput = document.getElementById('endTime');

        console.log('[TeamDynamics] startTime:', startTimeInput?.value, 'endTime:', endTimeInput?.value);

        if (startTimeInput && startTimeInput.value && endTimeInput && endTimeInput.value) {
            console.log('[TeamDynamics] Time filters ready, loading metrics');
            this.loadMetrics();
        } else {
            console.log('[TeamDynamics] Time filters not ready, waiting...');
            const maxRetries = 50;
            if (retryCount < maxRetries) {
                // Check if destroyed before scheduling retry
                if (this.destroyed) {
                    console.log('[TeamDynamics] Component destroyed, aborting retry loop');
                    return;
                }
                this._retryTimer = setTimeout(() => {
                    // Check if destroyed before executing retry
                    if (this.destroyed) {
                        console.log('[TeamDynamics] Component destroyed, aborting retry');
                        return;
                    }
                    this.checkAndLoadMetrics(retryCount + 1);
                }, 100);
            } else {
                console.error('[TeamDynamics] Max retry attempts reached. Time filters failed to initialize.');
            }
        }
    }

    /**
     * Set up listener for page changes
     */
    setupPageChangeListener() {
        // Listen for hash changes - load metrics directly when navigating to team-dynamics
        this.hashChangeHandler = () => {
            const hash = window.location.hash.slice(1);
            if (hash === 'team-dynamics') {
                console.log('[TeamDynamics] Navigated to team-dynamics page, loading metrics');
                this.loadMetrics();
            }
        };
        window.addEventListener('hashchange', this.hashChangeHandler);

        // Listen for time filter updates from dashboard (custom event)
        this.timeFiltersUpdatedHandler = () => {
            const hash = window.location.hash.slice(1);
            if (hash === 'team-dynamics') {
                console.log('[TeamDynamics] Time filters updated, refreshing metrics');
                this.loadMetrics();
            }
        };
        document.addEventListener('timeFiltersUpdated', this.timeFiltersUpdatedHandler);

        // Listen for repository and user filter changes with debounce
        this.inputHandler = (e) => {
            if (e.target.id === 'repositoryFilter') {
                clearTimeout(this.filterTimeouts?.repo);
                this.filterTimeouts = this.filterTimeouts || {};
                this.filterTimeouts.repo = setTimeout(() => {
                    const hash = window.location.hash.slice(1);
                    if (hash === 'team-dynamics') {
                        console.log('[TeamDynamics] Repository filter changed, refreshing metrics');
                        this.loadMetrics();
                    }
                }, 300);
            } else if (e.target.id === 'userFilter') {
                clearTimeout(this.filterTimeouts?.user);
                this.filterTimeouts = this.filterTimeouts || {};
                this.filterTimeouts.user = setTimeout(() => {
                    const hash = window.location.hash.slice(1);
                    if (hash === 'team-dynamics') {
                        console.log('[TeamDynamics] User filter changed, refreshing metrics');
                        this.loadMetrics();
                    }
                }, 300);
            }
        };
        document.addEventListener('input', this.inputHandler);
    }

    /**
     * Load team dynamics metrics from API
     */
    async loadMetrics() {
        console.log('[TeamDynamics] Loading team dynamics metrics');

        // Show loading state
        this.showLoading();

        try {
            // Get time filter values from the shared control panel
            const filters = this.getTimeFilters();
            console.log('[TeamDynamics] Using filters:', filters);

            // Get current page and page size from workload table
            // Note: Backend API accepts single page/page_size that applies to all three tables
            // (workload, review efficiency, and bottlenecks share the same pagination)
            const workloadPage = this.paginationState.workload.currentPage;
            const workloadPageSize = this.paginationState.workload.paginationComponent?.state.pageSize || 25;

            // Fetch data from API with filters and pagination
            const response = await apiClient.fetchTeamDynamics(
                filters.start_time,
                filters.end_time,
                filters.repository,
                filters.user,
                workloadPage,
                workloadPageSize
            );

            // Check for errors
            if (response.error) {
                this.showError(`Failed to load metrics: ${response.detail || response.error}`);
                return;
            }

            // Store data
            this.data = response;

            // Debug logging
            console.log('[TeamDynamics] Response received:', {
                hasWorkload: !!response.workload,
                hasReviewEfficiency: !!response.review_efficiency,
                hasBottlenecks: !!response.bottlenecks
            });

            // Update UI
            this.updateWorkloadSection(response.workload);
            this.updateReviewEfficiencySection(response.review_efficiency);
            this.updateBottlenecksSection(response.bottlenecks);

            // Show content
            this.showContent();

        } catch (error) {
            console.error('[TeamDynamics] Error loading metrics:', error);
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
     * Update workload section with data
     */
    updateWorkloadSection(workloadData) {
        if (!workloadData) {
            console.warn('[TeamDynamics] No workload data available');
            return;
        }

        // Update KPIs
        const summary = workloadData.summary || {};
        if (this.kpiTotalContributors) {
            this.kpiTotalContributors.textContent = summary.total_contributors || 0;
        }
        if (this.kpiAvgPrsPerContributor) {
            this.kpiAvgPrsPerContributor.textContent = summary.avg_prs_per_contributor
                ? summary.avg_prs_per_contributor.toFixed(1)
                : '0.0';
        }
        if (this.kpiTopContributor) {
            this.kpiTopContributor.textContent = summary.top_contributor?.user || 'N/A';
        }
        if (this.kpiWorkloadGini) {
            this.kpiWorkloadGini.textContent = summary.workload_gini != null
                ? `${(summary.workload_gini * 100).toFixed(1)}%`
                : 'N/A';
        }

        // Update SortableTable instance
        if (this.sortableTables.workload) {
            this.sortableTables.workload.update(workloadData.by_contributor || []);
        }

        // Update table directly with server-side paginated data
        this.updateWorkloadTable(workloadData.by_contributor || []);

        // Update pagination components with server-side pagination metadata
        // Note: All three tables share the same pagination from workload data
        const pagination = workloadData.pagination;
        if (pagination) {
            // Update all three pagination components to stay in sync
            ['workload', 'reviewEfficiency', 'bottlenecks'].forEach(key => {
                const paginationComponent = this.paginationState[key].paginationComponent;
                if (paginationComponent) {
                    paginationComponent.update({
                        total: pagination.total,
                        page: pagination.page,
                        pageSize: pagination.page_size
                    });

                    // Show/hide pagination based on total items
                    if (pagination.total > pagination.page_size) {
                        paginationComponent.show();
                    } else {
                        paginationComponent.hide();
                    }
                }
            });
        }
    }

    /**
     * Update review efficiency section with data
     */
    updateReviewEfficiencySection(reviewEfficiencyData) {
        if (!reviewEfficiencyData) {
            console.warn('[TeamDynamics] No review efficiency data available');
            return;
        }

        // Update KPIs
        const summary = reviewEfficiencyData.summary || {};
        if (this.kpiAvgReviewTime) {
            this.kpiAvgReviewTime.textContent = formatHours(summary.avg_review_time_hours);
        }
        if (this.kpiMedianReviewTime) {
            this.kpiMedianReviewTime.textContent = formatHours(summary.median_review_time_hours);
        }
        if (this.kpiFastestReviewer) {
            this.kpiFastestReviewer.textContent = summary.fastest_reviewer?.user || 'N/A';
        }
        if (this.kpiSlowestReviewer) {
            this.kpiSlowestReviewer.textContent = summary.slowest_reviewer?.user || 'N/A';
        }

        // Update SortableTable instance
        if (this.sortableTables.reviewEfficiency) {
            this.sortableTables.reviewEfficiency.update(reviewEfficiencyData.by_reviewer || []);
        }

        // Update table directly with server-side paginated data
        this.updateReviewEfficiencyTable(reviewEfficiencyData.by_reviewer || []);

        // Note: Pagination is updated in updateWorkloadSection() since all tables share the same pagination
    }

    /**
     * Update bottlenecks section with data
     */
    updateBottlenecksSection(bottlenecksData) {
        if (!bottlenecksData) {
            console.warn('[TeamDynamics] No bottlenecks data available');
            return;
        }

        // Update alert cards
        this.renderAlertCards(bottlenecksData.alerts || []);

        // Update SortableTable instance
        if (this.sortableTables.bottlenecks) {
            this.sortableTables.bottlenecks.update(bottlenecksData.by_approver || []);
        }

        // Update table directly with server-side paginated data
        this.updateBottlenecksTable(bottlenecksData.by_approver || []);

        // Note: Pagination is updated in updateWorkloadSection() since all tables share the same pagination
    }

    /**
     * Update workload table with data
     */
    updateWorkloadTable(contributors) {
        if (!this.workloadTableBody) {
            console.warn('[TeamDynamics] Workload table body not found');
            return;
        }

        // Clear existing rows
        this.workloadTableBody.innerHTML = '';

        // Handle empty data
        if (!contributors || contributors.length === 0) {
            this.workloadTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: var(--text-secondary);">No data available</td></tr>';
            return;
        }

        // Populate table
        // Note: HTML expects: contributor, prs_created, prs_reviewed, prs_approved
        // Backend provides: user, prs_created, prs_merged, workload_percentage
        // For now, we'll use prs_created and show zeros for reviewed/approved until backend is updated
        contributors.forEach(contributor => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><a href="#" class="clickable-username" data-username="${escapeHtml(contributor.user)}" data-category="workload">${escapeHtml(contributor.user)}</a></td>
                <td>${contributor.prs_created || 0}</td>
                <td>${contributor.prs_reviewed || 0}</td>
                <td>${contributor.prs_approved || contributor.prs_merged || 0}</td>
            `;
            this.workloadTableBody.appendChild(row);
        });

        // Set up click handlers for usernames
        this.setupUsernameClickHandlers(this.workloadTableBody);
    }

    /**
     * Update review efficiency table with data
     */
    updateReviewEfficiencyTable(reviewers) {
        if (!this.reviewEfficiencyTableBody) {
            console.warn('[TeamDynamics] Review efficiency table body not found');
            return;
        }

        // Clear existing rows
        this.reviewEfficiencyTableBody.innerHTML = '';

        // Handle empty data
        if (!reviewers || reviewers.length === 0) {
            this.reviewEfficiencyTableBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: var(--text-secondary);">No data available</td></tr>';
            return;
        }

        // Populate table
        reviewers.forEach(reviewer => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><a href="#" class="clickable-username" data-username="${escapeHtml(reviewer.user)}" data-category="reviewEfficiency">${escapeHtml(reviewer.user)}</a></td>
                <td>${formatHours(reviewer.avg_review_time_hours)}</td>
                <td>${formatHours(reviewer.median_review_time_hours)}</td>
                <td>${reviewer.total_reviews || 0}</td>
            `;
            this.reviewEfficiencyTableBody.appendChild(row);
        });

        // Set up click handlers for usernames
        this.setupUsernameClickHandlers(this.reviewEfficiencyTableBody);
    }

    /**
     * Update bottlenecks table with data
     */
    updateBottlenecksTable(approvers) {
        if (!this.bottlenecksTableBody) {
            console.warn('[TeamDynamics] Bottlenecks table body not found');
            return;
        }

        // Clear existing rows
        this.bottlenecksTableBody.innerHTML = '';

        // Handle empty data
        if (!approvers || approvers.length === 0) {
            this.bottlenecksTableBody.innerHTML = '<tr><td colspan="3" style="text-align: center; padding: 20px; color: var(--text-secondary);">No data available</td></tr>';
            return;
        }

        // Populate table
        approvers.forEach(approver => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td><a href="#" class="clickable-username" data-username="${escapeHtml(approver.approver)}" data-category="bottlenecks">${escapeHtml(approver.approver)}</a></td>
                <td>${formatHours(approver.avg_approval_hours)}</td>
                <td>${approver.total_approvals || 0}</td>
            `;
            this.bottlenecksTableBody.appendChild(row);
        });

        // Set up click handlers for usernames
        this.setupUsernameClickHandlers(this.bottlenecksTableBody);
    }

    /**
     * Render alert cards for bottlenecks
     */
    renderAlertCards(alerts) {
        if (!this.bottleneckAlertsContainer) {
            console.warn('[TeamDynamics] Bottleneck alerts container not found');
            return;
        }

        // Clear existing alerts
        this.bottleneckAlertsContainer.innerHTML = '';

        // Handle empty alerts
        if (!alerts || alerts.length === 0) {
            this.bottleneckAlertsContainer.innerHTML = '<div class="empty-state">No critical bottlenecks detected</div>';
            return;
        }

        // Render alert cards
        alerts.forEach(alert => {
            const alertClass = alert.severity === 'critical' ? 'alert-critical' : 'alert-warning';
            const alertCard = document.createElement('div');
            alertCard.className = `alert-card ${alertClass}`;
            alertCard.innerHTML = `
                <div class="alert-header">
                    <span class="alert-icon">${alert.severity === 'critical' ? '🚨' : '⚠️'}</span>
                    <span class="alert-title">${escapeHtml(alert.approver)}</span>
                </div>
                <div class="alert-body">
                    <p>Team has <strong>${alert.team_pending_count}</strong> pending approvals</p>
                    <p>Average approval time: <strong>${formatHours(alert.avg_approval_hours)}</strong></p>
                </div>
            `;
            this.bottleneckAlertsContainer.appendChild(alertCard);
        });
    }

    /**
     * Set up click handlers for usernames
     */
    setupUsernameClickHandlers(tableBody) {
        const usernameLinks = tableBody.querySelectorAll('.clickable-username');
        console.log(`[TeamDynamics] Setting up click handlers for ${usernameLinks.length} username links`);
        usernameLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const username = e.currentTarget.dataset.username;
                const category = e.currentTarget.dataset.category;
                if (username) {
                    console.log(`[TeamDynamics] Opening PRs modal for: ${username}, category: ${category}`);
                    this.showUserPrsModal(username, category);
                }
            });
        });
    }

    /**
     * Show modal with user's PRs (reuse pattern from turnaround.js)
     */
    async showUserPrsModal(username, category = 'workload') {
        console.log(`[TeamDynamics] Opening PRs modal for ${username}, category: ${category}`);

        // Store username and category, reset page to 1
        this.userPrsState.username = username;
        this.userPrsState.category = category;
        this.userPrsState.page = 1;

        // Open modal with username data
        this.userPrsModal.open({ username, category });

        // Set username in title
        this.userPrsModal.setTitle(`PRs for ${username}`);

        // Show loading state
        this.userPrsModal.showLoading('Loading user PRs...');

        // Load PRs from user-prs endpoint
        await this.loadUserPrs();
    }

    /**
     * Load user PRs from the API
     * Uses a reasonable page size (not totalItems) per API design principles
     */
    async loadUserPrs() {
        const { username, category, page } = this.userPrsState;

        try {
            const filters = this.getTimeFilters();

            // Map category to role parameter
            const roleMap = {
                workload: 'pr_creators',
                reviewEfficiency: 'pr_reviewers',
                bottlenecks: 'pr_approvers'
            };
            const role = roleMap[category] || 'pr_creators';

            // Fetch PRs with a reasonable page size
            const params = {
                user: username,
                role: role,
                page: page,
                page_size: this.DEFAULT_PAGE_SIZE
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

            const totalItems = data.pagination?.total || 0;
            const totalPages = Math.ceil(totalItems / this.DEFAULT_PAGE_SIZE);

            // Update title with PR count
            this.userPrsModal.setTitle(`PRs for ${username} (${totalItems})`);

            if (totalItems === 0) {
                this.userPrsModal.setBody('<div class="empty-state">No PRs found for this user in the selected time range.</div>');
                return;
            }

            // Render PRs
            this.renderUserPrsList(data.data || [], totalItems, page, totalPages);

        } catch (error) {
            console.error('[TeamDynamics] Error loading user PRs:', error);
            this.userPrsModal.setBody(`<div class="error-message">Failed to load PRs: ${escapeHtml(error.message)}</div>`);
        }
    }

    /**
     * Render user PRs list
     */
    renderUserPrsList(prs, totalItems, currentPage, totalPages) {
        const prsListHtml = this.renderUserPrsListHtml(prs, totalItems, currentPage, totalPages);
        this.userPrsModal.setBody(prsListHtml);

        // Set up delegated click listener for PR items
        const listPanel = document.querySelector('#userPrsModal .user-prs-list-panel');
        if (listPanel) {
            listPanel.removeEventListener('click', this._prItemClickHandler);

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

            listPanel.addEventListener('click', this._prItemClickHandler);
        }

        // Set up pagination controls
        if (totalPages > 1) {
            this.setupUserPrsPaginationControls(currentPage, totalPages);
        }
    }

    /**
     * Render list of user PRs
     */
    renderUserPrsListHtml(prs, totalItems, currentPage, totalPages) {
        if (!prs || prs.length === 0) {
            return '<div class="empty-state">No PRs found.</div>';
        }

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

        // Show pagination info or controls if needed
        let paginationHtml = '';
        if (totalPages > 1) {
            const startItem = (currentPage - 1) * this.DEFAULT_PAGE_SIZE + 1;
            const endItem = Math.min(currentPage * this.DEFAULT_PAGE_SIZE, totalItems);
            paginationHtml = `
                <div class="user-prs-pagination">
                    <div class="pagination-info">Showing ${startItem}-${endItem} of ${totalItems} PRs</div>
                    <div class="pagination-controls">
                        <button class="pagination-btn" id="user-prs-prev-btn" ${currentPage === 1 ? 'disabled' : ''}>← Previous</button>
                        <span class="pagination-page-info">Page ${currentPage} of ${totalPages}</span>
                        <button class="pagination-btn" id="user-prs-next-btn" ${currentPage === totalPages ? 'disabled' : ''}>Next →</button>
                    </div>
                </div>
            `;
        } else if (totalItems > this.DEFAULT_PAGE_SIZE) {
            // Showing first X of Y message if there are more items than page size but only one page shown
            paginationHtml = `
                <div class="user-prs-pagination">
                    <div class="pagination-info">Showing first ${prs.length} of ${totalItems} PRs</div>
                </div>
            `;
        }

        return `
            <div class="user-prs-container">
                <div class="user-prs-list-panel">
                    ${paginationHtml}
                    <div class="user-prs-list-content">
                        ${listPanelHtml}
                    </div>
                </div>
                <div class="user-prs-story-panel">
                    <div class="empty-state">Select a PR to view its timeline</div>
                </div>
            </div>
        `;
    }

    /**
     * Set up pagination controls for user PRs modal
     */
    setupUserPrsPaginationControls(currentPage, totalPages) {
        const prevBtn = document.getElementById('user-prs-prev-btn');
        const nextBtn = document.getElementById('user-prs-next-btn');

        if (prevBtn) {
            prevBtn.onclick = async () => {
                if (currentPage > 1) {
                    this.userPrsState.page = currentPage - 1;
                    this.userPrsModal.showLoading('Loading PRs...');
                    await this.loadUserPrs();
                }
            };
        }

        if (nextBtn) {
            nextBtn.onclick = async () => {
                if (currentPage < totalPages) {
                    this.userPrsState.page = currentPage + 1;
                    this.userPrsModal.showLoading('Loading PRs...');
                    await this.loadUserPrs();
                }
            };
        }
    }

    /**
     * Select a PR and show its timeline
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

        // Get story panel
        const storyPanel = document.querySelector('#userPrsModal .user-prs-story-panel');
        if (!storyPanel) return;

        // Show loading state
        storyPanel.innerHTML = '<div class="pr-story-loading">Loading PR timeline...</div>';

        // Load PR story (reuse from turnaround.js)
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
            console.error(`[TeamDynamics] Error loading PR story for ${repository}#${prNumber}:`, error);
            storyPanel.innerHTML = `<div class="error-message">Failed to load PR timeline: ${escapeHtml(error.message)}</div>`;
        }
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
     * Initialize SortableTable instances
     */
    initializeSortableTables() {
        const tableConfigs = {
            workload: {
                tableId: 'workloadTable',
                columns: {
                    contributor: { type: 'string' },
                    prs_created: { type: 'number' },
                    prs_reviewed: { type: 'number' },
                    prs_approved: { type: 'number' }
                }
            },
            reviewEfficiency: {
                tableId: 'reviewEfficiencyTable',
                columns: {
                    reviewer: { type: 'string' },
                    avg_time: { type: 'number' },
                    median_time: { type: 'number' },
                    total_reviews: { type: 'number' }
                }
            },
            bottlenecks: {
                tableId: 'approversTable',
                columns: {
                    approver: { type: 'string' },
                    avg_approval_time: { type: 'number' },
                    total_approvals: { type: 'number' }
                }
            }
        };

        Object.keys(tableConfigs).forEach(key => {
            const config = tableConfigs[key];
            const table = document.getElementById(config.tableId);

            if (!table) {
                console.warn(`[TeamDynamics] Table not found: ${config.tableId}`);
                return;
            }

            const data = this.getTableData(key);

            this.sortableTables[key] = new SortableTable({
                table: table,
                data: data,
                columns: config.columns,
                onSort: (sortedData, column, direction) => {
                    console.log(`[TeamDynamics] Table ${key} sorted by ${column} ${direction}`);
                    this.handleTableSorted(key, sortedData);
                }
            });

            console.log(`[TeamDynamics] SortableTable initialized for ${key}`);
        });
    }

    /**
     * Get table data for a given key
     */
    getTableData(key) {
        if (key === 'workload') {
            return this.data?.workload?.by_contributor || [];
        } else if (key === 'reviewEfficiency') {
            return this.data?.review_efficiency?.by_reviewer || [];
        } else if (key === 'bottlenecks') {
            return this.data?.bottlenecks?.by_approver || [];
        }
        return [];
    }

    /**
     * Handle table sorted callback
     */
    handleTableSorted(key, sortedData) {
        if (key === 'workload') {
            this.updateWorkloadTable(sortedData);
        } else if (key === 'reviewEfficiency') {
            this.updateReviewEfficiencyTable(sortedData);
        } else if (key === 'bottlenecks') {
            this.updateBottlenecksTable(sortedData);
        }
    }

    /**
     * Set up download buttons
     */
    setupDownloadButtons() {
        this.downloadButtons = {};

        // Workload table
        const workloadContainer = document.querySelector('[data-section="workload-distribution"] .table-controls');
        if (workloadContainer) {
            this.downloadButtons.workload = new DownloadButtons({
                container: workloadContainer,
                section: 'workload_distribution',
                getData: () => this.data?.workload?.by_contributor || []
            });
        }

        // Review efficiency table
        const reviewEfficiencyContainer = document.querySelector('[data-section="review-efficiency"] .table-controls');
        if (reviewEfficiencyContainer) {
            this.downloadButtons.reviewEfficiency = new DownloadButtons({
                container: reviewEfficiencyContainer,
                section: 'review_efficiency',
                getData: () => this.data?.review_efficiency?.by_reviewer || []
            });
        }

        // Bottlenecks table
        const bottlenecksContainer = document.querySelector('[data-section="bottlenecks"] .table-controls');
        if (bottlenecksContainer) {
            this.downloadButtons.bottlenecks = new DownloadButtons({
                container: bottlenecksContainer,
                section: 'bottlenecks',
                getData: () => this.data?.bottlenecks?.by_approver || []
            });
        }
    }

    /**
     * Set up pagination for the three data tables
     */
    setupPagination() {
        console.log('[TeamDynamics] Setting up pagination for data tables');

        const DEFAULT_TABLE_PAGE_SIZE = 25;
        const TABLE_PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

        // Workload table pagination
        const workloadPaginationContainer = document.getElementById('workloadTable-pagination');
        if (workloadPaginationContainer) {
            this.paginationState.workload.paginationComponent = new Pagination({
                container: workloadPaginationContainer,
                pageSize: DEFAULT_TABLE_PAGE_SIZE,
                pageSizeOptions: TABLE_PAGE_SIZE_OPTIONS,
                onPageChange: (page, pageSize) => {
                    console.log(`[TeamDynamics] Workload table page changed: ${page}, size: ${pageSize}`);
                    this.paginationState.workload.currentPage = page;
                    // Reload metrics from API with new page number
                    this.loadMetrics();
                },
                onPageSizeChange: (pageSize) => {
                    console.log(`[TeamDynamics] Workload table page size changed: ${pageSize}`);
                    this.paginationState.workload.currentPage = 1;
                    // Reload metrics from API with new page size
                    this.loadMetrics();
                }
            });
            // Initially hide pagination until data is loaded
            this.paginationState.workload.paginationComponent.hide();
        }

        // Review efficiency table pagination
        // Note: All three tables (workload, review efficiency, bottlenecks) share the same
        // pagination because the backend API uses a single page/page_size parameter
        const reviewEfficiencyPaginationContainer = document.getElementById('reviewEfficiencyTable-pagination');
        if (reviewEfficiencyPaginationContainer) {
            this.paginationState.reviewEfficiency.paginationComponent = new Pagination({
                container: reviewEfficiencyPaginationContainer,
                pageSize: DEFAULT_TABLE_PAGE_SIZE,
                pageSizeOptions: TABLE_PAGE_SIZE_OPTIONS,
                onPageChange: (page, pageSize) => {
                    console.log(`[TeamDynamics] Review efficiency table page changed: ${page}, size: ${pageSize}`);
                    // Sync to workload pagination (all tables share same pagination)
                    this.paginationState.workload.currentPage = page;
                    this.paginationState.reviewEfficiency.currentPage = page;
                    this.paginationState.bottlenecks.currentPage = page;
                    // Reload metrics from API with new page number
                    this.loadMetrics();
                },
                onPageSizeChange: (pageSize) => {
                    console.log(`[TeamDynamics] Review efficiency table page size changed: ${pageSize}`);
                    // Sync to workload pagination (all tables share same pagination)
                    this.paginationState.workload.currentPage = 1;
                    this.paginationState.reviewEfficiency.currentPage = 1;
                    this.paginationState.bottlenecks.currentPage = 1;
                    // Reload metrics from API with new page size
                    this.loadMetrics();
                }
            });
            // Initially hide pagination until data is loaded
            this.paginationState.reviewEfficiency.paginationComponent.hide();
        }

        // Bottlenecks table pagination
        // Note: All three tables (workload, review efficiency, bottlenecks) share the same
        // pagination because the backend API uses a single page/page_size parameter
        const bottlenecksPaginationContainer = document.getElementById('approversTable-pagination');
        if (bottlenecksPaginationContainer) {
            this.paginationState.bottlenecks.paginationComponent = new Pagination({
                container: bottlenecksPaginationContainer,
                pageSize: DEFAULT_TABLE_PAGE_SIZE,
                pageSizeOptions: TABLE_PAGE_SIZE_OPTIONS,
                onPageChange: (page, pageSize) => {
                    console.log(`[TeamDynamics] Bottlenecks table page changed: ${page}, size: ${pageSize}`);
                    // Sync to workload pagination (all tables share same pagination)
                    this.paginationState.workload.currentPage = page;
                    this.paginationState.reviewEfficiency.currentPage = page;
                    this.paginationState.bottlenecks.currentPage = page;
                    // Reload metrics from API with new page number
                    this.loadMetrics();
                },
                onPageSizeChange: (pageSize) => {
                    console.log(`[TeamDynamics] Bottlenecks table page size changed: ${pageSize}`);
                    // Sync to workload pagination (all tables share same pagination)
                    this.paginationState.workload.currentPage = 1;
                    this.paginationState.reviewEfficiency.currentPage = 1;
                    this.paginationState.bottlenecks.currentPage = 1;
                    // Reload metrics from API with new page size
                    this.loadMetrics();
                }
            });
            // Initially hide pagination until data is loaded
            this.paginationState.bottlenecks.paginationComponent.hide();
        }
    }


    /**
     * Destroy and clean up
     */
    destroy() {
        console.log('[TeamDynamics] Destroying team dynamics module');

        // Mark as destroyed to prevent retry loop continuation
        this.destroyed = true;

        // Clear any pending retry timer
        if (this._retryTimer) {
            clearTimeout(this._retryTimer);
            this._retryTimer = null;
        }

        // Remove event listeners
        if (this.hashChangeHandler) {
            window.removeEventListener('hashchange', this.hashChangeHandler);
            this.hashChangeHandler = null;
        }

        if (this.timeFiltersUpdatedHandler) {
            document.removeEventListener('timeFiltersUpdated', this.timeFiltersUpdatedHandler);
            this.timeFiltersUpdatedHandler = null;
        }

        // Remove input event listener
        if (this.inputHandler) {
            document.removeEventListener('input', this.inputHandler);
            this.inputHandler = null;
        }

        // Clear any pending filter timeouts
        if (this.filterTimeouts) {
            clearTimeout(this.filterTimeouts.repo);
            clearTimeout(this.filterTimeouts.user);
            this.filterTimeouts = { repo: null, user: null };
        }

        // Clean up PR item click handler
        if (this._prItemClickHandler) {
            // Note: The handler is attached to a modal element that may be destroyed,
            // so we just clear the reference
            this._prItemClickHandler = null;
        }

        // Destroy modal
        if (this.userPrsModal && typeof this.userPrsModal.destroy === 'function') {
            this.userPrsModal.destroy();
            this.userPrsModal = null;
        }

        // Destroy sortable tables
        if (this.sortableTables) {
            Object.keys(this.sortableTables).forEach(key => {
                const table = this.sortableTables[key];
                if (table && typeof table.destroy === 'function') {
                    table.destroy();
                }
            });
            this.sortableTables = { workload: null, reviewEfficiency: null, bottlenecks: null };
        }

        // Destroy pagination components
        if (this.paginationState) {
            Object.keys(this.paginationState).forEach(key => {
                const pagination = this.paginationState[key]?.paginationComponent;
                if (pagination && typeof pagination.destroy === 'function') {
                    pagination.destroy();
                }
            });
            this.paginationState = {
                workload: { currentPage: 1, paginationComponent: null },
                reviewEfficiency: { currentPage: 1, paginationComponent: null },
                bottlenecks: { currentPage: 1, paginationComponent: null }
            };
        }

        // Destroy download buttons
        if (this.downloadButtons) {
            Object.keys(this.downloadButtons).forEach(key => {
                const downloadBtn = this.downloadButtons[key];
                if (downloadBtn && typeof downloadBtn.destroy === 'function') {
                    downloadBtn.destroy();
                }
            });
            this.downloadButtons = null;
        }

        // Clear DOM references
        this.loadingElement = null;
        this.errorElement = null;
        this.contentElement = null;
        this.kpiTotalContributors = null;
        this.kpiAvgPrsPerContributor = null;
        this.kpiTopContributor = null;
        this.kpiWorkloadGini = null;
        this.kpiAvgReviewTime = null;
        this.kpiMedianReviewTime = null;
        this.kpiFastestReviewer = null;
        this.kpiSlowestReviewer = null;
        this.workloadTableBody = null;
        this.reviewEfficiencyTableBody = null;
        this.bottlenecksTableBody = null;
        this.bottleneckAlertsContainer = null;

        // Clear data
        this.data = null;

        console.log('[TeamDynamics] Team dynamics module destroyed');
    }
}

// Initialize team dynamics when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.teamDynamics = new TeamDynamics();
    });
} else {
    window.teamDynamics = new TeamDynamics();
}

// Export for module usage
export { TeamDynamics };
