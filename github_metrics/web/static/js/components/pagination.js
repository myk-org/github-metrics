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

export class Pagination {
    constructor(options) {
        this.container = options.container;
        this.pageSize = options.pageSize || 10;
        this.pageSizeOptions = options.pageSizeOptions || [10, 25, 50, 100];
        this.onPageChange = options.onPageChange || (() => {});
        this.onPageSizeChange = options.onPageSizeChange || (() => {});

        this.state = { total: 0, page: 1, pageSize: this.pageSize, totalPages: 0 };
        this.render();
        this.bindEvents();
    }

    update(state) {
        this.state = { ...this.state, ...state };
        this.state.totalPages = Math.ceil(this.state.total / this.state.pageSize) || 1;
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
                    <label for="page-number-input" class="visually-hidden">Page number</label>
                    <input
                        type="number"
                        id="page-number-input"
                        class="page-number-input"
                        min="1"
                        max="1"
                        value="1"
                        aria-label="Go to page"
                        aria-describedby="pagination-info"
                    />
                    <span id="pagination-info" class="pagination-info">of 1</span>
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
            pageInput.value = page;
            pageInput.max = totalPages;
        }
    }

    bindEvents() {
        const select = this.container.querySelector('.page-size-select');
        const prevBtn = this.container.querySelector('.prev-btn');
        const nextBtn = this.container.querySelector('.next-btn');
        const pageInput = this.container.querySelector('.page-number-input');

        if (select) {
            select.addEventListener('change', (e) => {
                const newSize = parseInt(e.target.value, 10);
                if (isNaN(newSize) || newSize < 1) {
                    console.error('[Pagination] Invalid page size:', e.target.value);
                    return;
                }
                this.state.pageSize = newSize;
                this.state.page = 1;
                this.onPageSizeChange(newSize);
            });
        }

        if (prevBtn) {
            prevBtn.addEventListener('click', () => {
                if (this.state.page > 1) {
                    this.state.page--;
                    this.onPageChange(this.state.page, this.state.pageSize);
                }
            });
        }

        if (nextBtn) {
            nextBtn.addEventListener('click', () => {
                if (this.state.page < this.state.totalPages) {
                    this.state.page++;
                    this.onPageChange(this.state.page, this.state.pageSize);
                }
            });
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

            pageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    handlePageNavigation();
                }
            });

            pageInput.addEventListener('blur', () => {
                handlePageNavigation();
            });
        }
    }
}
