/**
 * PR Story Modal - Pull Request Timeline Viewer
 *
 * Features:
 * - Modal popup with vertical timeline flowchart
 * - Fetches data from /api/metrics/pr-story/{repository}/{pr_number}
 * - Multi-select event type filter with checkboxes
 * - Collapsible event groups (e.g., check runs)
 * - Manual refresh button
 * - Loading, error, and empty states
 * - Dark/light theme support
 * - Click-outside-to-close and ESC key support
 * - Relative timestamps with hover for absolute time
 *
 * Usage:
 *   window.openPRStory('org/repo', 123);
 */

// Event type configuration with icons and colors
const PR_STORY_EVENT_CONFIG = {
    pr_opened: { icon: '🔀', color: '#3b82f6', label: 'PR Opened' },
    pr_closed: { icon: '❌', color: '#ef4444', label: 'PR Closed' },
    pr_merged: { icon: '🟣', color: '#8b5cf6', label: 'Merged' },
    pr_reopened: { icon: '🔄', color: '#3b82f6', label: 'Reopened' },
    commit: { icon: '📝', color: '#6b7280', label: 'Commit' },
    review_approved: { icon: '✅', color: '#22c55e', label: 'Approved' },
    review_changes: { icon: '🔄', color: '#ef4444', label: 'Changes Requested' },
    review_comment: { icon: '💬', color: '#3b82f6', label: 'Review Comment' },
    comment: { icon: '💬', color: '#6b7280', label: 'Comment' },
    review_requested: { icon: '👁️', color: '#f59e0b', label: 'Review Requested' },
    ready_for_review: { icon: '👁️', color: '#3b82f6', label: 'Ready for Review' },
    label_added: { icon: '🏷️', color: '#f59e0b', label: 'Label Added' },
    label_removed: { icon: '🏷️', color: '#6b7280', label: 'Label Removed' },
    verified: { icon: '🛡️', color: '#22c55e', label: 'Verified' },
    approved_label: { icon: '✅', color: '#22c55e', label: 'Approved' },
    lgtm: { icon: '👍', color: '#22c55e', label: 'LGTM' },
    check_run: { icon: '▶️', color: '#3b82f6', label: 'Check Run' },
};

class PRStoryModal {
    /**
     * Create a new PR Story modal instance.
     */
    constructor() {
        this.currentRepository = null;
        this.currentPRNumber = null;
        this.storyData = null;
        this.expandedGroups = new Set(); // Track which event groups are expanded
        this.selectedEventTypes = new Set(); // Track selected event types for filtering
        this._initializedFilters = false; // Track if filters have been initialized

        // Draggable state
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.modalStartX = 0;
        this.modalStartY = 0;
    }

    /**
     * Initialize the modal and inject into DOM.
     */
    initialize() {
        // Create modal HTML and inject into body
        this.createModalHTML();

        // Set up event listeners
        this.setupEventListeners();

        // Set up draggable functionality
        this.setupDraggable();

        console.log('[PRStory] PR Story modal initialized');
    }

