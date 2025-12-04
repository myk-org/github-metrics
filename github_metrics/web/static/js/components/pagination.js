/**
 * Reusable Pagination Component
 *
 * Usage:
 *   const pagination = new Pagination({
 *     container: document.getElementById('my-pagination'),
 *     pageSize: 10,
 *     pageSizeOptions: [10, 25, 50, 100],
 *     onPageChange: (page, pageSize) => { ... },
 *     onPageSizeChange: (pageSize) => { ... }
 *   });
 *   pagination.update({ total: 100, page: 1, pageSize: 10 });
 */

// Instance counter for generating unique IDs
let paginationInstanceCounter = 0;

export class Pagination {
    constructor(options) {
        this.container = options.container;
        this.pageSize = options.pageSize || 10;
        this.pageSizeOptions = options.pageSizeOptions || [10, 25, 50, 100];
        this.onPageChange = options.onPageChange || (() => {});
        this.onPageSizeChange = options.onPageSizeChange || (() => {});

        // Generate unique ID for this instance to avoid duplicate IDs
        this.instanceId = `pagination-${++paginationInstanceCounter}`;
        this.pageInputId = `page-number-input-${this.instanceId}`;
        this.paginationInfoId = `pagination-info-${this.instanceId}`;

        this.state = { total: 0, page: 1, pageSize: this.pageSize, totalPages: 0 };

        // Store bound handlers for removal in destroy()
        this.boundHandlers = {
            selectChange: null,
            prevClick: null,
            nextClick: null,
            pageKeydown: null,
            pageBlur: null
        };

        this.render();
        this.bindEvents();
    }

    update(state) {
        this.state = { ...this.state, ...state };
        // Prefer caller-provided totalPages, otherwise compute from total/pageSize
        if (!state.totalPages) {
            if (this.state.total === 0) {
                this.state.totalPages = 0;
            } else {
                this.state.totalPages = Math.ceil(this.state.total / this.state.pageSize);
            }
        }
        this.updateDisplay();
    }

    render() {
        this.container.innerHTML = `
            <div class="pagination-controls">
                <div class="pagination-size">
                    <label>Show</label>
                    <select class="page-size-select">
                        ${this.pageSizeOptions.map(size =>
                            `<option value="${size}" ${size === this.pageSize ? 'selected' : ''}>${size}</option>`
                        ).join('')}
                    </select>
                    <label>per page</label>
                </div>
                <div class="pagination-nav">
                    <button class="btn-pagination prev-btn" disabled>← Prev</button>
                    <label for="${this.pageInputId}" class="visually-hidden">Page number</label>
                    <input
                        type="number"
                        id="${this.pageInputId}"
                        class="page-number-input"
                        min="1"
                        max="1"
                        value="1"
                        aria-label="Go to page"
                        aria-describedby="${this.paginationInfoId}"
                    />
                    <span id="${this.paginationInfoId}" class="pagination-info">of 1</span>
                    <button class="btn-pagination next-btn" disabled>Next →</button>
                </div>
                <div class="pagination-total">Total: 0 items</div>
            </div>
        `;
    }

    updateDisplay() {
        const { total, page, totalPages } = this.state;

        const info = this.container.querySelector('.pagination-info');
        const totalEl = this.container.querySelector('.pagination-total');
        const prevBtn = this.container.querySelector('.prev-btn');
        const nextBtn = this.container.querySelector('.next-btn');
        const pageInput = this.container.querySelector('.page-number-input');

        if (info) info.textContent = `of ${totalPages}`;
        if (totalEl) totalEl.textContent = `Total: ${total} items`;
        if (prevBtn) prevBtn.disabled = page <= 1;
        if (nextBtn) nextBtn.disabled = page >= totalPages;

        if (pageInput) {
            // Handle empty dataset (totalPages = 0)
            if (totalPages === 0) {
                pageInput.value = 0;
                pageInput.max = 0;
                pageInput.disabled = true;
            } else {
                pageInput.value = page;
                pageInput.max = totalPages;
                pageInput.disabled = false;
            }
        }
    }

