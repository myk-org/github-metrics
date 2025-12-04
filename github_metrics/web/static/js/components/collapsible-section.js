/**
 * Reusable CollapsibleSection Component
 *
 * Makes any section collapsible with expand/collapse controls.
 * Handles both .control-panel and .chart-container sections.
 * Persists collapsed state in localStorage.
 *
 * Usage:
 *   const section = new CollapsibleSection({
 *     container: document.querySelector('[data-section="my-section"]'),
 *     onToggle: (isCollapsed) => {
 *       console.log(`Section is ${isCollapsed ? 'collapsed' : 'expanded'}`);
 *     },
 *     startCollapsed: false
 *   });
 *
 *   // Programmatic control
 *   section.expand();
 *   section.collapse();
 *   section.toggle();
 *   const collapsed = section.isCollapsed();
 *
 * HTML Requirements:
 *   - Section container must have data-section="section-id" attribute
 *   - Collapse button must have class="collapse-btn" and data-section="section-id"
 *   - Content must have class="panel-content" or "chart-content"
 *
 * Example HTML:
 *   <div class="control-panel" data-section="filters">
 *     <div class="panel-header">
 *       <h2>Filters</h2>
 *       <button class="collapse-btn" data-section="filters">▼</button>
 *     </div>
 *     <div class="panel-content">
 *       <!-- Content here -->
 *     </div>
 *   </div>
 *
 * CSS Classes:
 *   - .collapsed - Added to container when collapsed
 *   - .collapse-btn - The toggle button (icon rotates when collapsed)
 *   - .panel-content - Content for .control-panel sections
 *   - .chart-content - Content for .chart-container sections
 *
 * LocalStorage:
 *   - Saves state to 'collapsedSections' JSON object
 *   - Key is the section's data-section attribute value
 */

// Debug logging flag - set to true for development debugging
const DEBUG = false;

export class CollapsibleSection {
    /**
     * Initialize collapsible section.
     * @param {Object} options - Configuration options
     * @param {HTMLElement} options.container - Section container with data-section attribute
     * @param {Function} [options.onToggle] - Callback when toggled, receives (isCollapsed)
     * @param {boolean} [options.startCollapsed=false] - Initial collapsed state
     * @param {boolean} [options.persistState=true] - Whether to persist state in localStorage
     */
    constructor(options) {
        this.container = options.container;
        this.onToggle = options.onToggle || (() => {});
        this.persistState = options.persistState !== false; // Default true
        this.boundClickHandler = null;

        // Get section ID from data-section attribute
        this.sectionId = this.container?.dataset.section;
        if (!this.sectionId) {
            throw new Error('[CollapsibleSection] Container must have data-section attribute');
        }

        // Find collapse button
        this.collapseBtn = this.container.querySelector(`.collapse-btn[data-section="${this.sectionId}"]`);
        if (!this.collapseBtn) {
            console.warn(`[CollapsibleSection] No collapse button found for section: ${this.sectionId}`);
        }

        // Find content element (.panel-content or .chart-content)
        this.contentElement = this.container.querySelector('.panel-content') ||
                              this.container.querySelector('.chart-content');
        if (!this.contentElement) {
            console.warn(`[CollapsibleSection] No content element found for section: ${this.sectionId}`);
        }

        // Determine initial state (localStorage > startCollapsed > default)
        const savedState = this.persistState ? this.loadCollapsedState() : null;
        const initialCollapsed = savedState !== null ? savedState : (options.startCollapsed || false);

        // Initialize state
        this.collapsed = false; // Will be set by setCollapsed

        // Bind events
        this.bindEvents();

        // Apply initial state
        if (initialCollapsed) {
            this.collapse();
        } else {
            this.expand();
        }
    }

    /**
     * Bind click event to collapse button.
     */
    bindEvents() {
        if (!this.collapseBtn) return;

        this.boundClickHandler = (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.toggle();
        };
        this.collapseBtn.addEventListener('click', this.boundClickHandler);
    }