    /**
     * Create and inject modal HTML into DOM.
     */
    createModalHTML() {
        const modalHTML = `
            <div id="prStoryModal" class="modal" role="dialog" aria-labelledby="prStoryModalTitle" aria-modal="true">
                <div class="modal-content pr-story-modal">
                    <div class="modal-header pr-story-header" id="prStoryHeader">
                        <!-- PR title will be inserted here dynamically -->
                        <span id="prStoryModalTitle">PR Story</span>
                        <button class="close-modal" aria-label="Close PR Story">&times;</button>
                    </div>
                    <div class="modal-body">
                        <div class="pr-story-toolbar" id="prStorySummary">
                            <!-- Summary stats and filter will be inserted here -->
                        </div>
                        <div class="pr-story-timeline" id="prStoryTimeline">
                            <!-- Timeline events will be inserted here -->
                        </div>
                        <div class="pr-story-loading" id="prStoryLoading" style="display: none;">
                            <div class="spinner" aria-hidden="true"></div>
                            <p>Loading PR story...</p>
                        </div>
                        <div class="pr-story-error" id="prStoryError" style="display: none;">
                            <p></p>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Inject modal into body
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Add modal-specific styles
        this.injectStyles();
    }

    /**
     * Inject CSS styles for PR Story modal.
     */
    injectStyles() {
        const styleId = 'pr-story-modal-styles';
        if (document.getElementById(styleId)) {
            return; // Styles already injected
        }

        const styles = `
            <style id="${styleId}">
                /* Draggable header */
                .pr-story-modal .modal-header {
                    cursor: move;
                    cursor: grab;
                    user-select: none;
                }

                .pr-story-modal .modal-header:active {
                    cursor: grabbing;
                }

                /* Timeline styling */
                .pr-story-timeline {
                    position: relative;
                    padding-left: 30px;
                    flex: 1 1 auto;
                    min-height: 0;
                    overflow-y: auto;
                }

                .modal-footer {
                    display: flex;
                    justify-content: flex-end;
                    gap: 10px;
                    padding: 15px 20px;
                    border-top: 1px solid var(--border-color);
                }

                .pr-story-header {
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 10px;
                    flex-shrink: 0;
                }

                .pr-story-header-content {
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    flex: 1;
                    min-width: 0;
                }

                .pr-story-title {
                    font-size: 0.95rem;
                    font-weight: 600;
                    color: var(--text-color);
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }

                .pr-story-meta {
                    font-size: 0.75rem;
                    color: var(--text-secondary);
                    display: flex;
                    align-items: center;
                    gap: 0;
                }

                .pr-story-badge {
                    display: inline-block;
                    padding: 1px 5px;
                    border-radius: 3px;
                    font-size: 0.65rem;
                    font-weight: 600;
                }

                .pr-story-badge.merged {
                    background-color: var(--success-color);
                    color: white;
                }

                .pr-story-badge.closed {
                    background-color: var(--error-color);
                    color: white;
                }

                .pr-story-badge.open {
                    background-color: var(--success-color);
                    color: white;
                }

                .pr-story-toolbar {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    align-items: center;
                    justify-content: flex-start;
                    gap: 14px;
                    margin-bottom: 8px;
                    padding-bottom: 8px;
                    border-bottom: 1px solid var(--border-color);
                    font-size: 0.85rem;
                    flex: 0 0 auto;
                    color: var(--text-secondary);
                }

                .pr-story-summary {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex-wrap: nowrap;
                }

                .pr-story-summary-item {
                    display: flex;
                    align-items: center;
                    gap: 2px;
                    color: var(--text-color);
                    white-space: nowrap;
                }

                .pr-story-filter {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                }

                .pr-story-filter-label {
                    color: var(--text-secondary);
                }

                .pr-story-filter-dropdown {
                    position: relative;
                }

                .pr-story-filter-toggle {
                    padding: 3px 8px;
                    font-size: 0.85rem;
                    background-color: var(--container-bg);
                    color: var(--text-color);
                    border: 1px solid var(--border-color);
                    border-radius: 3px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 3px;
                    white-space: nowrap;
                }

                .pr-story-filter-toggle:hover {
                    border-color: var(--primary-color);
                }

                .pr-story-filter-toggle-arrow {
                    font-size: 0.6rem;
                    margin-left: 8px;
                }

                .pr-story-filter-menu {
                    position: absolute;
                    top: 100%;
                    right: 0;
                    min-width: 180px;
                    margin-top: 4px;
                    background-color: var(--container-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 4px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 1000;
                    display: none;
                    max-height: 250px;
                    overflow-y: auto;
                }

                .pr-story-filter-menu.open {
                    display: block;
                }

                .pr-story-filter-menu-actions {
                    display: flex;
                    gap: 4px;
                    padding: 6px;
                    border-bottom: 1px solid var(--border-color);
                }

                .pr-story-filter-btn {
                    flex: 1;
                    padding: 4px 8px;
                    font-size: 0.7rem;
                    background-color: var(--button-bg);
                    color: var(--button-text);
                    border: 1px solid var(--border-color);
                    border-radius: 3px;
                    cursor: pointer;
                }

                .pr-story-filter-btn:hover {
                    background-color: var(--button-hover-bg);
                }

                .pr-story-filter-option {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    padding: 6px 10px;
                    cursor: pointer;
                    font-size: 0.8rem;
                    transition: background-color 0.15s;
                    user-select: none;
                }

                .pr-story-filter-option:hover {
                    background-color: var(--input-bg);
                }

                .pr-story-filter-option input[type="checkbox"] {
                    margin: 0;
                    cursor: pointer;
                }

                .pr-story-filter-option-icon {
                    font-size: 0.9rem;
                }

                .pr-story-filter-option-label {
                    color: var(--text-color);
                }

                .pr-story-timeline::before {
                    content: '';
                    position: absolute;
                    left: 10px;
                    top: 0;
                    bottom: 0;
                    width: 2px;
                    background-color: var(--border-color);
                }

                /* Ensure modal body expands to fill available space */
                #prStoryModal .modal-body {
                    flex: 1 1 auto;
                    min-height: 0;
                    display: flex;
                    flex-direction: column;
                    overflow: hidden;
                }

                .timeline-event {
                    position: relative;
                    margin-bottom: 20px;
                    padding-bottom: 10px;
                }

                .timeline-event-marker {
                    position: absolute;
                    left: -24px;
                    top: 2px;
                    width: 10px;
                    height: 10px;
                    border-radius: 50%;
                    background-color: var(--text-secondary);
                    z-index: 1;
                }

                .timeline-event-content {
                    margin-left: 10px;
                }

                .timeline-event-header {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 4px;
                }

                .timeline-event-icon {
                    font-size: 1rem;
                }

                .timeline-event-title {
                    font-weight: 600;
                    color: var(--text-color);
                    font-size: 0.875rem;
                }

                .timeline-event-time {
                    font-size: 0.75rem;
                    color: var(--text-secondary);
                    margin-left: auto;
                }

                .timeline-event-description {
                    font-size: 0.875rem;
                    color: var(--text-secondary);
                    margin-top: 4px;
                }

                .timeline-event-comment-body {
                    font-size: 0.85rem;
                    color: var(--text-primary);
                    background-color: var(--input-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 4px;
                    padding: 8px 10px;
                    margin-top: 6px;
                    white-space: pre-wrap;
                    word-break: break-word;
                }

                .timeline-event-comment-body .comment-link {
                    text-decoration: none;
                    margin-left: 4px;
                }

                .timeline-event-comment-body .comment-link:hover {
                    opacity: 0.8;
                }

                .timeline-event-group {
                    background-color: var(--input-bg);
                    border: 1px solid var(--border-color);
                    border-radius: 4px;
                    padding: 10px;
                    cursor: pointer;
                    transition: background-color 0.2s ease;
                }

                .timeline-event-group:hover {
                    background-color: var(--border-color);
                }

                .timeline-event-group-header {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }

                .timeline-event-group-expand {
                    font-size: 0.75rem;
                    color: var(--text-secondary);
                    user-select: none;
                }

                .timeline-event-group-children {
                    margin-top: 10px;
                    padding-left: 10px;
                    border-left: 2px solid var(--border-color);
                    display: none;
                }

                .timeline-event-group.expanded .timeline-event-group-children {
                    display: block;
                }

                .timeline-event-group.expanded .timeline-event-group-expand::before {
                    content: '▼';
                }

                .timeline-event-group:not(.expanded) .timeline-event-group-expand::before {
                    content: '▶';
                }

                .timeline-event-child {
                    margin-bottom: 8px;
                    padding: 6px;
                    border-radius: 3px;
                    background-color: var(--container-bg);
                }

                .check-run-conclusion {
                    display: inline-block;
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-size: 0.75rem;
                    font-weight: 600;
                    margin-left: 5px;
                }

                .check-run-conclusion.success {
                    background-color: var(--success-color);
                    color: white;
                }

                .check-run-conclusion.failure {
                    background-color: var(--error-color);
                    color: white;
                }

                .check-run-conclusion.neutral {
                    background-color: var(--text-secondary);
                    color: white;
                }

                .pr-story-loading,
                .pr-story-error {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    padding: 40px 20px;
                    text-align: center;
                }

                .pr-story-loading .spinner {
                    border: 4px solid var(--border-color);
                    border-top: 4px solid var(--primary-color);
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    animation: spin 1s linear infinite;
                    margin-bottom: 15px;
                }

                .pr-story-error {
                    color: var(--error-color);
                }

                .pr-story-empty {
                    text-align: center;
                    padding: 40px 20px;
                    color: var(--text-secondary);
                    font-size: 0.875rem;
                }
            </style>
        `;

        document.head.insertAdjacentHTML('beforeend', styles);
    }

    /**
     * Set up event listeners for modal interactions.
     */
    setupEventListeners() {
        const modal = document.getElementById('prStoryModal');
        if (!modal) return;

        // Use event delegation for close button (handles re-rendered headers)
        modal.addEventListener('click', (e) => {
            if (e.target.closest('.close-modal')) {
                this.close();
            }
        });

        // Click outside modal to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.close();
            }
        });

        // ESC key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && modal.classList.contains('show')) {
                this.close();
            }
        });

        // Event delegation for expand/collapse groups
        const timeline = document.getElementById('prStoryTimeline');
        if (timeline) {
            timeline.addEventListener('click', (e) => {
                const group = e.target.closest('.timeline-event-group');
                if (group) {
                    this.toggleGroup(group);
                }
            });
        }

        // Event delegation for filter controls (on summary container since filter is dynamic)
        const summaryContainer = document.getElementById('prStorySummary');
        if (summaryContainer) {
            summaryContainer.addEventListener('click', (e) => {
                const filterContainer = document.getElementById('prStoryFilter');
                if (!filterContainer) return;

                // Handle dropdown toggle
                const toggleBtn = e.target.closest('.pr-story-filter-toggle');
                if (toggleBtn) {
                    const menu = document.getElementById('prStoryFilterMenu');
                    if (menu) {
                        menu.classList.toggle('open');
                    }
                    return;
                }

                // Handle "Show All" button
                if (e.target.classList.contains('pr-story-filter-show-all')) {
                    // Check all checkboxes
                    filterContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                        cb.checked = true;
                        this.selectedEventTypes.add(cb.dataset.eventType);
                    });
                    this.applyFilter();
                    return;
                }

                // Handle "None" button
                if (e.target.classList.contains('pr-story-filter-clear')) {
                    // Uncheck all checkboxes
                    filterContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
                        cb.checked = false;
                    });
                    this.selectedEventTypes.clear();
                    this.applyFilter();
                    return;
                }

                // Handle checkbox change
                const checkbox = e.target.closest('input[type="checkbox"]');
                if (checkbox) {
                    const eventType = checkbox.dataset.eventType;
                    if (checkbox.checked) {
                        this.selectedEventTypes.add(eventType);
                    } else {
                        this.selectedEventTypes.delete(eventType);
                    }
                    this.applyFilter();
                }
            });
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            const menu = document.getElementById('prStoryFilterMenu');
            const toggle = document.getElementById('prStoryFilterToggle');
            if (menu && menu.classList.contains('open')) {
                if (!menu.contains(e.target) && e.target !== toggle && !toggle?.contains(e.target)) {
                    menu.classList.remove('open');
                }
            }
        });

        console.log('[PRStory] Event listeners set up');
    }

    /**
     * Set up draggable functionality for the modal.
     */
    setupDraggable() {
        const modal = document.getElementById('prStoryModal');
        if (!modal) return;

        const modalContent = modal.querySelector('.modal-content.pr-story-modal');
        const header = modal.querySelector('.modal-header');

        if (!modalContent || !header) return;

        // Bind event handlers to preserve 'this' context
        this.handleDragStart = this.handleDragStart.bind(this);
        this.handleDragMove = this.handleDragMove.bind(this);
        this.handleDragEnd = this.handleDragEnd.bind(this);

        // Mouse down on header to start drag
        header.addEventListener('mousedown', (e) => {
            // Don't start drag if clicking the close button
            if (e.target.closest('.close-modal')) {
                return;
            }
            this.handleDragStart(e, modalContent);
        });

        console.log('[PRStory] Draggable functionality set up');
    }

    /**
     * Handle drag start event.
     *
     * @param {MouseEvent} e - Mouse event
     * @param {HTMLElement} modalContent - Modal content element
     */
    handleDragStart(e, modalContent) {
        this.isDragging = true;

        // Get current position of modal
        const rect = modalContent.getBoundingClientRect();
        this.modalStartX = rect.left;
        this.modalStartY = rect.top;

        // Store initial mouse position
        this.dragStartX = e.clientX;
        this.dragStartY = e.clientY;

        // Remove transform to allow manual positioning
        modalContent.style.transform = 'none';

        // Set initial position
        modalContent.style.left = `${this.modalStartX}px`;
        modalContent.style.top = `${this.modalStartY}px`;

        // Add event listeners for drag
        document.addEventListener('mousemove', this.handleDragMove);
        document.addEventListener('mouseup', this.handleDragEnd);

        // Prevent text selection during drag
        e.preventDefault();
    }

    /**
     * Handle drag move event.
     *
     * @param {MouseEvent} e - Mouse event
     */
    handleDragMove(e) {
        if (!this.isDragging) return;

        const modal = document.getElementById('prStoryModal');
        if (!modal) return;

        const modalContent = modal.querySelector('.modal-content.pr-story-modal');
        if (!modalContent) return;

        // Calculate new position
        const deltaX = e.clientX - this.dragStartX;
        const deltaY = e.clientY - this.dragStartY;

        let newX = this.modalStartX + deltaX;
        let newY = this.modalStartY + deltaY;

        // Get modal dimensions
        const rect = modalContent.getBoundingClientRect();
        const modalWidth = rect.width;

        // Get viewport dimensions
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        // Constrain to viewport bounds (keep at least 50px of header visible)
        const minVisiblePixels = 50;
        newX = Math.max(-modalWidth + minVisiblePixels, Math.min(newX, viewportWidth - minVisiblePixels));
        newY = Math.max(0, Math.min(newY, viewportHeight - minVisiblePixels));

        // Apply new position
        modalContent.style.left = `${newX}px`;
        modalContent.style.top = `${newY}px`;
    }

    /**
     * Handle drag end event.
     */
    handleDragEnd() {
        if (!this.isDragging) return;

        this.isDragging = false;

        // Remove event listeners
        document.removeEventListener('mousemove', this.handleDragMove);
        document.removeEventListener('mouseup', this.handleDragEnd);
    }

    /**
     * Open the PR Story modal for a specific PR.
     *
     * @param {string} repository - Repository name (org/repo)
     * @param {number} prNumber - Pull request number
     */
    async open(repository, prNumber) {
        console.log(`[PRStory] Opening PR story for ${repository}#${prNumber}`);

        this.currentRepository = repository;
        this.currentPRNumber = prNumber;
        this.expandedGroups.clear();
        this.selectedEventTypes.clear(); // Reset filter
        this._initializedFilters = false; // Reset for new PR

        // Show modal
        const modal = document.getElementById('prStoryModal');
        if (!modal) {
            console.error('[PRStory] Modal element not found');
            return;
        }

        modal.classList.add('show');
        document.body.style.overflow = 'hidden';

        // Load data
        await this.loadData();
    }

    /**
     * Close the PR Story modal.
     */
    close() {
        // Cleanup drag listeners if still attached (prevents memory leak)
        document.removeEventListener('mousemove', this.handleDragMove);
        document.removeEventListener('mouseup', this.handleDragEnd);
        this.isDragging = false;

        const modal = document.getElementById('prStoryModal');
        if (modal) {
            modal.classList.remove('show');

            // Reset modal position to center
            const modalContent = modal.querySelector('.modal-content.pr-story-modal');
            if (modalContent) {
                modalContent.style.transform = 'translate(-50%, -50%)';
                modalContent.style.left = '50%';
                modalContent.style.top = '50%';
            }
        }
        document.body.style.overflow = '';

        console.log('[PRStory] Modal closed');
    }

    /**
     * Refresh the PR Story data.
     */
    async refresh() {
        console.log('[PRStory] Refreshing PR story');
        await this.loadData();
    }

    /**
     * Load PR story data from API.
     */
    async loadData() {
        if (!this.currentRepository || !this.currentPRNumber) {
            console.error('[PRStory] No repository or PR number set');
            return;
        }

        this.showLoading(true);
        this.hideError();

        try {
            // Fetch PR story from API
            const url = `/api/metrics/pr-story/${encodeURIComponent(this.currentRepository)}/${this.currentPRNumber}`;
            console.log(`[PRStory] Fetching: ${url}`);

            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('[PRStory] Data loaded:', data);

            this.storyData = data;
            this.showLoading(false);
            this.render();

        } catch (error) {
            console.error('[PRStory] Error loading data:', error);
            this.showLoading(false);
            this.showError(error.message || 'Failed to load PR story');
        }
    }

    /**
     * Render PR story in modal.
     */
    render() {
        if (!this.storyData) {
            this.showEmpty();
            return;
        }

        const { pr, events, summary } = this.storyData;

        // Render header
        this.renderHeader(pr);

        // Render summary
        this.renderSummary(summary);

        // Render filter
        this.renderFilter(events);

        // Render timeline
        this.renderTimeline(events);
    }

    /**
     * Render PR header section.
     *
     * @param {Object} pr - PR metadata
     */
    renderHeader(pr) {
        const header = document.getElementById('prStoryHeader');
        if (!header) return;

        const stateClass = pr.merged ? 'merged' : pr.state;
        const stateLabel = pr.merged ? 'merged' : pr.state;

        // Two-line header:
        // Line 1: #number: title
        // Line 2: @author · date · status (repo)
        header.innerHTML = `
            <div class="pr-story-header-content">
                <div class="pr-story-title">#${pr.number}: ${this.escapeHtml(pr.title)}</div>
                <div class="pr-story-meta">
                    @${this.escapeHtml(pr.author)} · ${this.formatDate(pr.created_at)} ·
                    <span class="pr-story-badge ${stateClass}">${stateLabel}</span>
                    · ${this.escapeHtml(pr.repository)}
                </div>
            </div>
            <button class="close-modal" aria-label="Close PR Story">&times;</button>
        `;
    }

    /**
     * Render summary statistics (includes filter).
     *
     * @param {Object} summary - Summary statistics
     */
    renderSummary(summary) {
        const summaryEl = document.getElementById('prStorySummary');
        if (!summaryEl) return;

        const { total_commits, total_reviews, total_check_runs, total_comments } = summary;

        summaryEl.innerHTML = `
            <div class="pr-story-summary-item">
                <span>📝</span>
                <strong>${total_commits}</strong> commit${total_commits !== 1 ? 's' : ''}
            </div>
            <div class="pr-story-summary-item">
                <span>💬</span>
                <strong>${total_reviews}</strong> review${total_reviews !== 1 ? 's' : ''}
            </div>
            <div class="pr-story-summary-item">
                <span>▶️</span>
                <strong>${total_check_runs}</strong> check run${total_check_runs !== 1 ? 's' : ''}
            </div>
            <div class="pr-story-summary-item">
                <span>💭</span>
                <strong>${total_comments}</strong> comment${total_comments !== 1 ? 's' : ''}
            </div>
            <div class="pr-story-filter" id="prStoryFilter">
                <!-- Filter dropdown will be inserted by renderFilter -->
            </div>
        `;
    }

    /**
     * Render event type filter.
     *
     * @param {Array} events - Timeline events
     */
    renderFilter(events) {
        const filterEl = document.getElementById('prStoryFilter');
        if (!filterEl) return;

        // Initialize selectedEventTypes with all event types on first render
        if (!this._initializedFilters && events.length > 0) {
            events.forEach(event => {
                this.selectedEventTypes.add(event.event_type);
            });
            this._initializedFilters = true;
        }

        // Extract unique event types from events
        const eventTypes = new Set();
        events.forEach(event => {
            eventTypes.add(event.event_type);
        });

        // Sort event types alphabetically
        const sortedEventTypes = Array.from(eventTypes).sort();

        // Generate filter options HTML
        const filterOptionsHTML = sortedEventTypes.map(eventType => {
            const config = PR_STORY_EVENT_CONFIG[eventType] || { icon: '●', label: eventType };
            const isChecked = this.selectedEventTypes.has(eventType);

            return `
                <label class="pr-story-filter-option">
                    <input type="checkbox"
                           data-event-type="${eventType}"
                           ${isChecked ? 'checked' : ''}>
                    <span class="pr-story-filter-option-icon">${config.icon}</span>
                    <span class="pr-story-filter-option-label">${config.label}</span>
                </label>
            `;
        }).join('');

        // Get toggle button text
        const selectedCount = this.selectedEventTypes.size;
        const totalCount = sortedEventTypes.length;
        const toggleText = selectedCount === 0 || selectedCount === totalCount
            ? 'All Events'
            : `${selectedCount}/${totalCount}`;

        filterEl.innerHTML = `
            <div class="pr-story-filter-dropdown">
                <button class="pr-story-filter-toggle" id="prStoryFilterToggle">
                    <span>🔍</span>
                    <span class="pr-story-filter-label">${toggleText}</span>
                    <span class="pr-story-filter-toggle-arrow">▼</span>
                </button>
                <div class="pr-story-filter-menu" id="prStoryFilterMenu">
                    <div class="pr-story-filter-menu-actions">
                        <button class="pr-story-filter-btn pr-story-filter-show-all">All</button>
                        <button class="pr-story-filter-btn pr-story-filter-clear">None</button>
                    </div>
                    ${filterOptionsHTML}
                </div>
            </div>
        `;
    }

    /**
     * Render timeline events.
     *
     * @param {Array} events - Timeline events
     */
    renderTimeline(events) {
        const timeline = document.getElementById('prStoryTimeline');
        if (!timeline) return;

        if (!events || events.length === 0) {
            timeline.innerHTML = '<div class="pr-story-empty">No events found for this PR</div>';
            return;
        }

        // Filter events based on selected event types
        const filteredEvents = this.filterEventsByType(events);

        if (filteredEvents.length === 0) {
            timeline.innerHTML = '<div class="pr-story-empty">No events match the current filter</div>';
            return;
        }

        const timelineHTML = filteredEvents.map((event, index) => {
            return this.renderEvent(event, index);
        }).join('');

        timeline.innerHTML = timelineHTML;
    }

    /**
     * Filter events by selected event types.
     *
     * @param {Array} events - All timeline events
     * @returns {Array} Filtered events
     */
    filterEventsByType(events) {
        // Filter events by selected types (empty set = show nothing)
        return events.filter(event => this.selectedEventTypes.has(event.event_type));
    }

    /**
     * Apply filter to timeline (re-render with current filter).
     */
    applyFilter() {
        if (!this.storyData || !this.storyData.events) return;

        // Update toggle button text
        const toggleBtn = document.querySelector('.pr-story-filter-toggle .pr-story-filter-label');
        if (toggleBtn) {
            const totalCount = document.querySelectorAll('#prStoryFilter input[type="checkbox"]').length;
            const selectedCount = this.selectedEventTypes.size;
            toggleBtn.textContent = selectedCount === 0 || selectedCount === totalCount
                ? 'All Events'
                : `${selectedCount}/${totalCount}`;
        }

        // Re-render timeline with filter
        this.renderTimeline(this.storyData.events);

        console.log(`[PRStory] Filter applied: ${Array.from(this.selectedEventTypes).join(', ')}`);
    }

    /**
     * Clear filter and show all events.
     */
    clearFilter() {
        // Get all event types from the current story data
        if (this.storyData && this.storyData.events) {
            this.storyData.events.forEach(event => {
                this.selectedEventTypes.add(event.event_type);
            });
        }

        // Update checkboxes
        const checkboxes = document.querySelectorAll('#prStoryFilter input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.checked = true;
        });

        // Re-render timeline
        this.applyFilter();

        console.log('[PRStory] Filter cleared');
    }

