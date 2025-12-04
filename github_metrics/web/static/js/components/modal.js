/**
 * Reusable Modal Component
 *
 * A flexible modal dialog component with support for:
 * - Title and body content management
 * - Loading states
 * - Open/close with overlay click and ESC key
 * - Body scroll locking
 * - Focus management
 * - Event callbacks
 *
 * Usage:
 *   const modal = new Modal({
 *     id: 'myModal',
 *     onOpen: (data) => console.log('Modal opened with:', data),
 *     onClose: () => console.log('Modal closed'),
 *     closeOnOverlay: true,  // Default: true
 *     closeOnEscape: true    // Default: true
 *   });
 *
 *   // Open modal with optional data
 *   modal.open({ userId: 123 });
 *
 *   // Update title and content
 *   modal.setTitle('User Details');
 *   modal.setBody('<p>User information here...</p>');
 *
 *   // Show loading state
 *   modal.showLoading('Loading user data...');
 *
 *   // Close modal
 *   modal.close();
 *
 *   // Check if open
 *   if (modal.isOpen()) {
 *     console.log('Modal is currently visible');
 *   }
 *
 * HTML Structure Requirements:
 *   <div id="myModal" class="modal">
 *     <div class="modal-content">
 *       <div class="modal-header">
 *         <h2 id="myModalTitle">Title</h2>
 *         <button class="close-modal">&times;</button>
 *       </div>
 *       <div class="modal-body">
 *         <!-- Body content -->
 *       </div>
 *     </div>
 *   </div>
 *
 * CSS Classes:
 *   - .modal - Base modal container (overlay)
 *   - .modal.show - Visible state
 *   - .modal-content - Content container
 *   - .modal-header - Header section
 *   - .modal-body - Body section
 *   - .close-modal - Close button
 *
 * Features:
 *   - Overlay click to close (configurable)
 *   - ESC key to close (configurable)
 *   - Body scroll lock when modal is open
 *   - Focus trap (prevents tabbing outside modal)
 *   - Loading state with spinner
 */

// Module-scoped state for managing body scroll lock across multiple modals
let modalOpenCount = 0;
let originalBodyOverflow = '';

export class Modal {
    /**
     * Create a new Modal instance.
     * @param {Object} options - Configuration options
     * @param {string} options.id - Modal element ID (required)
     * @param {Function} [options.onOpen] - Callback when modal opens, receives data parameter
     * @param {Function} [options.onClose] - Callback when modal closes
     * @param {boolean} [options.closeOnOverlay=true] - Close modal when clicking overlay
     * @param {boolean} [options.closeOnEscape=true] - Close modal on ESC key
     */
    constructor(options) {
        this.id = options.id;
        this.onOpen = options.onOpen || (() => {});
        this.onClose = options.onClose || (() => {});
        this.closeOnOverlay = options.closeOnOverlay !== false; // Default: true
        this.closeOnEscape = options.closeOnEscape !== false;   // Default: true

        this.modal = null;
        this.modalTitle = null;
        this.modalBody = null;
        this.closeButton = null;
        this.isOpenState = false;
        this.escapeHandler = null;
        this.focusTrapHandler = null;
        this.focusableElements = [];

        this.initialize();
    }

    /**
     * Initialize the modal by finding DOM elements and setting up event listeners.
     */
    initialize() {
        // Find modal elements
        this.modal = document.getElementById(this.id);
        if (!this.modal) {
            console.error(`[Modal] Modal element with id="${this.id}" not found`);
            return;
        }

        this.modalTitle = document.getElementById(`${this.id}Title`);
        this.modalBody = this.modal.querySelector('.modal-body');
        this.closeButton = this.modal.querySelector('.close-modal');

        if (!this.modalBody) {
            console.error(`[Modal] Modal body not found in modal #${this.id}`);
        }

        // Set up event listeners
        this.setupEventListeners();

        console.debug(`[Modal] Initialized modal: ${this.id}`);
    }

    /**
     * Set up event listeners for modal interactions.
     */
    setupEventListeners() {
        if (!this.modal) return;

        // Close button click
        if (this.closeButton) {
            this.closeButton.addEventListener('click', () => {
                this.close();
            });
        }

        // Overlay click to close (if enabled)
        if (this.closeOnOverlay) {
            this.modal.addEventListener('click', (e) => {
                if (e.target === this.modal) {
                    this.close();
                }
            });
        }

        console.debug(`[Modal] Event listeners set up for modal: ${this.id}`);
    }

