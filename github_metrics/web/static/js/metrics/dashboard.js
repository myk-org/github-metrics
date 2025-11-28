/**
 * Metrics Dashboard - Main JavaScript Controller
 *
 * This module handles:
 * - Initial data loading via REST API
 * - KPI card updates
 * - Chart updates via charts.js
 * - Theme management (dark/light mode)
 * - Time range filtering
 * - Manual refresh
 */

// Dashboard Controller
class MetricsDashboard {
    constructor() {
        this.apiClient = null;  // Will be initialized in initialize()
        this.charts = {};  // Will hold Chart.js instances
        this.currentData = {
            summary: null,
            webhooks: null,
            repositories: null
        };
        this.timeRange = '24h';  // Default time range
        this.repositoryFilter = '';  // Repository filter lowercase for local comparisons (empty = show all)
        this.repositoryFilterRaw = '';  // Repository filter original case for API calls
        this.userFilter = '';  // User filter (empty = show all)
        this.repositoryComboBox = null;  // ComboBox instance for repository filter
        this.userComboBox = null;  // ComboBox instance for user filter

        // Pagination state for each section
        this.pagination = {
            topRepositories: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
            recentEvents: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
            prCreators: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
            prReviewers: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
            prApprovers: { page: 1, pageSize: 10, total: 0, totalPages: 0 },
            userPrs: { page: 1, pageSize: 10, total: 0, totalPages: 0 }
        };

        // Sort state for each table
        this.tableSortState = {
            topRepositories: { column: null, direction: 'asc' },
            recentEvents: { column: null, direction: 'asc' },
            prCreators: { column: null, direction: 'asc' },
            prReviewers: { column: null, direction: 'asc' },
            prApprovers: { column: null, direction: 'asc' },
            userPrs: { column: null, direction: 'asc' }
        };

        // Load saved page sizes from localStorage
        Object.keys(this.pagination).forEach(section => {
            const saved = localStorage.getItem(`pageSize_${section}`);
            if (saved) {
                this.pagination[section].pageSize = parseInt(saved, 10);
            }
        });

        // Note: Dashboard self-initializes asynchronously.
        // Callers should not assume immediate readiness after construction.
        this.initialize();
    }