    /**
     * Render a single timeline event.
     *
     * @param {Object} event - Event data
     * @param {number} index - Event index
     * @returns {string} Event HTML
     */
    renderEvent(event, index) {
        const config = PR_STORY_EVENT_CONFIG[event.event_type] || { icon: '●', color: '#6b7280', label: event.event_type };

        // Check if this is a grouped event (e.g., check runs)
        if (event.children && event.children.length > 0) {
            return this.renderGroupedEvent(event, index, config);
        }

        // Single event
        let descriptionHtml = '';
        if (event.event_type === 'comment' && event.body) {
            // Comment with body and optional link
            const bodyText = this.escapeHtml(event.body);
            const truncatedIndicator = event.truncated ? '...' : '';
            const linkHtml = event.url ? ` <a href="${this.escapeHtml(event.url)}" target="_blank" rel="noopener noreferrer" class="comment-link" title="View on GitHub">🔗</a>` : '';
            descriptionHtml = `<div class="timeline-event-description">${this.escapeHtml(event.description)}</div>
                <div class="timeline-event-comment-body">${bodyText}${truncatedIndicator}${linkHtml}</div>`;
        } else if (event.description) {
            descriptionHtml = `<div class="timeline-event-description">${this.escapeHtml(event.description)}</div>`;
        }

        const absoluteTime = this.formatAbsoluteTime(event.timestamp);
        const relativeTime = this.formatRelativeTime(event.timestamp);

        return `
            <div class="timeline-event" data-event-index="${index}">
                <div class="timeline-event-marker"></div>
                <div class="timeline-event-content">
                    <div class="timeline-event-header">
                        <span class="timeline-event-icon">${config.icon}</span>
                        <span class="timeline-event-title">${config.label}</span>
                        <span class="timeline-event-time">
                            ${relativeTime} (${absoluteTime})
                        </span>
                    </div>
                    ${descriptionHtml}
                </div>
            </div>
        `;
    }