    /**
     * Toggle collapsed state.
     */
    toggle() {
        if (this.collapsed) {
            this.expand();
        } else {
            this.collapse();
        }
    }

    /**
     * Expand the section.
     */
    expand() {
        this.setCollapsed(false);
    }

    /**
     * Collapse the section.
     */
    collapse() {
        this.setCollapsed(true);
    }

    /**
     * Set collapsed state.
     * @param {boolean} collapsed - Whether section should be collapsed
     */
    setCollapsed(collapsed) {
        this.collapsed = collapsed;

        // Update container class
        if (collapsed) {
            this.container.classList.add('collapsed');
        } else {
            this.container.classList.remove('collapsed');
        }

        // Update button icon, title, and aria-expanded
        if (this.collapseBtn) {
            // Icon: ▼ when expanded (pointing down), ▲ when collapsed (pointing up/right)
            this.collapseBtn.textContent = collapsed ? '▲' : '▼';
            this.collapseBtn.title = collapsed ? 'Expand' : 'Collapse';
            this.collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        }

        // Save state to localStorage
        if (this.persistState) {
            this.saveCollapsedState(collapsed);
        }

        // Notify consumer
        this.onToggle(collapsed);

        if (DEBUG) {
            console.log(`[CollapsibleSection] Section ${this.sectionId} ${collapsed ? 'collapsed' : 'expanded'}`);
        }
    }

    /**
     * Check if section is currently collapsed.
     * @returns {boolean} True if collapsed
     */
    isCollapsed() {
        return this.collapsed;
    }

    /**
     * Save collapsed state to localStorage.
     * @param {boolean} isCollapsed - Whether section is collapsed
     */
    saveCollapsedState(isCollapsed) {
        try {
            const state = JSON.parse(localStorage.getItem('collapsedSections') || '{}');
            state[this.sectionId] = isCollapsed;
            localStorage.setItem('collapsedSections', JSON.stringify(state));
        } catch (error) {
            console.warn('[CollapsibleSection] Failed to save state to localStorage:', error);
        }
    }

    /**
     * Load collapsed state from localStorage.
     * @returns {boolean|null} Collapsed state or null if not found
     */
    loadCollapsedState() {
        try {
            const state = JSON.parse(localStorage.getItem('collapsedSections') || '{}');
            return state[this.sectionId] !== undefined ? state[this.sectionId] : null;
        } catch (error) {
            console.warn('[CollapsibleSection] Failed to load state from localStorage:', error);
            return null;
        }
    }

    /**
     * Destroy the component and remove event listeners.
     */
    destroy() {
        // Remove event listener properly
        if (this.collapseBtn && this.boundClickHandler) {
            this.collapseBtn.removeEventListener('click', this.boundClickHandler);
            this.boundClickHandler = null;
        }
        this.collapseBtn = null;

        this.container = null;
        this.contentElement = null;
        this.onToggle = null;
    }
}

/**
 * Initialize all collapsible sections on a page.
 * @param {Object} options - Configuration options
 * @param {string} [options.selector='[data-section]'] - Selector for section containers
 * @param {Function} [options.onToggle] - Global callback for all sections
 * @param {boolean} [options.persistState=true] - Whether to persist state in localStorage
 * @returns {Array<CollapsibleSection>} Array of initialized CollapsibleSection instances
 */
export function initializeCollapsibleSections(options = {}) {
    const selector = options.selector || '[data-section]';
    const containers = document.querySelectorAll(selector);
    const instances = [];

    containers.forEach(container => {
        // Only initialize if container has a collapse button
        const sectionId = container.dataset.section;
        const hasCollapseBtn = container.querySelector(`.collapse-btn[data-section="${sectionId}"]`);

        if (hasCollapseBtn) {
            const instance = new CollapsibleSection({
                container,
                onToggle: options.onToggle,
                persistState: options.persistState
            });
            instances.push(instance);
        }
    });

    if (DEBUG) {
        console.log(`[CollapsibleSection] Initialized ${instances.length} collapsible sections`);
    }
    return instances;
}
