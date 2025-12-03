/**
 * Navigation Module
 *
 * Handles sidebar navigation state management:
 * - Page routing via URL hash
 * - Sidebar toggle on mobile
 * - Active state management
 * - localStorage persistence
 */

class NavigationManager {
    constructor() {
        this.sidebar = document.getElementById('sidebar');
        this.sidebarToggle = document.getElementById('sidebar-toggle');
        this.sidebarCollapseToggle = document.getElementById('sidebar-collapse-toggle');
        this.mobileMenuToggle = document.getElementById('mobile-menu-toggle');
        this.sidebarOverlay = document.getElementById('sidebar-overlay');
        this.navItems = document.querySelectorAll('.nav-item');
        this.pages = document.querySelectorAll('.page');

        // Validate required DOM elements
        const missingElements = [];
        if (!this.sidebar) missingElements.push('sidebar');
        if (!this.sidebarCollapseToggle) missingElements.push('sidebar-collapse-toggle');
        if (!this.mobileMenuToggle) missingElements.push('mobile-menu-toggle');
        if (!this.sidebarOverlay) missingElements.push('sidebar-overlay');
        if (this.navItems.length === 0) missingElements.push('nav-items');
        if (this.pages.length === 0) missingElements.push('pages');
        if (missingElements.length > 0) {
            throw new Error(`Missing required DOM elements: ${missingElements.join(', ')}`);
        }

        this.currentPage = 'overview';
        this.isMobile = window.innerWidth < 1024;
        this.isCollapsed = false;

        // Store debounced resize handler for cleanup
        this._debouncedResizeHandler = null;

        this.initialize();
    }

    /**
     * Initialize navigation
     */
    initialize() {
        console.log('[Navigation] Initializing navigation manager');

        // Set up event listeners
        this.setupEventListeners();

        // Load saved page from localStorage or use hash
        this.loadInitialPage();

        // Load saved sidebar collapsed state
        this.loadSidebarState();

        // Handle window resize with debounce
        this._debouncedResizeHandler = this._debounce(() => this.handleResize(), 100);
        window.addEventListener('resize', this._debouncedResizeHandler);
    }