    /**
     * Open the modal.
     * @param {*} [data] - Optional data to pass to onOpen callback
     */
    open(data) {
        if (!this.modal) {
            console.error(`[Modal] Cannot open modal - element not found: ${this.id}`);
            return;
        }

        // Show modal
        this.modal.classList.add('show');
        this.isOpenState = true;

        // Lock body scroll (using counter-based approach for multiple modals)
        if (modalOpenCount === 0) {
            originalBodyOverflow = document.body.style.overflow;
            document.body.style.overflow = 'hidden';
        }
        modalOpenCount++;

        // Set up ESC key handler (if enabled)
        if (this.closeOnEscape && !this.escapeHandler) {
            this.escapeHandler = (e) => {
                if (e.key === 'Escape' && this.isOpen()) {
                    this.close();
                }
            };
            document.addEventListener('keydown', this.escapeHandler);
        }

        // Set up focus trap
        this.trapFocus();

        // Call onOpen callback with data
        this.onOpen(data);

        console.debug(`[Modal] Opened modal: ${this.id}`);
    }

    /**
     * Close the modal.
     */
    close() {
        if (!this.modal) return;

        // Hide modal
        this.modal.classList.remove('show');
        this.isOpenState = false;

        // Unlock body scroll (using counter-based approach for multiple modals)
        modalOpenCount--;
        if (modalOpenCount === 0) {
            document.body.style.overflow = originalBodyOverflow;
        }

        // Remove ESC key handler
        if (this.escapeHandler) {
            document.removeEventListener('keydown', this.escapeHandler);
            this.escapeHandler = null;
        }

        // Remove focus trap handler
        if (this.focusTrapHandler) {
            document.removeEventListener('keydown', this.focusTrapHandler);
            this.focusTrapHandler = null;
        }

        // Call onClose callback
        this.onClose();

        console.debug(`[Modal] Closed modal: ${this.id}`);
    }

    /**
     * Trap focus within the modal.
     * Prevents tabbing outside modal by cycling focus between first and last focusable element.
     */
    trapFocus() {
        if (!this.modal) return;

        // Find all focusable elements within the modal
        const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
        this.focusableElements = Array.from(this.modal.querySelectorAll(focusableSelector));

        // Filter out hidden or disabled elements
        this.focusableElements = this.focusableElements.filter(el => {
            return !el.hasAttribute('disabled') &&
                   el.offsetWidth > 0 &&
                   el.offsetHeight > 0 &&
                   window.getComputedStyle(el).visibility !== 'hidden';
        });

        // Focus the first focusable element if available
        if (this.focusableElements.length > 0) {
            this.focusableElements[0].focus();
        }

        // Handle Tab/Shift+Tab to trap focus
        this.focusTrapHandler = (e) => {
            if (e.key !== 'Tab' || !this.isOpen()) return;

            const firstElement = this.focusableElements[0];
            const lastElement = this.focusableElements[this.focusableElements.length - 1];

            // Handle single or zero focusable elements
            if (this.focusableElements.length === 0) {
                e.preventDefault();
                return;
            }

            if (this.focusableElements.length === 1) {
                e.preventDefault();
                firstElement.focus();
                return;
            }

            // Shift+Tab on first element: go to last
            if (e.shiftKey && document.activeElement === firstElement) {
                e.preventDefault();
                lastElement.focus();
            }
            // Tab on last element: go to first
            else if (!e.shiftKey && document.activeElement === lastElement) {
                e.preventDefault();
                firstElement.focus();
            }
        };

        document.addEventListener('keydown', this.focusTrapHandler);
    }

    /**
     * Check if the modal is currently open.
     * @returns {boolean} True if modal is open
     */
    isOpen() {
        return this.isOpenState;
    }

    /**
     * Set the modal title.
     * @param {string} title - Title text
     */
    setTitle(title) {
        if (this.modalTitle) {
            this.modalTitle.textContent = title;
        }
    }

    /**
     * Set the modal body content.
     * @param {string} html - HTML content for modal body
     */
    setBody(html) {
        if (this.modalBody) {
            this.modalBody.innerHTML = html;
        }
    }

    /**
     * Show loading state in modal body.
     * @param {string} [message='Loading...'] - Loading message to display
     */
    showLoading(message = 'Loading...') {
        if (!this.modalBody) return;

        const loadingHtml = `
            <div class="modal-loading" style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 20px; text-align: center;">
                <div class="spinner" style="border: 4px solid var(--border-color); border-top: 4px solid var(--primary-color); border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin-bottom: 15px;"></div>
                <p style="color: var(--text-secondary);">${this.escapeHtml(message)}</p>
            </div>
        `;

        this.setBody(loadingHtml);
    }

    /**
     * Escape HTML to prevent XSS.
     * @param {string} text - Text to escape
     * @returns {string} Escaped text
     */
    escapeHtml(text) {
        if (text == null) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