    bindEvents() {
        const select = this.container.querySelector('.page-size-select');
        const prevBtn = this.container.querySelector('.prev-btn');
        const nextBtn = this.container.querySelector('.next-btn');
        const pageInput = this.container.querySelector('.page-number-input');

        if (select) {
            this.boundHandlers.selectChange = (e) => {
                const newSize = parseInt(e.target.value, 10);
                if (isNaN(newSize) || newSize < 1) {
                    console.error('[Pagination] Invalid page size:', e.target.value);
                    return;
                }
                this.state.pageSize = newSize;
                this.state.page = 1;
                this.onPageSizeChange(newSize);
            };
            select.addEventListener('change', this.boundHandlers.selectChange);
        }

        if (prevBtn) {
            this.boundHandlers.prevClick = () => {
                if (this.state.page > 1) {
                    this.state.page--;
                    this.onPageChange(this.state.page, this.state.pageSize);
                }
            };
            prevBtn.addEventListener('click', this.boundHandlers.prevClick);
        }

        if (nextBtn) {
            this.boundHandlers.nextClick = () => {
                if (this.state.page < this.state.totalPages) {
                    this.state.page++;
                    this.onPageChange(this.state.page, this.state.pageSize);
                }
            };
            nextBtn.addEventListener('click', this.boundHandlers.nextClick);
        }

        if (pageInput) {
            const handlePageNavigation = () => {
                const inputValue = parseInt(pageInput.value, 10);

                if (isNaN(inputValue)) {
                    pageInput.value = this.state.page;
                    pageInput.setCustomValidity('Please enter a valid page number');
                    pageInput.reportValidity();
                    return;
                }

                const clampedPage = Math.max(1, Math.min(inputValue, this.state.totalPages));

                if (clampedPage !== inputValue) {
                    pageInput.value = clampedPage;
                    pageInput.setCustomValidity(`Page must be between 1 and ${this.state.totalPages}`);
                    pageInput.reportValidity();
                }

                if (clampedPage !== this.state.page) {
                    this.state.page = clampedPage;
                    this.onPageChange(this.state.page, this.state.pageSize);
                }

                pageInput.setCustomValidity('');
            };

            this.boundHandlers.pageKeydown = (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handlePageNavigation();
                }
            };
            this.boundHandlers.pageBlur = () => {
                handlePageNavigation();
            };

            pageInput.addEventListener('keydown', this.boundHandlers.pageKeydown);
            pageInput.addEventListener('blur', this.boundHandlers.pageBlur);
        }
    }

    /**
     * Hide pagination controls (for non-paginated data).
     */
    hide() {
        const controls = this.container.querySelector('.pagination-controls');
        if (controls) {
            controls.style.display = 'none';
        }
    }

    /**
     * Show pagination controls (reverse of hide()).
     */
    show() {
        const controls = this.container.querySelector('.pagination-controls');
        if (controls) {
            controls.style.display = '';
        }
    }

    /**
     * Clean up event listeners and resources.
     */
    destroy() {
        if (!this.container) return;

        const select = this.container.querySelector('.page-size-select');
        const prevBtn = this.container.querySelector('.prev-btn');
        const nextBtn = this.container.querySelector('.next-btn');
        const pageInput = this.container.querySelector('.page-number-input');

        // Remove all bound event listeners
        if (select && this.boundHandlers.selectChange) {
            select.removeEventListener('change', this.boundHandlers.selectChange);
        }
        if (prevBtn && this.boundHandlers.prevClick) {
            prevBtn.removeEventListener('click', this.boundHandlers.prevClick);
        }
        if (nextBtn && this.boundHandlers.nextClick) {
            nextBtn.removeEventListener('click', this.boundHandlers.nextClick);
        }
        if (pageInput) {
            if (this.boundHandlers.pageKeydown) {
                pageInput.removeEventListener('keydown', this.boundHandlers.pageKeydown);
            }
            if (this.boundHandlers.pageBlur) {
                pageInput.removeEventListener('blur', this.boundHandlers.pageBlur);
            }
        }

        // Clear stored references
        this.boundHandlers = null;
        this.container = null;
        this.onPageChange = null;
        this.onPageSizeChange = null;
    }
}