    /**
     * Render a grouped event (e.g., multiple check runs).
     *
     * @param {Object} event - Event data with children
     * @param {number} index - Event index
     * @param {Object} config - Event configuration
     * @returns {string} Event HTML
     */
    renderGroupedEvent(event, index, config) {
        const childCount = event.children.length;
        const successCount = event.children.filter(c => c.conclusion === 'success').length;
        const failureCount = event.children.filter(c => c.conclusion === 'failure').length;
        const pendingCount = event.children.filter(c => !c.conclusion).length;

        const groupId = `event-group-${index}`;
        const isExpanded = this.expandedGroups.has(groupId);
        const commitInfo = event.commit ? ` @ ${event.commit}` : '';
        const absoluteTime = this.formatAbsoluteTime(event.timestamp);
        const relativeTime = this.formatRelativeTime(event.timestamp);
        const pendingInfo = pendingCount > 0 ? `, ${pendingCount} ⏳` : '';

        return `
            <div class="timeline-event" data-event-index="${index}">
                <div class="timeline-event-marker"></div>
                <div class="timeline-event-content">
                    <div class="timeline-event-group ${isExpanded ? 'expanded' : ''}" data-group-id="${groupId}">
                        <div class="timeline-event-group-header">
                            <span class="timeline-event-group-expand"></span>
                            <span class="timeline-event-icon">${config.icon}</span>
                            <span class="timeline-event-title">
                                ${childCount} ${config.label}${childCount !== 1 ? 's' : ''}
                                (${successCount} ✓, ${failureCount} ✗${pendingInfo})${commitInfo}
                            </span>
                            <span class="timeline-event-time">
                                ${relativeTime} (${absoluteTime})
                            </span>
                        </div>
                        <div class="timeline-event-group-children">
                            ${event.children.map(child => this.renderChildEvent(child)).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Render a child event within a group.
     *
     * @param {Object} child - Child event data
     * @returns {string} Child event HTML
     */
    renderChildEvent(child) {
        const conclusionClass = child.conclusion === 'success' ? 'success' : child.conclusion === 'failure' ? 'failure' : 'neutral';
        const conclusionLabel = child.conclusion || 'pending';

        return `
            <div class="timeline-event-child">
                <strong>${this.escapeHtml(child.name)}</strong>
                <span class="check-run-conclusion ${conclusionClass}">${conclusionLabel}</span>
                ${child.description ? `<div class="timeline-event-description">${this.escapeHtml(child.description)}</div>` : ''}
            </div>
        `;
    }

    /**
     * Toggle expand/collapse of event group.
     *
     * @param {HTMLElement} groupElement - Group element
     */
    toggleGroup(groupElement) {
        const groupId = groupElement.dataset.groupId;

        if (this.expandedGroups.has(groupId)) {
            this.expandedGroups.delete(groupId);
            groupElement.classList.remove('expanded');
        } else {
            this.expandedGroups.add(groupId);
            groupElement.classList.add('expanded');
        }
    }

    /**
     * Show loading spinner.
     *
     * @param {boolean} show - Whether to show loading spinner
     */
    showLoading(show) {
        const loading = document.getElementById('prStoryLoading');
        const header = document.getElementById('prStoryHeader');
        const summary = document.getElementById('prStorySummary');
        const timeline = document.getElementById('prStoryTimeline');

        if (loading) {
            loading.style.display = show ? 'flex' : 'none';
        }

        if (header && summary && timeline) {
            const displayValue = show ? 'none' : '';
            header.style.display = displayValue;
            summary.style.display = displayValue;
            timeline.style.display = displayValue;
        }
    }

    /**
     * Show error message.
     *
     * @param {string} message - Error message
     */
    showError(message) {
        const error = document.getElementById('prStoryError');
        const header = document.getElementById('prStoryHeader');
        const summary = document.getElementById('prStorySummary');
        const timeline = document.getElementById('prStoryTimeline');

        if (error) {
            error.style.display = 'flex';
            error.querySelector('p').textContent = message;
        }

        if (header && summary && timeline) {
            header.style.display = 'none';
            summary.style.display = 'none';
            timeline.style.display = 'none';
        }
    }

    /**
     * Hide error message.
     */
    hideError() {
        const error = document.getElementById('prStoryError');
        if (error) {
            error.style.display = 'none';
        }
    }

    /**
     * Show empty state.
     */
    showEmpty() {
        const timeline = document.getElementById('prStoryTimeline');
        if (timeline) {
            timeline.innerHTML = '<div class="pr-story-empty">No events found for this PR</div>';
        }
    }

    /**
     * Format relative time (e.g., "2 hours ago").
     *
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Relative time string
     */
    formatRelativeTime(timestamp) {
        return window.MetricsUtils?.formatRelativeTime(timestamp) || timestamp;
    }

    /**
     * Format absolute time for hover tooltip.
     *
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Formatted timestamp
     */
    formatAbsoluteTime(timestamp) {
        return window.MetricsUtils?.formatTimestamp(timestamp) || timestamp;
    }

    /**
     * Format date for header.
     *
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Formatted date
     */
    formatDate(timestamp) {
        try {
            const date = new Date(timestamp);
            return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        } catch {
            return timestamp;
        }
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
        // Local fallback with proper HTML escaping
        if (text == null) return '';
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
}

// Global function to open PR Story modal
function openPRStory(repository, prNumber) {
    if (!window.prStoryModal) {
        window.prStoryModal = new PRStoryModal();
        window.prStoryModal.initialize();
    }

    window.prStoryModal.open(repository, prNumber);
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    // Only create if not already initialized (e.g., by openPRStory being called earlier)
    if (!window.prStoryModal) {
        console.log('[PRStory] Initializing PR Story modal');
        window.prStoryModal = new PRStoryModal();
        window.prStoryModal.initialize();
    }
});

// Export to window for non-module usage
if (typeof window !== 'undefined') {
    window.openPRStory = openPRStory;
    window.PRStoryModal = PRStoryModal;
}

// ESM exports
export { PRStoryModal, openPRStory };
