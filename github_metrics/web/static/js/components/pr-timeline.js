/**
 * PR Timeline Component
 *
 * Shared PR story timeline rendering used by turnaround and team-dynamics modules.
 */

import { formatTimestamp, escapeHtml } from '../utils/formatters.js';

/**
 * Get event configuration (icon, label)
 */
export function getEventConfig(eventType) {
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
 * Render a single timeline event
 */
export function renderTimelineEvent(event) {
    const eventConfig = getEventConfig(event.event_type);
    const icon = eventConfig.icon;
    const label = eventConfig.label;

    let descriptionHtml = '';
    if (event.description) {
        descriptionHtml = `<div class="timeline-event-description">${escapeHtml(event.description)}</div>`;
    }

    const timeStr = formatTimestamp(event.timestamp);

    return `
        <div class="timeline-event-item">
            <div class="timeline-event-marker"></div>
            <div class="timeline-event-content">
                <div class="timeline-event-header">
                    <span class="timeline-event-icon">${icon}</span>
                    <span class="timeline-event-title">${escapeHtml(label)}</span>
                    <span class="timeline-event-time">${timeStr}</span>
                </div>
                ${descriptionHtml}
            </div>
        </div>
    `;
}

/**
 * Render PR story timeline
 */
export function renderPrStoryTimeline(storyData) {
    const events = storyData?.events || [];
    const summary = storyData?.summary || {
        total_commits: 0,
        total_reviews: 0,
        total_check_runs: 0,
        total_comments: 0
    };

    if (events.length === 0) {
        return '<div class="empty-state">No timeline events found for this PR.</div>';
    }

    const summaryHtml = `
        <div class="pr-story-summary">
            <span>📝 ${summary.total_commits} commits</span>
            <span>💬 ${summary.total_reviews} reviews</span>
            <span>▶️ ${summary.total_check_runs} check runs</span>
            <span>💭 ${summary.total_comments} comments</span>
        </div>
    `;

    const eventsHtml = events.map(event => renderTimelineEvent(event)).join('');

    return `
        ${summaryHtml}
        <div class="pr-timeline">
            ${eventsHtml}
        </div>
    `;
}
