/* global CustomEvent */

/**
 * Metrics Dashboard - Main JavaScript Controller
 *
 * This module handles:
 * - Initial data loading via REST API
 * - KPI card updates
 * - Table updates with pagination and sorting
 * - Theme management (dark/light mode)
 * - Time range filtering
 * - Manual refresh
 */

import { initializeCollapsibleSections } from '../components/collapsible-section.js';
import { SortableTable } from '../components/sortable-table.js';
import { DownloadButtons } from '../components/download-buttons.js';
import { Pagination } from '../components/pagination.js';

// Dashboard Controller
class MetricsDashboard {
    // Large download threshold - warn user before downloading large datasets
    static LARGE_DOWNLOAD_THRESHOLD = 10000;

    // Section display names for downloads and error messages
    static SECTION_DISPLAY_NAMES = {
        'topRepositories': 'top_repositories',
        'recentEvents': 'recent_events',
        'userPrs': 'pull_requests'
        // Note: prCreators, prReviewers, prApprovers removed from Overview page
        // They're now only in Contributors page, managed by turnaround.js
    };

    constructor() {
        this.apiClient = null;  // Will be initialized in initialize()
        this.currentData = {
            summary: null,
            webhooks: null,
            repositories: null
        };
        // Read default from HTML select element (single source of truth)
        const timeRangeSelect = document.getElementById('time-range-select');
        this.timeRange = timeRangeSelect ? timeRangeSelect.value : '7d';
        this.repositoryFilter = '';  // Repository filter lowercase for local comparisons (empty = show all)
        this.repositoryFilterRaw = '';  // Repository filter original case for API calls
        this.userFilter = '';  // User filter (empty = show all)
        this.repositoryComboBox = null;  // ComboBox instance for repository filter
        this.userComboBox = null;  // ComboBox instance for user filter

        // Pagination components for each section
        this.paginationComponents = {
            topRepositories: null,
            recentEvents: null,
            userPrs: null
        };

        // SortableTable instances for each section
        this.sortableTables = {
            topRepositories: null,
            recentEvents: null,
            userPrs: null
        };

        // Note: Dashboard self-initializes asynchronously.
        // Callers should not assume immediate readiness after construction.
        this.initialize();
    }