    /**
     * Debounce utility function
     * @private
     */
    _debounce(func, delay) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    /**
     * Set up event listeners
     */
    setupEventListeners() {
        // Mobile menu toggle
        if (this.mobileMenuToggle) {
            this.mobileMenuToggle.addEventListener('click', () => this.toggleSidebar());
        }

        // Sidebar toggle (inside sidebar)
        if (this.sidebarToggle) {
            this.sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        }

        // Sidebar collapse toggle (desktop only)
        if (this.sidebarCollapseToggle) {
            this.sidebarCollapseToggle.addEventListener('click', () => this.toggleSidebarCollapse());
        }

        // Sidebar overlay (close on click outside)
        if (this.sidebarOverlay) {
            this.sidebarOverlay.addEventListener('click', () => this.closeSidebar());
        }

        // Navigation items
        this.navItems.forEach(item => {
            item.addEventListener('click', (e) => this.handleNavClick(e));
        });

        // Hash change event
        window.addEventListener('hashchange', () => this.handleHashChange());

        // Keyboard navigation - Escape to close sidebar
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.sidebar.classList.contains('open')) {
                this.closeSidebar();
            }
        });
    }

    /**
     * Handle navigation item click
     */
    handleNavClick(event) {
        event.preventDefault();
        const navItem = event.currentTarget;
        const page = navItem.dataset.page;

        if (page) {
            this.navigateToPage(page);

            // Close sidebar on mobile after navigation
            if (this.isMobile) {
                this.closeSidebar();
            }
        }
    }

    /**
     * Navigate to a specific page
     */
    navigateToPage(page) {
        console.log(`[Navigation] Navigating to page: ${page}`);

        // Update URL hash
        window.location.hash = page;

        // Update current page
        this.currentPage = page;

        // Save to localStorage
        try {
            localStorage.setItem('lastViewedPage', page);
        } catch (error) {
            console.warn('[Navigation] Failed to save to localStorage:', error);
        }

        // Update UI
        this.updateActivePage();
        this.updateActiveNavItem();
    }

    /**
     * Update active page display
     */
    updateActivePage() {
        this.pages.forEach(page => {
            const pageId = `page-${this.currentPage}`;
            if (page.id === pageId) {
                page.classList.add('active');
                page.style.display = 'block';
            } else {
                page.classList.remove('active');
                page.style.display = 'none';
            }
        });
    }

    /**
     * Update active navigation item
     */
    updateActiveNavItem() {
        this.navItems.forEach(item => {
            if (item.dataset.page === this.currentPage) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }

    /**
     * Handle hash change
     */
    handleHashChange() {
        const hash = window.location.hash.slice(1); // Remove '#'
        if (hash && hash !== this.currentPage) {
            this.currentPage = hash;
            this.updateActivePage();
            this.updateActiveNavItem();
            try {
                localStorage.setItem('lastViewedPage', hash);
            } catch (error) {
                console.warn('[Navigation] Failed to save to localStorage:', error);
            }
        }
    }

    /**
     * Load initial page from hash or localStorage
     */
    loadInitialPage() {
        // Known valid pages
        const knownPages = Array.from(this.navItems).map(item => item.dataset.page);
        let initialPage = 'overview';

        // Check URL hash first
        const hash = window.location.hash.slice(1);
        if (hash && knownPages.includes(hash)) {
            initialPage = hash;
        } else if (hash) {
            // Invalid hash - fall back to overview
            console.warn(`[Navigation] Invalid page in URL hash: ${hash}, falling back to overview`);
            initialPage = 'overview';
            window.location.hash = 'overview';
        } else {
            // Check localStorage
            try {
                const savedPage = localStorage.getItem('lastViewedPage');
                if (savedPage && knownPages.includes(savedPage)) {
                    initialPage = savedPage;
                    // Update hash to match saved page
                    window.location.hash = savedPage;
                } else {
                    // Invalid or missing saved page - default to overview
                    if (savedPage) {
                        console.warn(`[Navigation] Invalid page in localStorage: ${savedPage}, falling back to overview`);
                    }
                    window.location.hash = 'overview';
                }
            } catch (error) {
                console.warn('[Navigation] Failed to read from localStorage:', error);
                // Default to overview
                window.location.hash = 'overview';
            }
        }

        this.currentPage = initialPage;
        this.updateActivePage();
        this.updateActiveNavItem();
    }

    /**
     * Toggle sidebar open/closed
     */
    toggleSidebar() {
        if (this.sidebar.classList.contains('open')) {
            this.closeSidebar();
        } else {
            this.openSidebar();
        }
    }

    /**
     * Open sidebar
     */
    openSidebar() {
        this.sidebar.classList.add('open');
        if (this.sidebarOverlay) {
            this.sidebarOverlay.classList.add('active');
        }
        try {
            localStorage.setItem('sidebarOpen', 'true');
        } catch (error) {
            console.warn('[Navigation] Failed to save to localStorage:', error);
        }
    }

    /**
     * Close sidebar
     */
    closeSidebar() {
        this.sidebar.classList.remove('open');
        if (this.sidebarOverlay) {
            this.sidebarOverlay.classList.remove('active');
        }
        try {
            localStorage.setItem('sidebarOpen', 'false');
        } catch (error) {
            console.warn('[Navigation] Failed to save to localStorage:', error);
        }
    }

    /**
     * Handle window resize
     */
    handleResize() {
        const wasMobile = this.isMobile;
        this.isMobile = window.innerWidth < 1024;

        // If transitioning from mobile to desktop, clear mobile overlay/open state so desktop sidebar is shown
        if (wasMobile && !this.isMobile) {
            this.closeSidebar();
        }
    }

    /**
     * Toggle sidebar collapse state (desktop only)
     */
    toggleSidebarCollapse() {
        if (this.isMobile) {
            return; // Don't collapse on mobile
        }

        this.isCollapsed = !this.isCollapsed;

        if (this.isCollapsed) {
            this.sidebar.classList.add('collapsed');
        } else {
            this.sidebar.classList.remove('collapsed');
        }

        // Save state to localStorage
        try {
            localStorage.setItem('sidebarCollapsed', this.isCollapsed ? 'true' : 'false');
        } catch (error) {
            console.warn('[Navigation] Failed to save sidebar state:', error);
        }
    }

    /**
     * Load sidebar collapsed state from localStorage
     */
    loadSidebarState() {
        if (this.isMobile) {
            return; // Don't apply collapsed state on mobile
        }

        try {
            const savedState = localStorage.getItem('sidebarCollapsed');
            if (savedState === 'true') {
                this.isCollapsed = true;
                this.sidebar.classList.add('collapsed');
            }
        } catch (error) {
            console.warn('[Navigation] Failed to load sidebar state:', error);
        }
    }
}

// Initialize navigation when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.navigationManager = new NavigationManager();
    });
} else {
    window.navigationManager = new NavigationManager();
}

// Export for module usage
export { NavigationManager };