    /**
     * Initialize dashboard - load theme, data, and charts.
     */
    async initialize() {
        console.log('[Dashboard] Initializing metrics dashboard');

        // 1. Initialize API client (from api-client.js loaded globally)
        this.apiClient = window.MetricsAPI?.apiClient;
        if (!this.apiClient) {
            console.error('[Dashboard] MetricsAPI client not found - ensure api-client.js is loaded');
            this.showError('Metrics API client not available. Please refresh the page.');
            return;
        }

        // 2. Set ready status
        this.updateConnectionStatus(true);

        // 3. Initialize theme
        this.initializeTheme();

        // 4. Set up event listeners
        this.setupEventListeners();

        // 5. Initialize ComboBox components
        this.initializeComboBoxes();

        // 6. Populate date inputs with default 24h range logic so they are not empty
        const { startTime, endTime } = this.getTimeRangeDates(this.timeRange);
        const startInput = document.getElementById('startTime');
        const endInput = document.getElementById('endTime');
        if (startInput && endInput) {
            startInput.value = this.formatDateForInput(startTime);
            endInput.value = this.formatDateForInput(endTime);
        }

        // 7. Show loading state
        this.showLoading(true);

        try {
            // 8. Load initial data via REST API
            await this.loadInitialData();

            // 9. Initialize charts (calls functions from charts.js)
            this.initializeCharts();

            console.log('[Dashboard] Dashboard initialization complete');
        } catch (error) {
            console.error('[Dashboard] Initialization error:', error);
            this.showError('Failed to load dashboard data. Please refresh the page.');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Load initial data from REST API endpoints.
     */
    async loadInitialData() {
        console.log('[Dashboard] Loading initial data...');

        try {
            const { startTime, endTime } = this.getTimeRangeDates(this.timeRange);
            console.log(`[Dashboard] Time range: ${this.timeRange} (${startTime} to ${endTime})`);

            // Fetch all data in parallel using apiClient
            // Use bucket='hour' for ranges <= 24h, 'day' for others
            const bucket = (this.timeRange === '1h' || this.timeRange === '24h') ? 'hour' : 'day';

            const [summaryData, webhooksData, reposData, trendsData, contributorsData, userPrsData] = await Promise.all([
                this.apiClient.fetchSummary(startTime, endTime),
                this.apiClient.fetchWebhooks({ page: 1, page_size: 10, start_time: startTime, end_time: endTime }),
                this.apiClient.fetchRepositories(startTime, endTime, { page: 1, page_size: 10 }),
                this.apiClient.fetchTrends(startTime, endTime, bucket).catch(err => {
                    console.warn('[Dashboard] Trends endpoint not available:', err);
                    return { trends: [] }; // Return empty trends if endpoint doesn't exist
                }),
                this.apiClient.fetchContributors(startTime, endTime, 10, { page: 1, page_size: 10 }),
                this.apiClient.fetchUserPRs(startTime, endTime, { page: 1, page_size: 10 }).catch(err => {
                    console.warn('[Dashboard] User PRs endpoint error:', err);
                    return { data: [], pagination: { total: 0, page: 1, page_size: 10, total_pages: 0 } };
                })
            ]);

            // Check for errors in responses
            if (summaryData.error) {
                console.error('[Dashboard] Summary fetch error:', summaryData);
                throw new Error(summaryData.detail || 'Failed to fetch summary data');
            }
            if (webhooksData.error) {
                console.error('[Dashboard] Webhooks fetch error:', webhooksData);
                throw new Error(webhooksData.detail || 'Failed to fetch webhooks data');
            }
            if (reposData.error) {
                console.error('[Dashboard] Repositories fetch error:', reposData);
                throw new Error(reposData.detail || 'Failed to fetch repositories data');
            }
            if (trendsData.error) {
                console.error('[Dashboard] Trends fetch error:', trendsData);
                // Don't fail completely if trends fail, just log it
            }

            // Store data (preserve full paginated responses for tables)
            this.currentData = {
                summary: summaryData.summary || summaryData,
                topRepositories: summaryData.top_repositories || [],  // Store top-level top_repositories
                webhooks: webhooksData,  // Store full response with pagination
                repositories: reposData,  // Store full response with pagination
                trends: trendsData.trends || [],
                contributors: contributorsData,  // Store full response with pagination
                eventTypeDistribution: summaryData.event_type_distribution || {},  // Store top-level event_type_distribution
                userPrs: userPrsData  // Store user PRs data for sorting
            };

            console.log('[Dashboard] Initial data loaded:', this.currentData);

            // Update UI with loaded data
            this.updateKPITooltip(summaryData.summary || summaryData);
            this.updateCharts(this.currentData);

            // Update User PRs table
            console.log('[Dashboard] Updating User PRs table with data:', userPrsData);
            this.updateUserPRsTable(userPrsData);

            // Populate filter dropdowns
            this.populateRepositoryFilter();
            this.populateUserFilter();

        } catch (error) {
            console.error('[Dashboard] Error loading initial data:', error);
            throw error;
        }
    }

    /**
     * Calculate start and end dates based on selected time range.
     * @param {string} range - Time range identifier
     * @returns {Object} { startTime, endTime } in ISO format
     */
    getTimeRangeDates(range) {
        const now = new Date();
        let start = new Date();

        switch (range) {
            case '1h':
                start.setHours(now.getHours() - 1);
                break;
            case '24h':
                start.setHours(now.getHours() - 24);
                break;
            case '7d':
                start.setDate(now.getDate() - 7);
                break;
            case '30d':
                start.setDate(now.getDate() - 30);
                break;
            case 'custom': {
                // Handle custom range inputs
                const startInput = document.getElementById('startTime');
                const endInput = document.getElementById('endTime');
                if (startInput && endInput && startInput.value && endInput.value) {
                    return {
                        startTime: new Date(startInput.value).toISOString(),
                        endTime: new Date(endInput.value).toISOString()
                    };
                }
                // Fallback to 24h if inputs invalid
                start.setHours(now.getHours() - 24);
                break;
            }
            default:
                // Default to 24h if unknown
                start.setHours(now.getHours() - 24);
        }

        return {
            startTime: start.toISOString(),
            endTime: now.toISOString()
        };
    }

    /**
     * Format ISO date string for datetime-local input.
     * Converts ISO string to local timezone and formats for HTML5 datetime-local input.
     *
     * @param {string} isoString - ISO date string
     * @returns {string} Formatted string (YYYY-MM-DDThh:mm)
     */
    formatDateForInput(isoString) {
        const date = new Date(isoString);
        // Adjust for local timezone for display
        const localDate = new Date(date.getTime() - (date.getTimezoneOffset() * 60000));
        return localDate.toISOString().slice(0, 16);
    }

    /**
     * Update KPI tooltip with new data.
     *
     * @param {Object} summary - Summary data
     */
    updateKPITooltip(summary) {
        if (!summary) {
            console.warn('[Dashboard] No summary data to update KPI tooltip');
            return;
        }

        // Total Events
        this.updateTooltipMetric('tooltipTotalEvents', 'tooltipTotalEventsTrend', {
            value: summary.total_events ?? 0,
            trend: summary.total_events_trend ?? 0
        });

        // Success Rate
        const successRate = summary.success_rate ??
            (summary.total_events > 0 ? (summary.successful_events / summary.total_events * 100) : 0);
        this.updateTooltipMetric('tooltipSuccessRate', 'tooltipSuccessRateTrend', {
            value: `${successRate.toFixed(2)}%`,
            trend: summary.success_rate_trend ?? 0
        });

        // Failed Events
        this.updateTooltipMetric('tooltipFailedEvents', 'tooltipFailedEventsTrend', {
            value: summary.failed_events ?? 0,
            trend: summary.failed_events_trend ?? 0
        });

        // Average Duration
        const avgDuration = summary.avg_duration_ms ?? summary.avg_processing_time_ms ?? 0;
        this.updateTooltipMetric('tooltipAvgDuration', 'tooltipAvgDurationTrend', {
            value: window.MetricsUtils.formatDuration(avgDuration),
            trend: summary.avg_duration_trend ?? 0
        });

        console.log('[Dashboard] KPI tooltip updated');
    }

    /**
     * Update individual metric in tooltip.
     *
     * @param {string} valueId - Value element ID
     * @param {string} trendId - Trend element ID
     * @param {Object} data - Metric data
     */
    updateTooltipMetric(valueId, trendId, data) {
        const valueElement = document.getElementById(valueId);
        const trendElement = document.getElementById(trendId);

        if (valueElement) {
            valueElement.textContent = data.value;
        }

        if (trendElement) {
            const trend = data.trend || 0;
            const trendClass = trend > 0 ? 'positive' : trend < 0 ? 'negative' : 'neutral';
            const trendIcon = trend > 0 ? '↑' : trend < 0 ? '↓' : '→';

            trendElement.className = `kpi-trend-text ${trendClass}`;
            trendElement.textContent = `(${trendIcon} ${Math.abs(trend).toFixed(1)}% vs last period)`;
        }
    }

    /**
     * Initialize all charts (calls functions from charts.js).
     * Note: Chart sections have been removed from the dashboard for simplification.
     * This method is kept for backward compatibility but does nothing.
     */
    initializeCharts() {
        console.log('[Dashboard] Chart initialization skipped (charts removed from UI)');
        // Charts have been removed from the dashboard
        // Keeping this method to avoid breaking existing code references
    }

    /**
     * Normalize repositories data from paginated response to array.
     * Handles both paginated response objects and plain arrays.
     * Supports both current ({ data: [...] }) and legacy ({ repositories: [...] }) shapes.
     *
     * @param {Object|Array} repositories - Repositories data (paginated response or array)
     * @returns {Array} Normalized array of repositories
     */
    normalizeRepositories(repositories) {
        if (!repositories) {
            return [];
        }
        // If already an array, return as-is
        if (Array.isArray(repositories)) {
            return repositories;
        }
        // Handle paginated response format: { data: [...] } or legacy { repositories: [...] }
        return repositories.data || repositories.repositories || [];
    }

    /**
     * Update all charts with new data.
     *
     * @param {Object} data - Complete dashboard data
     */
    updateCharts(data) {
        if (!data || !window.MetricsCharts) {
            console.warn('[Dashboard] No data or MetricsCharts library not available');
            return;
        }

        // Create working copy to avoid mutating original data
        // This allows filter to be cleared and original data restored
        // Extract arrays from paginated responses for filtering
        const workingData = {
            summary: { ...data.summary },
            webhooks: data.webhooks?.data || data.webhooks || [],
            repositories: this.normalizeRepositories(data.repositories),
            trends: data.trends,
            contributors: data.contributors ? {
                pr_creators: data.contributors.pr_creators?.data || data.contributors.pr_creators || [],
                pr_reviewers: data.contributors.pr_reviewers?.data || data.contributors.pr_reviewers || [],
                pr_approvers: data.contributors.pr_approvers?.data || data.contributors.pr_approvers || []
            } : null,
            eventTypeDistribution: data.eventTypeDistribution
        };

        const summary = workingData.summary;
        let webhooks = workingData.webhooks;
        let repositories = workingData.repositories;
        const trends = workingData.trends;

        // Apply repository filter
        let filteredWebhooks = webhooks;
        let filteredRepositories = repositories;
        let filteredContributors = workingData.contributors;
        let filteredSummary = summary;

        if (this.repositoryFilter) {
            // Filter webhooks and repositories
            filteredWebhooks = this.filterDataByRepository(webhooks);
            filteredRepositories = this.filterDataByRepository(repositories);

            // Recalculate event type distribution from filtered webhooks
            const eventTypeCount = {};
            filteredWebhooks.forEach(event => {
                const eventType = event.event_type || 'unknown';
                eventTypeCount[eventType] = (eventTypeCount[eventType] || 0) + 1;
            });
            workingData.eventTypeDistribution = eventTypeCount;

            // Filter contributors by repository
            // Extract repository from webhook events to find users active in this repo
            if (workingData.contributors) {
                const usersInRepo = new Set();
                filteredWebhooks.forEach(event => {
                    const user = event.sender || event.user || (event.payload && (event.payload.sender || event.payload.user));
                    if (user) {
                        usersInRepo.add(user);
                    }
                });

                filteredContributors = {
                    pr_creators: (workingData.contributors.pr_creators || []).filter(c => usersInRepo.has(c.user)),
                    pr_reviewers: (workingData.contributors.pr_reviewers || []).filter(c => usersInRepo.has(c.user)),
                    pr_approvers: (workingData.contributors.pr_approvers || []).filter(c => usersInRepo.has(c.user))
                };
            }

            // Recalculate summary for filtered data
            filteredSummary = {
                ...summary,  // Keep original fields
                total_events: filteredWebhooks.length,
                successful_events: filteredWebhooks.filter(e => e.status === 'success').length,
                failed_events: filteredWebhooks.filter(e => e.status === 'error').length,
            };
            filteredSummary.success_rate = filteredSummary.total_events > 0
                ? (filteredSummary.successful_events / filteredSummary.total_events * 100)
                : 0;

            console.log(`[Dashboard] Filtered by repository: ${filteredWebhooks.length} events, ${filteredRepositories.length} repos`);
        }

        // Apply user filter second (on already-filtered data)
        if (this.userFilter && filteredContributors) {
            filteredContributors = {
                pr_creators: this.filterDataByUser(filteredContributors.pr_creators || []),
                pr_reviewers: this.filterDataByUser(filteredContributors.pr_reviewers || []),
                pr_approvers: this.filterDataByUser(filteredContributors.pr_approvers || [])
            };

            console.log(`[Dashboard] Filtered by user: ${filteredContributors.pr_creators.length} creators, ${filteredContributors.pr_reviewers.length} reviewers, ${filteredContributors.pr_approvers.length} approvers`);
        }

        // ALWAYS update KPI tooltip (whether filtered or not)
        this.updateKPITooltip(filteredSummary);

        // Use filtered data for chart updates
        webhooks = filteredWebhooks;
        repositories = filteredRepositories;
        if (filteredContributors) {
            workingData.contributors = filteredContributors;
        }

        try {
            // Note: Chart update logic has been removed as charts are no longer in the UI

            // Update Repository Table with top repositories from summary (has percentage field)
            if (data.topRepositories && data.topRepositories.length > 0) {
                // Top repositories from summary endpoint (has percentage field)
                // Apply repository filter if active
                const topRepos = this.repositoryFilter
                    ? data.topRepositories.filter(repo =>
                        repo.repository && repo.repository.toLowerCase().includes(this.repositoryFilter))
                    : data.topRepositories;
                this.updateRepositoryTable(topRepos);
            }

            // Update Recent Events Table with filtered data
            if (data.webhooks) {
                // Preserve pagination shape if original had it, otherwise pass filtered array
                const webhooksForTable = data.webhooks.data
                    ? { ...data.webhooks, data: filteredWebhooks }
                    : filteredWebhooks;
                this.updateRecentEventsTable(webhooksForTable);
            }

            // Update Contributors Tables with filtered data
            if (data.contributors) {
                // Preserve pagination shapes for each contributor type
                const contributorsForTable = {
                    pr_creators: data.contributors.pr_creators?.data
                        ? { ...data.contributors.pr_creators, data: filteredContributors.pr_creators }
                        : filteredContributors.pr_creators,
                    pr_reviewers: data.contributors.pr_reviewers?.data
                        ? { ...data.contributors.pr_reviewers, data: filteredContributors.pr_reviewers }
                        : filteredContributors.pr_reviewers,
                    pr_approvers: data.contributors.pr_approvers?.data
                        ? { ...data.contributors.pr_approvers, data: filteredContributors.pr_approvers }
                        : filteredContributors.pr_approvers
                };
                this.updateContributorsTables(contributorsForTable);
            }

            console.log('[Dashboard] Charts updated');
        } catch (error) {
            console.error('[Dashboard] Error updating charts:', error);
        }
    }

    /**
     * Process trends data from API for chart.
     * Note: This method is kept for backward compatibility but is no longer used.
     * @param {Array} trends - Trends data from API
     * @returns {Object} Chart data
     */
    processTrendsData(trends) {
        // Method kept for backward compatibility
        // Charts have been removed from the dashboard
        return { labels: [], success: [], errors: [], total: [] };
    }

    /**
     * Update repository table with new data.
     *
     * @param {Object|Array} reposData - Repository data with pagination ({data: [...], pagination: {...}}) or plain array
     */
    updateRepositoryTable(reposData) {
        const tableBody = document.getElementById('repository-table-body');
        if (!tableBody) {
            console.warn('[Dashboard] Repository table body not found');
            return;
        }

        // Handle both paginated response and plain array formats
        const repositories = Array.isArray(reposData) ? reposData : (reposData.data || reposData.repositories || []);
        const pagination = Array.isArray(reposData) ? null : reposData.pagination;

        // Update pagination state if available
        if (pagination) {
            this.pagination.topRepositories = {
                page: pagination.page,
                pageSize: pagination.page_size,
                total: pagination.total,
                totalPages: pagination.total_pages
            };
        }

        if (!repositories || !Array.isArray(repositories) || repositories.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="3" style="text-align: center;">No repository data available</td></tr>';
            return;
        }

        // Generate table rows - show percentage of total events
        const rows = repositories.map(repo => {
            const percentage = repo.percentage || 0; // Percentage of total events
            return `
                <tr>
                    <td>${this.escapeHtml(repo.repository || 'Unknown')}</td>
                    <td>${repo.total_events || 0}</td>
                    <td>${percentage.toFixed(1)}%</td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = rows;

        // Add pagination controls
        const container = document.querySelector('[data-section="top-repositories"] .chart-content');
        const existingControls = container?.querySelector('.pagination-controls');
        if (existingControls) {
            existingControls.remove();
        }

        if (container && pagination) {
            container.insertAdjacentHTML('beforeend', this.createPaginationControls('top-repositories'));
        }
    }

    /**
     * Update recent events table with new data.
     *
     * @param {Object|Array} eventsData - Recent webhook events (can be array or {data: [...], pagination: {...}})
     */
    updateRecentEventsTable(eventsData) {
        const tableBody = document.querySelector('#recentEventsTable tbody');
        if (!tableBody) {
            console.warn('[Dashboard] Recent events table body not found');
            return;
        }

        // Handle both array format and paginated response format
        const events = Array.isArray(eventsData) ? eventsData : (eventsData.data || eventsData.events || []);
        const pagination = Array.isArray(eventsData) ? null : eventsData.pagination;

        // Update pagination state if available
        if (pagination) {
            this.pagination.recentEvents = {
                page: pagination.page,
                pageSize: pagination.page_size,
                total: pagination.total,
                totalPages: pagination.total_pages
            };
        }

        if (!events || !Array.isArray(events) || events.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No recent events</td></tr>';
            return;
        }

        // Generate table rows
        const rows = events.map(event => {
            const time = new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
            const status = event.status || 'unknown';
            const statusClass = status === 'success' ? 'status-success' : status === 'error' ? 'status-error' : 'status-partial';

            return `
                <tr>
                    <td>${time}</td>
                    <td>${this.escapeHtml(event.repository || 'Unknown')}</td>
                    <td>${this.escapeHtml(event.event_type || 'unknown')}</td>
                    <td><span class="${statusClass}">${status}</span></td>
                </tr>
            `;
        }).join('');

        tableBody.innerHTML = rows;

        // Add pagination controls
        const container = document.querySelector('[data-section="recent-events"] .chart-content');
        const existingControls = container?.querySelector('.pagination-controls');
        if (existingControls) {
            existingControls.remove();
        }

        if (container && pagination) {
            container.insertAdjacentHTML('beforeend', this.createPaginationControls('recent-events'));
        }
    }

    /**
     * Update PR contributors tables with new data.
     *
     * @param {Object} contributors - Contributors data with pagination
     */
    updateContributorsTables(contributors) {
        if (!contributors) {
            console.warn('[Dashboard] No contributors data available');
            return;
        }

        // Extract data and pagination for PR Creators
        const prCreatorsData = contributors.pr_creators?.data || contributors.pr_creators || [];
        const prCreatorsPagination = contributors.pr_creators?.pagination;

        if (prCreatorsPagination) {
            this.pagination.prCreators = {
                page: prCreatorsPagination.page,
                pageSize: prCreatorsPagination.page_size,
                total: prCreatorsPagination.total,
                totalPages: prCreatorsPagination.total_pages
            };
        }

        // Update PR Creators table
        this.updateContributorsTable(
            'pr-creators-table-body',
            prCreatorsData,
            (creator) => `
                <tr>
                    <td><span class="clickable-username" data-user="${this.escapeHtml(creator.user)}">${this.escapeHtml(creator.user)}</span></td>
                    <td>${creator.total_prs}</td>
                    <td>${creator.merged_prs}</td>
                    <td>${creator.closed_prs}</td>
                    <td>${creator.avg_commits_per_pr || 0}</td>
                </tr>
            `
        );

        // Add pagination controls for PR Creators
        const creatorsContainer = document.querySelector('[data-section="pr-creators"]');
        const creatorsExistingControls = creatorsContainer?.querySelector('.pagination-controls');
        if (creatorsExistingControls) {
            creatorsExistingControls.remove();
        }
        if (creatorsContainer && prCreatorsPagination) {
            creatorsContainer.insertAdjacentHTML('beforeend', this.createPaginationControls('prCreators'));
        }

        // Extract data and pagination for PR Reviewers
        const prReviewersData = contributors.pr_reviewers?.data || contributors.pr_reviewers || [];
        const prReviewersPagination = contributors.pr_reviewers?.pagination;

        if (prReviewersPagination) {
            this.pagination.prReviewers = {
                page: prReviewersPagination.page,
                pageSize: prReviewersPagination.page_size,
                total: prReviewersPagination.total,
                totalPages: prReviewersPagination.total_pages
            };
        }

        // Update PR Reviewers table
        this.updateContributorsTable(
            'pr-reviewers-table-body',
            prReviewersData,
            (reviewer) => `
                <tr>
                    <td><span class="clickable-username" data-user="${this.escapeHtml(reviewer.user)}">${this.escapeHtml(reviewer.user)}</span></td>
                    <td>${reviewer.total_reviews}</td>
                    <td>${reviewer.prs_reviewed}</td>
                    <td>${reviewer.avg_reviews_per_pr}</td>
                </tr>
            `
        );

        // Add pagination controls for PR Reviewers
        const reviewersContainer = document.querySelector('[data-section="pr-reviewers"]');
        const reviewersExistingControls = reviewersContainer?.querySelector('.pagination-controls');
        if (reviewersExistingControls) {
            reviewersExistingControls.remove();
        }
        if (reviewersContainer && prReviewersPagination) {
            reviewersContainer.insertAdjacentHTML('beforeend', this.createPaginationControls('prReviewers'));
        }

        // Extract data and pagination for PR Approvers
        const prApproversData = contributors.pr_approvers?.data || contributors.pr_approvers || [];
        const prApproversPagination = contributors.pr_approvers?.pagination;

        if (prApproversPagination) {
            this.pagination.prApprovers = {
                page: prApproversPagination.page,
                pageSize: prApproversPagination.page_size,
                total: prApproversPagination.total,
                totalPages: prApproversPagination.total_pages
            };
        }

        // Update PR Approvers table
        this.updateContributorsTable(
            'pr-approvers-table-body',
            prApproversData,
            (approver) => `
                <tr>
                    <td><span class="clickable-username" data-user="${this.escapeHtml(approver.user)}">${this.escapeHtml(approver.user)}</span></td>
                    <td>${approver.total_approvals}</td>
                    <td>${approver.prs_approved}</td>
                </tr>
            `
        );

        // Add pagination controls for PR Approvers
        const approversContainer = document.querySelector('[data-section="pr-approvers"]');
        const approversExistingControls = approversContainer?.querySelector('.pagination-controls');
        if (approversExistingControls) {
            approversExistingControls.remove();
        }
        if (approversContainer && prApproversPagination) {
            approversContainer.insertAdjacentHTML('beforeend', this.createPaginationControls('prApprovers'));
        }
    }

    /**
     * Generic contributor table updater.
     *
     * @param {string} tableBodyId - Table body element ID
     * @param {Array} data - Contributors data array
     * @param {Function} rowGenerator - Function to generate table row HTML
     */
    updateContributorsTable(tableBodyId, data, rowGenerator) {
        const tableBody = document.getElementById(tableBodyId);
        if (!tableBody) {
            console.warn(`[Dashboard] Table body not found: ${tableBodyId}`);
            return;
        }

        if (!data || data.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center;">No data available</td></tr>';
            return;
        }

        const rows = data.map(rowGenerator).join('');
        tableBody.innerHTML = rows;
    }

    /**
     * Set up event listeners for UI controls.
     */
    setupEventListeners() {
        // Theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Time range selector
        const timeRangeSelect = document.getElementById('time-range-select');
        if (timeRangeSelect) {
            timeRangeSelect.addEventListener('change', (e) => this.changeTimeRange(e.target.value));
        }

        // Custom date inputs
        const startTimeInput = document.getElementById('startTime');
        const endTimeInput = document.getElementById('endTime');

        if (startTimeInput && endTimeInput) {
            const handleCustomDateChange = () => {
                // Switch dropdown to custom if not already
                if (timeRangeSelect && timeRangeSelect.value !== 'custom') {
                    timeRangeSelect.value = 'custom';
                    this.timeRange = 'custom';
                }
                // Only reload if both dates are valid
                if (startTimeInput.value && endTimeInput.value) {
                    this.changeTimeRange('custom');
                }
            };

            startTimeInput.addEventListener('change', handleCustomDateChange);
            endTimeInput.addEventListener('change', handleCustomDateChange);
        }

        // Manual refresh button
        const refreshButton = document.getElementById('refresh-button');
        if (refreshButton) {
            refreshButton.addEventListener('click', () => this.manualRefresh());
        }

        // Clickable usernames - set ComboBox value and trigger filter
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('clickable-username')) {
                const username = e.target.dataset.user;
                if (this.userComboBox) {
                    this.userComboBox.setValue(username);
                    this.filterByUser(username);
                }
            }
        });

        // PR Story button - delegated handler
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.pr-story-btn');
            if (btn) {
                const repo = btn.dataset.repo;
                const pr = Number(btn.dataset.pr);
                if (window.openPRStory && repo && !isNaN(pr)) {
                    window.openPRStory(repo, pr);
                }
            }
        });

        // Pagination listeners
        this.setupPaginationListeners();

        // Sort listeners
        this.setupSortListeners();

        // Collapse buttons
        this.setupCollapseButtons();

        // Note: Chart settings event listeners have been removed as charts are no longer in the UI

        console.log('[Dashboard] Event listeners set up');
    }

    /**
     * Initialize ComboBox components for repository and user filters.
     */
    initializeComboBoxes() {
        const repoContainer = document.getElementById('repository-filter-group');
        if (repoContainer && window.ComboBox) {
            this.repositoryComboBox = new window.ComboBox({
                container: repoContainer,
                inputId: 'repositoryFilter',
                placeholder: 'Type to search or select...',
                options: [{ value: '', label: 'All Repositories' }],
                allowFreeText: true,
                onSelect: (value) => this.filterByRepository(value),
                onInput: (value) => this.filterByRepository(value)
            });
            console.log('[Dashboard] Repository ComboBox initialized');
        }

        const userContainer = document.getElementById('user-filter-group');
        if (userContainer && window.ComboBox) {
            this.userComboBox = new window.ComboBox({
                container: userContainer,
                inputId: 'userFilter',
                placeholder: 'Type to search or select...',
                options: [{ value: '', label: 'All Users' }],
                allowFreeText: true,
                onSelect: (value) => this.filterByUser(value),
                onInput: (value) => this.filterByUser(value)
            });
            console.log('[Dashboard] User ComboBox initialized');
        }
    }

    /**
     * Set up collapse button listeners and restore collapsed state.
     */
    setupCollapseButtons() {
        const collapseButtons = document.querySelectorAll('.collapse-btn');
        collapseButtons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const sectionId = e.currentTarget.dataset.section;
                this.toggleSection(sectionId);
            });
        });

        // Restore collapsed state from localStorage
        this.restoreCollapsedSections();
    }

    /**
     * Toggle a section's collapsed state.
     * @param {string} sectionId - Section identifier
     */
    toggleSection(sectionId) {
        const section = document.querySelector(`[data-section="${sectionId}"]`);
        if (!section) {
            console.warn(`[Dashboard] Section not found: ${sectionId}`);
            return;
        }

        section.classList.toggle('collapsed');

        // Update button icon
        const btn = section.querySelector(`.collapse-btn[data-section="${sectionId}"]`);
        if (btn) {
            btn.textContent = section.classList.contains('collapsed') ? '▲' : '▼';
            btn.title = section.classList.contains('collapsed') ? 'Expand' : 'Collapse';
        }

        // Save state
        this.saveCollapsedState(sectionId, section.classList.contains('collapsed'));

        console.log(`[Dashboard] Section ${sectionId} ${section.classList.contains('collapsed') ? 'collapsed' : 'expanded'}`);
    }

    /**
     * Save collapsed state to localStorage.
     * @param {string} sectionId - Section identifier
     * @param {boolean} isCollapsed - Whether section is collapsed
     */
    saveCollapsedState(sectionId, isCollapsed) {
        const state = JSON.parse(localStorage.getItem('collapsedSections') || '{}');
        state[sectionId] = isCollapsed;
        localStorage.setItem('collapsedSections', JSON.stringify(state));
    }

    /**
     * Restore collapsed sections from localStorage.
     */
    restoreCollapsedSections() {
        const state = JSON.parse(localStorage.getItem('collapsedSections') || '{}');
        Object.keys(state).forEach(sectionId => {
            if (state[sectionId]) {
                const section = document.querySelector(`[data-section="${sectionId}"]`);
                if (section) {
                    section.classList.add('collapsed');
                    const btn = section.querySelector(`.collapse-btn[data-section="${sectionId}"]`);
                    if (btn) {
                        btn.textContent = '▲';
                        btn.title = 'Expand';
                    }
                }
            }
        });
        console.log('[Dashboard] Collapsed sections restored from localStorage');
    }

    /**
     * Initialize theme from localStorage and apply it.
     */
    initializeTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        console.log(`[Dashboard] Theme initialized: ${savedTheme}`);
    }

    /**
     * Toggle between dark and light theme.
     */
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);

        console.log(`[Dashboard] Theme changed to: ${newTheme}`);

        // Recreate charts with new theme colors
        if (this.currentData && this.currentData.summary) {
            // Destroy existing charts
            Object.values(this.charts).forEach(chart => {
                if (chart && typeof chart.destroy === 'function') {
                    chart.destroy();
                }
            });

            // Clear charts object
            this.charts = {};

            // Recreate charts with new theme
            this.initializeCharts();
        }
    }

    /**
     * Change time range and reload data.
     *
     * @param {string} timeRange - New time range ('24h', '7d', '30d', etc.)
     */
    async changeTimeRange(timeRange) {
        console.log(`[Dashboard] Changing time range to: ${timeRange}`);
        this.timeRange = timeRange;

        // If preset selected, populate inputs
        if (timeRange !== 'custom') {
            const { startTime, endTime } = this.getTimeRangeDates(timeRange);
            const startInput = document.getElementById('startTime');
            const endInput = document.getElementById('endTime');

            if (startInput && endInput) {
                startInput.value = this.formatDateForInput(startTime);
                endInput.value = this.formatDateForInput(endTime);
            }
        }

        // For custom range, validation
        if (timeRange === 'custom') {
            const startInput = document.getElementById('startTime');
            const endInput = document.getElementById('endTime');
            if (!startInput?.value || !endInput?.value) {
                return;
            }
        }

        this.showLoading(true);
        try {
            await this.loadInitialData();
        } catch (error) {
            console.error('[Dashboard] Error changing time range:', error);
            this.showError('Failed to load data for selected time range');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Manually refresh all data.
     */
    async manualRefresh() {
        console.log('[Dashboard] Manual refresh triggered');

        this.showLoading(true);
        try {
            await this.loadInitialData();
            this.updateCharts(this.currentData);
            this.showSuccessNotification('Dashboard refreshed successfully');
        } catch (error) {
            console.error('[Dashboard] Error during manual refresh:', error);
            this.showError('Failed to refresh dashboard');
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Filter dashboard data by repository name.
     *
     * @param {string} filterValue - Repository name or partial name to filter by
     */
    filterByRepository(filterValue) {
        // Keep original input for API call (backend may be case-sensitive)
        const trimmedFilter = filterValue.trim();

        // Check if filter actually changed (case-insensitive comparison)
        if (trimmedFilter.toLowerCase() === this.repositoryFilter) {
            return;  // No change, skip update
        }

        // Store BOTH: original case for API calls, lowercase for local filtering
        this.repositoryFilterRaw = trimmedFilter;
        this.repositoryFilter = trimmedFilter.toLowerCase();
        console.log(`[Dashboard] Filtering by repository: "${this.repositoryFilter || '(showing all)'}"`);

        // ALWAYS re-render charts and tables (even when filter is cleared)
        if (this.currentData) {
            this.updateCharts(this.currentData);
        }
    }

    /**
     * Filter data array by repository name.
     *
     * @param {Array} data - Array of data objects with 'repository' field
     * @returns {Array} Filtered data
     */
    filterDataByRepository(data) {
        if (!this.repositoryFilter || !Array.isArray(data)) {
            return data;  // No filter or invalid data, return as-is
        }

        // Use lowercase for local includes() check
        return data.filter(item => {
            const repo = (item.repository || '').toLowerCase();
            return repo.includes(this.repositoryFilter);
        });
    }

    /**
     * Filter dashboard data by user.
     *
     * @param {string} filterValue - User to filter by
     */
    filterByUser(filterValue) {
        const newFilter = filterValue.trim();

        // Check if filter actually changed
        if (newFilter === this.userFilter) {
            return;  // No change, skip update
        }

        this.userFilter = newFilter;
        console.log(`[Dashboard] Filtering by user: "${this.userFilter || '(showing all users)'}"`);

        // Re-render charts and tables
        if (this.currentData) {
            this.updateCharts(this.currentData);
        }
    }

    /**
     * Filter data array by user.
     *
     * @param {Array} data - Array of contributor data
     * @returns {Array} Filtered data
     */
    filterDataByUser(data) {
        if (!this.userFilter || !Array.isArray(data)) {
            return data;  // No filter or invalid data, return as-is
        }

        return data.filter(item => {
            const user = (item.user || '').toLowerCase();
            return user === this.userFilter.toLowerCase();
        });
    }

    /**
     * Populate repository filter combo-box from repositories data.
     */
    populateRepositoryFilter() {
        if (!this.repositoryComboBox) {
            console.warn('[Dashboard] Repository ComboBox not initialized');
            return;
        }

        const repositories = new Set();
        if (this.currentData.repositories) {
            const reposArray = this.normalizeRepositories(this.currentData.repositories);
            reposArray.forEach(repo => {
                if (repo.repository) {
                    repositories.add(repo.repository);
                }
            });
        }

        const options = [{ value: '', label: 'All Repositories' }];
        Array.from(repositories).sort().forEach(repo => {
            options.push({ value: repo, label: repo });
        });

        this.repositoryComboBox.setOptions(options);
        console.log(`[Dashboard] Repository filter populated with ${repositories.size} repositories`);
    }

    /**
     * Populate user filter combo-box from contributors data.
     */
    populateUserFilter() {
        if (!this.userComboBox) {
            console.warn('[Dashboard] User ComboBox not initialized');
            return;
        }

        // Collect all unique users from contributors data
        const users = new Set();

        if (this.currentData.contributors) {
            const { pr_creators, pr_reviewers, pr_approvers } = this.currentData.contributors;

            // Extract data arrays from paginated responses
            const creatorsData = pr_creators?.data || pr_creators || [];
            const reviewersData = pr_reviewers?.data || pr_reviewers || [];
            const approversData = pr_approvers?.data || pr_approvers || [];

            // Add users from all contributor types
            [...creatorsData, ...reviewersData, ...approversData]
                .forEach(contributor => {
                    if (contributor.user) {
                        users.add(contributor.user);
                    }
                });
        }

        const options = [{ value: '', label: 'All Users' }];
        Array.from(users).sort().forEach(user => {
            options.push({ value: user, label: user });
        });

        this.userComboBox.setOptions(options);
        console.log(`[Dashboard] User filter populated with ${users.size} users`);
    }

    /**
     * Update connection status indicator.
     *
     * @param {boolean} ready - Dashboard ready status
     */
    updateConnectionStatus(ready) {
        const statusElement = document.getElementById('connection-status');
        const statusText = document.getElementById('statusText');

        if (!statusElement || !statusText) {
            return;
        }

        if (ready) {
            statusElement.className = 'status connected';
            statusText.textContent = 'Ready';
        } else {
            statusElement.className = 'status disconnected';
            statusText.textContent = 'Initializing...';
        }

        console.log(`[Dashboard] Status: ${ready ? 'Ready' : 'Initializing'}`);
    }

    /**
     * Show loading spinner.
     *
     * @param {boolean} show - Whether to show or hide loading spinner
     */
    showLoading(show) {
        const spinner = document.getElementById('loading-spinner');
        if (spinner) {
            spinner.style.display = show ? 'flex' : 'none';
            spinner.setAttribute('aria-busy', show ? 'true' : 'false');
        }
    }

    /**
     * Show error message.
     *
     * @param {string} message - Error message to display
     */
    showError(message) {
        console.error(`[Dashboard] Error: ${message}`);

        // Remove any existing error toast
        const existingToast = document.querySelector('.error-toast');
        if (existingToast) {
            existingToast.remove();
        }

        // Create non-blocking toast notification
        const toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.setAttribute('role', 'alert');
        toast.textContent = message;
        document.body.appendChild(toast);

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 5000);
    }

    /**
     * Show success notification.
     *
     * @param {string} message - Success message
     */
    showSuccessNotification(message) {
        console.log(`[Dashboard] Success: ${message}`);
        // Could implement toast notification here
    }

    /**
     * Prepare event trends data for line chart.
     * Note: This method is kept for backward compatibility but is no longer used.
     *
     * @param {Array} events - Array of webhook events
     * @returns {Object} Chart data with labels, success, errors, and total arrays
     */
    prepareEventTrendsData(events) {
        // Method kept for backward compatibility
        // Charts have been removed from the dashboard
        return { labels: [], success: [], errors: [], total: [] };
    }

    /**
     * Prepare API usage data for bar chart.
     * Note: This method is kept for backward compatibility but is no longer used.
     *
     * @param {Array} repositories - Array of repository statistics
     * @param {number} topN - Number of top repositories to show (default: 7)
     * @param {string} sortOrder - Sort order ('asc' or 'desc', default: 'desc')
     * @returns {Object} Chart data with labels and values arrays
     */
    prepareAPIUsageData(repositories, topN = 7, sortOrder = 'desc') {
        // Method kept for backward compatibility
        // Charts have been removed from the dashboard
        return { labels: [], values: [] };
    }

    /**
     * Note: Modal and chart customization functions have been removed
     * as charts are no longer part of the dashboard UI.
     * These methods were kept for backward compatibility in the codebase.
     */

    /**
     * Escape a CSV value by wrapping in quotes if needed and escaping internal quotes.
     * @param {*} value - Value to escape
     * @return {string} - Escaped CSV value
     */
    escapeCsvValue(value) {
        // Convert to string
        const stringValue = String(value ?? '');

        // Check if value needs escaping (contains comma, quote, or newline)
        const needsEscaping = /[",\n\r]/.test(stringValue);

        if (needsEscaping) {
            // Escape quotes by doubling them
            const escapedValue = stringValue.replace(/"/g, '""');
            // Wrap in quotes
            return `"${escapedValue}"`;
        }

        return stringValue;
    }

    /**
     * Download data as CSV or JSON file.
     * @param {Array} data - Data array to download
     * @param {string} filename - Output filename
     * @param {string} format - Format ('csv' or 'json')
     */
    downloadData(data, filename, format) {
        let content, mimeType;

        if (format === 'csv') {
            // Convert to CSV
            if (!data.length) return;
            const headers = Object.keys(data[0]).map(h => this.escapeCsvValue(h)).join(',');
            const rows = data.map(row =>
                Object.values(row).map(v => this.escapeCsvValue(v)).join(',')
            );
            content = [headers, ...rows].join('\n');
            mimeType = 'text/csv';
        } else {
            // JSON format
            content = JSON.stringify(data, null, 2);
            mimeType = 'application/json';
        }

        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }


    /**
     * Convert kebab-case to camelCase for pagination state keys
     * @param {string} kebabCase - kebab-case identifier
     * @returns {string} camelCase identifier
     */
    toCamelCase(kebabCase) {
        return kebabCase.replace(/-([a-z])/g, (g) => g[1].toUpperCase());
    }

    /**
     * Create pagination controls HTML
     * @param {string} section - Section identifier (kebab-case from HTML)
     * @returns {string} Pagination HTML
     */
    createPaginationControls(section) {
        // Convert kebab-case to camelCase for pagination state lookup
        const stateKey = this.toCamelCase(section);
        const state = this.pagination[stateKey];
        if (!state) {
            console.warn(`[Dashboard] No pagination state for section: ${section} (${stateKey})`);
            return '';
        }
        const { page, pageSize, total, totalPages } = state;

        const hasNext = page < totalPages;
        const hasPrev = page > 1;

        return `
            <div class="pagination-controls">
                <div class="pagination-size">
                    <label>Show</label>
                    <select class="page-size-select" data-section="${section}">
                        <option value="10" ${pageSize === 10 ? 'selected' : ''}>10</option>
                        <option value="25" ${pageSize === 25 ? 'selected' : ''}>25</option>
                        <option value="50" ${pageSize === 50 ? 'selected' : ''}>50</option>
                        <option value="100" ${pageSize === 100 ? 'selected' : ''}>100</option>
                    </select>
                    <label>per page</label>
                </div>
                <div class="pagination-nav">
                    <button class="btn-pagination" data-section="${section}" data-action="prev"
                            ${!hasPrev ? 'disabled' : ''}>← Prev</button>
                    <span class="pagination-info">Page ${page} of ${totalPages || 1}</span>
                    <button class="btn-pagination" data-section="${section}" data-action="next"
                            ${!hasNext ? 'disabled' : ''}>Next →</button>
                </div>
                <div class="pagination-total">
                    <span>Total: ${total} items</span>
                </div>
            </div>
        `;
    }

    /**
     * Handle page size change
     * @param {string} section - Section identifier
     * @param {number} newSize - New page size
     */
    async changePageSize(section, newSize) {
        this.pagination[section].pageSize = newSize;
        this.pagination[section].page = 1; // Reset to page 1
        localStorage.setItem(`pageSize_${section}`, newSize);

        await this.loadSectionData(section);
    }

    /**
     * Handle page navigation
     * @param {string} section - Section identifier
     * @param {string} action - 'next' or 'prev'
     */
    async navigatePage(section, action) {
        const state = this.pagination[section];

        if (action === 'next' && state.page < state.totalPages) {
            state.page++;
        } else if (action === 'prev' && state.page > 1) {
            state.page--;
        }

        await this.loadSectionData(section);
    }

    /**
     * Set up pagination event listeners
     */
    setupPaginationListeners() {
        // Page size selectors - debounced to prevent rapid consecutive API calls
        const debouncedPageSizeChange = window.MetricsUtils?.debounce((section, newSize) => {
            this.changePageSize(section, newSize);
        }, 300) || ((section, newSize) => this.changePageSize(section, newSize));

        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('page-size-select')) {
                const section = e.target.dataset.section; // kebab-case from HTML
                const stateKey = this.toCamelCase(section); // Convert to camelCase
                const newSize = parseInt(e.target.value, 10);
                debouncedPageSizeChange(stateKey, newSize);
            }
        });

        // Navigation buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('btn-pagination')) {
                const section = e.target.dataset.section; // kebab-case from HTML
                const stateKey = this.toCamelCase(section); // Convert to camelCase
                const action = e.target.dataset.action;
                if (!e.target.disabled) {
                    this.navigatePage(stateKey, action);
                }
            }
        });
    }

    /**
     * Load data for a specific section with pagination
     * @param {string} section - Section identifier
     */
    async loadSectionData(section) {
        const state = this.pagination[section];
        const { startTime, endTime } = this.getTimeRangeDates(this.timeRange);

        this.showLoading(true);

        try {
            let data;
            const params = {
                page: state.page,
                page_size: state.pageSize
            };

            // Add filters
            if (this.repositoryFilterRaw) {
                params.repository = this.repositoryFilterRaw;
            }
            if (this.userFilter) {
                params.user = this.userFilter;
            }

            switch (section) {
                case 'topRepositories':
                    data = await this.apiClient.fetchRepositories(startTime, endTime, params);
                    this.updateRepositoryTable(data);
                    break;
                case 'recentEvents':
                    params.start_time = startTime;
                    params.end_time = endTime;
                    data = await this.apiClient.fetchWebhooks(params);
                    this.updateRecentEventsTable(data);
                    break;
                case 'prCreators':
                case 'prReviewers':
                case 'prApprovers':
                    data = await this.apiClient.fetchContributors(startTime, endTime, state.pageSize, params);
                    this.updateContributorsTables(data);
                    break;
                case 'userPrs':
                    data = await this.apiClient.fetchUserPRs(startTime, endTime, params);
                    // Store user PRs data for sorting
                    this.currentData.userPrs = data;
                    this.updateUserPRsTable(data);
                    break;
            }
        } catch (error) {
            console.error(`[Dashboard] Error loading ${section} data:`, error);
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Update User PRs table with new data.
     * @param {Object} prsData - User PRs data with pagination
     */
    updateUserPRsTable(prsData) {
        const tableBody = document.getElementById('user-prs-table-body');
        if (!tableBody) return;

        const prs = prsData.data || [];
        const pagination = prsData.pagination;

        if (pagination) {
            this.pagination.userPrs = {
                page: pagination.page,
                pageSize: pagination.page_size,
                total: pagination.total,
                totalPages: pagination.total_pages
            };
        }

        if (!prs || prs.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="8" style="text-align: center;">No pull requests found</td></tr>';
        } else {
            const rows = prs.map(pr => {
                // Soft fallbacks for missing/invalid date fields
                const created = pr.created_at ? this.formatDateSafe(pr.created_at) : '-';
                const updated = pr.updated_at ? this.formatDateSafe(pr.updated_at) : '-';
                const stateClass = pr.state === 'open' ? 'status-success' : 'status-error';
                const mergedBadge = pr.merged ? '<span class="badge-merged">Merged</span>' : '';

                // Soft fallbacks for missing fields
                const prNumber = pr.number || 'N/A';
                const title = pr.title || 'Untitled';
                const owner = pr.owner || 'Unknown';
                const repository = pr.repository || 'Unknown';
                const state = pr.state || 'unknown';
                const commitsCount = pr.commits_count || 0;

                return `
                    <tr class="pr-row" data-pr-id="${prNumber}">
                        <td>
                            <a href="https://github.com/${this.escapeHtml(repository)}/pull/${prNumber}" target="_blank" rel="noopener noreferrer">#${prNumber}</a>
                            <button type="button" class="pr-story-btn" data-repo="${this.escapeHtml(repository)}" data-pr="${prNumber}" title="View PR Story">📊</button>
                        </td>
                        <td>${this.escapeHtml(title)}</td>
                        <td><span class="clickable-username" data-user="${this.escapeHtml(owner)}">${this.escapeHtml(owner)}</span></td>
                        <td>${this.escapeHtml(repository)}</td>
                        <td><span class="${stateClass}">${this.escapeHtml(state)}</span> ${mergedBadge}</td>
                        <td>${created}</td>
                        <td>${updated}</td>
                        <td>${commitsCount}</td>
                    </tr>
                `;
            }).join('');
            tableBody.innerHTML = rows;
        }

        // Add pagination controls
        const container = document.querySelector('[data-section="user-prs"] .chart-content');
        const existingControls = container?.querySelector('.pagination-controls');
        if (existingControls) {
            existingControls.remove();
        }

        if (container && pagination) {
            container.insertAdjacentHTML('beforeend', this.createPaginationControls('user-prs'));
        }
    }

    /**
     * Clean up resources on page unload.
     */
    destroy() {
        console.log('[Dashboard] Destroying dashboard...');

        // Destroy charts
        Object.values(this.charts).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });

        // Destroy combo-boxes
        if (this.repositoryComboBox) {
            this.repositoryComboBox.destroy();
            this.repositoryComboBox = null;
        }
        if (this.userComboBox) {
            this.userComboBox.destroy();
            this.userComboBox = null;
        }

        console.log('[Dashboard] Dashboard destroyed');
    }

    /**
     * Escape HTML to prevent XSS.
     *
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        return window.MetricsUtils?.escapeHTML(text) || String(text);
    }

    /**
     * Safely format a date string, handling invalid dates.
     *
     * @param {string} dateString - ISO date string
     * @returns {string} Formatted date or fallback
     */
    formatDateSafe(dateString) {
        try {
            const date = new Date(dateString);
            if (isNaN(date.getTime())) {
                return '-';
            }
            return date.toLocaleDateString();
        } catch {
            return '-';
        }
    }

    /**
     * Set up sort event listeners for table headers.
     */
    setupSortListeners() {
        document.addEventListener('click', (e) => {
            const header = e.target.closest('th.sortable');
            if (header) {
                const tableId = header.closest('table').id;
                const column = header.dataset.column;
                const section = this.getTableSection(tableId);

                if (section && column) {
                    this.handleTableSort(section, column);
                }
            }
        });
    }

    /**
     * Map table ID to section name.
     * @param {string} tableId - Table element ID
     * @returns {string|null} Section identifier
     */
    getTableSection(tableId) {
        const tableToSection = {
            'topRepositoriesTable': 'topRepositories',
            'recentEventsTable': 'recentEvents',
            'prCreatorsTable': 'prCreators',
            'prReviewersTable': 'prReviewers',
            'prApproversTable': 'prApprovers',
            'userPrsTable': 'userPrs'
        };
        return tableToSection[tableId] || null;
    }

    /**
     * Handle table header click for sorting.
     * @param {string} section - Section identifier
     * @param {string} column - Column name to sort by
     */
    handleTableSort(section, column) {
        const state = this.tableSortState[section];

        // Toggle direction if same column, otherwise reset to ascending
        if (state.column === column) {
            state.direction = state.direction === 'asc' ? 'desc' : 'asc';
        } else {
            state.column = column;
            state.direction = 'asc';
        }

        console.log(`[Dashboard] Sorting ${section} by ${column} ${state.direction}`);

        // Re-render the table with sorted data
        this.sortAndRenderTable(section);
    }

    /**
     * Sort table data and re-render.
     * @param {string} section - Section identifier
     */
    sortAndRenderTable(section) {
        const state = this.tableSortState[section];

        if (!state.column) {
            return; // No column selected
        }

        // Get the data for this section
        let data = this.getTableData(section);

        if (!data || !Array.isArray(data) || data.length === 0) {
            return;
        }

        // Sort the data
        const sortedData = this.sortTableData(data, state.column, state.direction);

        // Update the appropriate table
        switch (section) {
            case 'topRepositories':
                this.updateRepositoryTable(sortedData);
                this.updateSortIndicators('topRepositoriesTable', state.column, state.direction);
                break;
            case 'recentEvents':
                this.updateRecentEventsTable(sortedData);
                this.updateSortIndicators('recentEventsTable', state.column, state.direction);
                break;
            case 'prCreators':
                this.updateContributorsTable('pr-creators-table-body', sortedData, (creator) => `
                    <tr>
                        <td><span class="clickable-username" data-user="${this.escapeHtml(creator.user)}">${this.escapeHtml(creator.user)}</span></td>
                        <td>${creator.total_prs}</td>
                        <td>${creator.merged_prs}</td>
                        <td>${creator.closed_prs}</td>
                        <td>${creator.avg_commits_per_pr || 0}</td>
                    </tr>
                `);
                this.updateSortIndicators('prCreatorsTable', state.column, state.direction);
                break;
            case 'prReviewers':
                this.updateContributorsTable('pr-reviewers-table-body', sortedData, (reviewer) => `
                    <tr>
                        <td><span class="clickable-username" data-user="${this.escapeHtml(reviewer.user)}">${this.escapeHtml(reviewer.user)}</span></td>
                        <td>${reviewer.total_reviews}</td>
                        <td>${reviewer.prs_reviewed}</td>
                        <td>${reviewer.avg_reviews_per_pr}</td>
                    </tr>
                `);
                this.updateSortIndicators('prReviewersTable', state.column, state.direction);
                break;
            case 'prApprovers':
                this.updateContributorsTable('pr-approvers-table-body', sortedData, (approver) => `
                    <tr>
                        <td><span class="clickable-username" data-user="${this.escapeHtml(approver.user)}">${this.escapeHtml(approver.user)}</span></td>
                        <td>${approver.total_approvals}</td>
                        <td>${approver.prs_approved}</td>
                    </tr>
                `);
                this.updateSortIndicators('prApproversTable', state.column, state.direction);
                break;
            case 'userPrs':
                this.updateUserPRsTable({ data: sortedData, pagination: this.pagination.userPrs });
                this.updateSortIndicators('userPrsTable', state.column, state.direction);
                break;
        }
    }

    /**
     * Get table data for a section.
     * @param {string} section - Section identifier
     * @returns {Array} Table data
     */
    getTableData(section) {
        switch (section) {
            case 'topRepositories':
                return this.currentData.topRepositories || [];
            case 'recentEvents':
                return this.currentData.webhooks?.data || this.currentData.webhooks || [];
            case 'prCreators':
                return this.currentData.contributors?.pr_creators?.data || this.currentData.contributors?.pr_creators || [];
            case 'prReviewers':
                return this.currentData.contributors?.pr_reviewers?.data || this.currentData.contributors?.pr_reviewers || [];
            case 'prApprovers':
                return this.currentData.contributors?.pr_approvers?.data || this.currentData.contributors?.pr_approvers || [];
            case 'userPrs':
                return this.currentData.userPrs?.data || this.currentData.userPrs || [];
            default:
                return [];
        }
    }

    /**
     * Sort table data by column and direction.
     * @param {Array} data - Array of data objects
     * @param {string} column - Column name
     * @param {string} direction - 'asc' or 'desc'
     * @returns {Array} Sorted data
     */
    sortTableData(data, column, direction) {
        const sorted = [...data].sort((a, b) => {
            let aVal = a[column];
            let bVal = b[column];

            // Handle null/undefined - sort to end
            if (aVal == null && bVal == null) return 0;
            if (aVal == null) return 1;
            if (bVal == null) return -1;

            // Check for ISO date strings FIRST (before number check)
            // ISO dates look like: "2025-11-27T10:30:00" or "2025-11-27T10:30:00.000Z"
            const isoDateRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/;
            if (typeof aVal === 'string' && typeof bVal === 'string' &&
                isoDateRegex.test(aVal) && isoDateRegex.test(bVal)) {
                const aDate = new Date(aVal);
                const bDate = new Date(bVal);
                if (!isNaN(aDate.getTime()) && !isNaN(bDate.getTime())) {
                    return direction === 'asc' ? aDate - bDate : bDate - aDate;
                }
            }

            // Try to parse as number (only if both are purely numeric)
            const aNum = parseFloat(aVal);
            const bNum = parseFloat(bVal);
            const aIsNum = !isNaN(aNum) && isFinite(aVal) && String(aVal).trim() === String(aNum);
            const bIsNum = !isNaN(bNum) && isFinite(bVal) && String(bVal).trim() === String(bNum);

            if (aIsNum && bIsNum) {
                // Numeric comparison
                return direction === 'asc' ? aNum - bNum : bNum - aNum;
            }

            // String comparison (case-insensitive)
            const aStr = String(aVal).toLowerCase();
            const bStr = String(bVal).toLowerCase();

            if (direction === 'asc') {
                return aStr.localeCompare(bStr);
            }
            return bStr.localeCompare(aStr);
        });

        return sorted;
    }

    /**
     * Update sort indicators on table headers.
     * @param {string} tableId - Table element ID
     * @param {string} column - Currently sorted column
     * @param {string} direction - Sort direction ('asc' or 'desc')
     */
    updateSortIndicators(tableId, column, direction) {
        const table = document.getElementById(tableId);
        if (!table) return;

        // Remove existing sort classes
        table.querySelectorAll('th.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });

        // Add sort class to current column
        const currentHeader = table.querySelector(`th.sortable[data-column="${column}"]`);
        if (currentHeader) {
            currentHeader.classList.add(`sort-${direction}`);
        }
    }
}


// Initialize dashboard on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] DOM loaded, initializing dashboard...');

    // Create global dashboard instance
    window.metricsDashboard = new MetricsDashboard();

    // Clean up on page unload
    window.addEventListener('beforeunload', () => {
        if (window.metricsDashboard) {
            window.metricsDashboard.destroy();
        }
    });
});