    /**
     * Initialize dashboard - load theme, data, and tables.
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

        // 5b. Initialize collapsible sections (all sections with collapse buttons)
        this.collapsibleSections = initializeCollapsibleSections();

        // 5c. Initialize pagination components
        this.initializePaginationComponents();

        // 6. Populate date inputs with default 7d range logic so they are not empty
        const { startTime, endTime } = this.getTimeRangeDates(this.timeRange);
        const startInput = document.getElementById('startTime');
        const endInput = document.getElementById('endTime');
        if (startInput && endInput) {
            startInput.value = this.formatDateForInput(startTime);
            endInput.value = this.formatDateForInput(endTime);
            // Note: No change events dispatched here to avoid triggering handleCustomDateChange
            // during initialization. Events are only dispatched when user changes time range.
        }

        // 7. Show loading state
        this.showLoading(true);

        try {
            // 8. Load initial data via REST API
            await this.loadInitialData();

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
            this.updateTables(this.currentData);

            // Update User PRs table
            console.log('[Dashboard] Updating User PRs table with data:', userPrsData);
            this.updateUserPRsTable(userPrsData);

            // Populate filter dropdowns
            this.populateRepositoryFilter();
            this.populateUserFilter();

            // Dispatch event to notify other modules that dashboard is ready
            document.dispatchEvent(new CustomEvent('dashboard:ready'));
            console.log('[Dashboard] Dispatched dashboard:ready event');

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
                // Fallback to 7d if inputs invalid
                start.setDate(now.getDate() - 7);
                break;
            }
            default:
                // Default to 7d if unknown
                start.setDate(now.getDate() - 7);
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
     * Update all tables with new data.
     *
     * @param {Object} data - Complete dashboard data
     */
    updateTables(data) {
        if (!data) {
            console.warn('[Dashboard] No data available');
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
            userPrs: data.userPrs,
            eventTypeDistribution: data.eventTypeDistribution,
        };

        const summary = workingData.summary;
        let webhooks = workingData.webhooks;
        let repositories = workingData.repositories;

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

        // Apply user filter to User PRs (filter by owner field)
        let filteredUserPrs = workingData.userPrs;
        if (this.userFilter && filteredUserPrs) {
            const userPrsData = filteredUserPrs.data || filteredUserPrs;
            const filteredPRsData = Array.isArray(userPrsData)
                ? userPrsData.filter(pr => {
                    const owner = (pr.owner || '').toLowerCase();
                    return owner === this.userFilter.toLowerCase();
                })
                : [];

            filteredUserPrs = filteredUserPrs.data
                ? { ...filteredUserPrs, data: filteredPRsData }
                : filteredPRsData;

            console.log(`[Dashboard] Filtered User PRs by owner: ${filteredPRsData.length} PRs`);
        }

        // Store filtered view for sorting operations
        this.currentData.userPrsView = filteredUserPrs;

        // ALWAYS update KPI tooltip (whether filtered or not)
        this.updateKPITooltip(filteredSummary);

        // Use filtered data for table updates
        webhooks = filteredWebhooks;
        repositories = filteredRepositories;
        if (filteredContributors) {
            workingData.contributors = filteredContributors;
        }

        try {
            // Update Repository Table with top repositories from summary (has percentage field)
            if (data.topRepositories) {
                // Top repositories from summary endpoint (has percentage field)
                // Apply repository filter if active
                const topRepos = this.repositoryFilter
                    ? data.topRepositories.filter(repo =>
                        repo.repository && repo.repository.toLowerCase().includes(this.repositoryFilter))
                    : data.topRepositories;
                this.updateRepositoryTable(topRepos);

                // Update SortableTable instance with new data
                if (this.sortableTables.topRepositories) {
                    this.sortableTables.topRepositories.update(topRepos);
                }
            }

            // Update Recent Events Table with filtered data
            if (data.webhooks) {
                // Preserve pagination shape if original had it, otherwise pass filtered array
                const webhooksForTable = data.webhooks.data
                    ? { ...data.webhooks, data: filteredWebhooks }
                    : filteredWebhooks;
                this.updateRecentEventsTable(webhooksForTable);

                // Update SortableTable instance with new data
                if (this.sortableTables.recentEvents) {
                    this.sortableTables.recentEvents.update(filteredWebhooks);
                }
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

            // Update User PRs Table with filtered data
            if (filteredUserPrs) {
                this.updateUserPRsTable(filteredUserPrs);

                // Update SortableTable instance with new data
                const userPrsData = filteredUserPrs.data || filteredUserPrs;
                if (this.sortableTables.userPrs && Array.isArray(userPrsData)) {
                    this.sortableTables.userPrs.update(userPrsData);
                }
            }

            console.log('[Dashboard] Tables updated');
        } catch (error) {
            console.error('[Dashboard] Error updating tables:', error);
        }
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

        // Update pagination component if available
        // Note: topRepositories comes from summary.top_repositories which is NOT paginated
        // Only update pagination if we have pagination metadata (from fetchRepositories API)
        if (pagination && this.paginationComponents.topRepositories) {
            this.paginationComponents.topRepositories.update({
                total: pagination.total,
                page: pagination.page,
                pageSize: pagination.page_size
            });
        } else if (!pagination && repositories.length > 0 && this.paginationComponents.topRepositories) {
            // For non-paginated top repositories (from summary), show count without pagination controls
            this.paginationComponents.topRepositories.update({
                total: repositories.length,
                page: 1,
                pageSize: repositories.length
            });
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

        // Update pagination component if available
        if (pagination && this.paginationComponents.recentEvents) {
            this.paginationComponents.recentEvents.update({
                total: pagination.total,
                page: pagination.page,
                pageSize: pagination.page_size
            });
        }
    }

    /**
     * Update PR contributors tables with new data.
     * Note: This method is now a no-op as PR contributor tables were removed from Overview page.
     * PR contributor tables are only in Contributors page, managed by turnaround.js.
     */
    updateContributorsTables() {
        // No-op: PR contributor tables removed from Overview page
        // They're only in Contributors page now, managed by turnaround.js
        console.log('[Dashboard] updateContributorsTables called but PR contributor tables are in Contributors page');
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
        // Debounced time range change to prevent rapid consecutive API calls
        const debouncedTimeRangeChange = window.MetricsUtils?.debounce(
            (timeRange) => this.changeTimeRange(timeRange),
            300
        ) || ((timeRange) => this.changeTimeRange(timeRange));

        // Theme toggle button
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }

        // Time range selector
        const timeRangeSelect = document.getElementById('time-range-select');
        if (timeRangeSelect) {
            timeRangeSelect.addEventListener('change', (e) => debouncedTimeRangeChange(e.target.value));
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
                    debouncedTimeRangeChange('custom');
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
                // Check if this is from turnaround tables (has data-username)
                // If so, skip - let turnaround.js handler take care of it
                if (e.target.dataset.username) {
                    return;
                }

                // Handle main dashboard clickable usernames (use data-user)
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

        // Initialize SortableTable instances
        this.initializeSortableTables();

        // Download buttons (delegate to DownloadButtons component)
        this.setupDownloadButtons();

        console.log('[Dashboard] Event listeners set up');
    }

    /**
     * Set up download buttons using DownloadButtons component.
     */
    setupDownloadButtons() {
        // Initialize download buttons for each section
        this.downloadButtons = {};

        // Top Repositories
        const topReposContainer = document.querySelector('[data-section="top-repositories"] .table-controls');
        if (topReposContainer) {
            this.downloadButtons.topRepositories = new DownloadButtons({
                container: topReposContainer,
                section: 'top_repositories',
                getData: () => this.getTableData('topRepositories')
            });
        }

        // Recent Events
        const recentEventsContainer = document.querySelector('[data-section="recent-events"] .table-controls');
        if (recentEventsContainer) {
            this.downloadButtons.recentEvents = new DownloadButtons({
                container: recentEventsContainer,
                section: 'recent_events',
                getData: () => this.getTableData('recentEvents')
            });
        }

        // User PRs
        const userPrsContainer = document.querySelector('[data-section="user-prs"] .table-controls');
        if (userPrsContainer) {
            this.downloadButtons.userPrs = new DownloadButtons({
                container: userPrsContainer,
                section: 'pull_requests',
                getData: () => this.getTableData('userPrs')
            });
        }
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
     * Initialize pagination components for each table section.
     */
    initializePaginationComponents() {
        const sections = [
            { key: 'topRepositories', containerId: 'top-repositories-pagination' },
            { key: 'recentEvents', containerId: 'recent-events-pagination' },
            { key: 'userPrs', containerId: 'user-prs-pagination' }
        ];

        sections.forEach(({ key, containerId }) => {
            // Create pagination container if it doesn't exist
            let container = document.getElementById(containerId);
            if (!container) {
                // Find the chart-content div for this section
                const sectionDataAttr = this.camelToKebab(key);
                const chartContent = document.querySelector(`[data-section="${sectionDataAttr}"] .chart-content`);
                if (chartContent) {
                    container = document.createElement('div');
                    container.id = containerId;
                    chartContent.appendChild(container);
                }
            }

            if (container) {
                // Load saved page size from localStorage
                const savedPageSize = localStorage.getItem(`pageSize_${key}`);
                const pageSize = savedPageSize ? parseInt(savedPageSize, 10) : 10;

                this.paginationComponents[key] = new Pagination({
                    container: container,
                    pageSize: pageSize,
                    pageSizeOptions: [10, 25, 50, 100],
                    onPageChange: () => {
                        this.loadSectionData(key);
                    },
                    onPageSizeChange: (newPageSize) => {
                        localStorage.setItem(`pageSize_${key}`, newPageSize);
                        this.loadSectionData(key);
                    }
                });
                console.log(`[Dashboard] Pagination initialized for ${key}`);
            } else {
                console.warn(`[Dashboard] Pagination container not found for ${key}`);
            }
        });
    }

    /**
     * Convert camelCase to kebab-case
     * @param {string} str - camelCase string
     * @returns {string} kebab-case string
     */
    camelToKebab(str) {
        return str.replace(/([a-z])([A-Z])/g, '$1-$2').toLowerCase();
    }


    /**
     * Initialize theme from localStorage and apply it.
     */
    initializeTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateThemeIcon(savedTheme);
        console.log(`[Dashboard] Theme initialized: ${savedTheme}`);
    }

    /**
     * Update theme toggle button icon based on current theme.
     * @param {string} theme - Current theme ('light' or 'dark')
     */
    updateThemeIcon(theme) {
        const themeToggle = document.getElementById('theme-toggle');
        if (themeToggle) {
            // Show moon (🌙) in light mode (clicking will switch to dark)
            // Show sun (☀️) in dark mode (clicking will switch to light)
            themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
        }
    }

    /**
     * Toggle between dark and light theme.
     */
    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';

        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        this.updateThemeIcon(newTheme);

        console.log(`[Dashboard] Theme changed to: ${newTheme}`);
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

                // Dispatch custom event for turnaround.js to reload data
                // Don't use 'change' event to avoid triggering handleCustomDateChange
                document.dispatchEvent(new CustomEvent('timeFiltersUpdated'));
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

            // Also refresh Contributors page if it's currently active
            const contributorsPage = document.getElementById('page-contributors');
            if (contributorsPage && contributorsPage.classList.contains('active')) {
                console.log('[Dashboard] Refreshing Contributors page');
                if (window.turnaroundMetrics) {
                    await window.turnaroundMetrics.loadMetrics();
                }
            }

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

        // ALWAYS re-render tables (even when filter is cleared)
        if (this.currentData) {
            this.updateTables(this.currentData);
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

        // Clear filtered view when filter is cleared
        if (!this.userFilter && this.currentData) {
            this.currentData.userPrsView = null;
        }

        // Re-render tables
        if (this.currentData) {
            this.updateTables(this.currentData);
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
        // Update legacy status indicator (if present)
        const statusElement = document.getElementById('connection-status');
        const statusText = document.getElementById('statusText');

        if (statusElement && statusText) {
            if (ready) {
                statusElement.className = 'status connected';
                statusText.textContent = 'Ready';
            } else {
                statusElement.className = 'status disconnected';
                statusText.textContent = 'Initializing...';
            }
        }

        // Update new inline status indicator
        const statusInline = document.getElementById('connection-status-inline');
        const statusTextInline = document.getElementById('statusTextInline');

        if (statusInline && statusTextInline) {
            if (ready) {
                statusInline.className = 'status-inline connected';
                statusTextInline.textContent = 'Ready';
            } else {
                statusInline.className = 'status-inline disconnected';
                statusTextInline.textContent = 'Connecting...';
            }
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
     * Load data for a specific section with pagination
     * @param {string} section - Section identifier
     */
    async loadSectionData(section) {
        const paginationComponent = this.paginationComponents[section];
        if (!paginationComponent) {
            console.warn(`[Dashboard] No pagination component for section: ${section}`);
            return;
        }

        const state = paginationComponent.state;
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
                    this.currentData.topRepositories = data.data || data;  // Store for sorting/downloads
                    this.updateRepositoryTable(data);
                    // Update SortableTable instance with new data after pagination
                    if (this.sortableTables.topRepositories) {
                        const reposData = data.data || data;
                        this.sortableTables.topRepositories.update(reposData);
                    }
                    break;
                case 'recentEvents':
                    params.start_time = startTime;
                    params.end_time = endTime;
                    data = await this.apiClient.fetchWebhooks(params);
                    this.currentData.webhooks = data;  // Store for sorting/downloads
                    this.updateRecentEventsTable(data);
                    // Update SortableTable instance with new data after pagination
                    if (this.sortableTables.recentEvents) {
                        const eventsData = data.data || data;
                        this.sortableTables.recentEvents.update(eventsData);
                    }
                    break;
                case 'userPrs':
                    data = await this.apiClient.fetchUserPRs(startTime, endTime, params);
                    // Store user PRs data for sorting
                    this.currentData.userPrs = data;
                    // Clear filtered view - server already applied user filter via params.user
                    // This ensures getTableData uses fresh paginated data instead of stale view
                    this.currentData.userPrsView = null;
                    this.updateUserPRsTable(data);
                    // Update SortableTable instance with new data after pagination
                    if (this.sortableTables.userPrs) {
                        const prsData = data.data || data;
                        this.sortableTables.userPrs.update(prsData);
                    }
                    break;
                // Note: prCreators, prReviewers, prApprovers removed from Overview page
                // They're only in Contributors page now, managed by turnaround.js
            }
        } catch (error) {
            console.error(`[Dashboard] Error loading ${section} data:`, error);
        } finally {
            this.showLoading(false);
        }
    }

    /**
     * Update User PRs table with new data.
     * @param {Object|Array} prsData - User PRs data (can be array or {data: [...], pagination: {...}})
     */
    updateUserPRsTable(prsData) {
        const tableBody = document.getElementById('user-prs-table-body');
        if (!tableBody) return;

        // Handle both array format and paginated response format
        const prs = Array.isArray(prsData) ? prsData : (prsData.data || []);
        const pagination = Array.isArray(prsData) ? null : prsData.pagination;

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

        // Update pagination component if available
        if (pagination && this.paginationComponents.userPrs) {
            this.paginationComponents.userPrs.update({
                total: pagination.total,
                page: pagination.page,
                pageSize: pagination.page_size
            });
        }
    }

    /**
     * Clean up resources on page unload.
     */
    destroy() {
        console.log('[Dashboard] Destroying dashboard...');

        // Destroy combo-boxes
        if (this.repositoryComboBox) {
            this.repositoryComboBox.destroy();
            this.repositoryComboBox = null;
        }
        if (this.userComboBox) {
            this.userComboBox.destroy();
            this.userComboBox = null;
        }

        // Destroy collapsible sections
        if (this.collapsibleSections) {
            this.collapsibleSections.forEach(section => section.destroy());
            this.collapsibleSections = null;
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
        if (window.MetricsUtils?.escapeHTML) {
            return window.MetricsUtils.escapeHTML(text);
        }
        // Safe inline fallback using string replacement
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
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
     * Initialize SortableTable instances for each table section.
     */
    initializeSortableTables() {
        // Map table IDs to sections and column configurations
        const tableConfigs = {
            topRepositories: {
                tableId: 'topRepositoriesTable',
                columns: {
                    repository: { type: 'string' },
                    total_events: { type: 'number' },
                    percentage: { type: 'number' }
                }
            },
            recentEvents: {
                tableId: 'recentEventsTable',
                columns: {
                    created_at: { type: 'date' },
                    repository: { type: 'string' },
                    event_type: { type: 'string' },
                    status: { type: 'string' }
                }
            },
            userPrs: {
                tableId: 'userPrsTable',
                columns: {
                    number: { type: 'number' },
                    title: { type: 'string' },
                    owner: { type: 'string' },
                    repository: { type: 'string' },
                    state: { type: 'string' },
                    created_at: { type: 'date' },
                    updated_at: { type: 'date' },
                    commits_count: { type: 'number' }
                }
            }
        };

        Object.keys(tableConfigs).forEach(section => {
            const config = tableConfigs[section];
            const table = document.getElementById(config.tableId);

            if (!table) {
                console.warn(`[Dashboard] Table not found: ${config.tableId}`);
                return;
            }

            // Initialize SortableTable instance
            this.sortableTables[section] = new SortableTable({
                table: table,
                data: this.getTableData(section),
                columns: config.columns,
                onSort: (sortedData, column, direction) => {
                    console.log(`[Dashboard] Table ${section} sorted by ${column} ${direction}`);
                    this.handleTableSorted(section, sortedData);
                }
            });

            console.log(`[Dashboard] SortableTable initialized for ${section}`);
        });
    }

    /**
     * Handle table sorted callback - update the appropriate table with sorted data.
     * @param {string} section - Section identifier
     * @param {Array} sortedData - Sorted data array
     */
    handleTableSorted(section, sortedData) {
        // Update the appropriate table with sorted data
        switch (section) {
            case 'topRepositories':
                this.updateRepositoryTable(sortedData);
                break;
            case 'recentEvents':
                this.updateRecentEventsTable(sortedData);
                break;
            case 'userPrs': {
                const paginationState = this.paginationComponents.userPrs?.state || { page: 1, pageSize: 10, total: 0 };
                this.updateUserPRsTable({
                    data: sortedData,
                    pagination: {
                        page: paginationState.page,
                        page_size: paginationState.pageSize,
                        total: paginationState.total,
                        total_pages: Math.ceil(paginationState.total / paginationState.pageSize) || 1
                    }
                });
                break;
            }
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
            case 'userPrs':
                return this.currentData.userPrsView?.data || this.currentData.userPrsView ||
                       this.currentData.userPrs?.data || this.currentData.userPrs || [];
            default:
                // Note: prCreators, prReviewers, prApprovers removed from Overview page
                return [];
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
