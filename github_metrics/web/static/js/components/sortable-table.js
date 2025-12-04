/**
 * Reusable SortableTable Component
 *
 * Makes any table sortable by clicking on column headers.
 * Handles different data types (string, number, date) automatically.
 *
 * Usage:
 *   const sortableTable = new SortableTable({
 *     table: document.getElementById('my-table'),
 *     data: [
 *       { name: 'Alice', score: 85, created: '2024-01-15T10:30:00Z' },
 *       { name: 'Bob', score: 92, created: '2024-01-14T09:20:00Z' }
 *     ],
 *     columns: {
 *       name: { type: 'string' },
 *       score: { type: 'number' },
 *       created: { type: 'date' }
 *     },
 *     onSort: (sortedData, column, direction) => {
 *       console.log(`Sorted by ${column} ${direction}`);
 *       // Re-render table with sortedData
 *     },
 *     renderRow: (item) => {
 *       return `<tr>
 *         <td>${item.name}</td>
 *         <td>${item.score}</td>
 *         <td>${item.created}</td>
 *       </tr>`;
 *     }
 *   });
 *
 *   // Update data
 *   sortableTable.update(newData);
 *
 *   // Get current sorted data
 *   const sorted = sortableTable.getData();
 *
 * HTML Requirements:
 *   - Table headers must have class="sortable" and data-column="columnName"
 *   - Example: <th class="sortable" data-column="name">Name</th>
 *
 * Column Configuration:
 *   - type: 'string' | 'number' | 'date'
 *   - Date type handles ISO 8601 strings (2024-01-15T10:30:00Z)
 *   - Number type handles numeric values
 *   - String type uses case-insensitive locale comparison
 *
 * CSS Classes:
 *   - .sortable - Applied to sortable header cells
 *   - .sort-asc - Applied when sorted ascending
 *   - .sort-desc - Applied when sorted descending
 */

export class SortableTable {
    /**
     * Initialize the sortable table.
     * @param {Object} options - Configuration options
     * @param {HTMLTableElement} options.table - The table element to make sortable
     * @param {Array} options.data - The data backing the table
     * @param {Object} options.columns - Column definitions with data types
     * @param {Function} options.onSort - Callback when sorted, receives (sortedData, column, direction)
     * @param {Function} [options.renderRow] - Optional function to render a single row from data item
     */
    constructor(options) {
        this.table = options.table;
        this.data = options.data || [];
        this.columns = options.columns || {};
        this.onSort = options.onSort || (() => {});
        this.renderRow = options.renderRow || null;

        this.state = {
            column: null,
            direction: 'asc'
        };

        this.bindEvents();
    }

    /**
     * Bind click events to sortable headers.
     */
    bindEvents() {
        if (!this.table) return;

        const headers = this.table.querySelectorAll('th.sortable');
        headers.forEach(header => {
            header.addEventListener('click', () => {
                const column = header.dataset.column;
                if (column) {
                    this.handleSort(column);
                }
            });
        });
    }

    /**
     * Handle sort when header is clicked.
     * @param {string} column - Column name to sort by
     */
    handleSort(column) {
        // Toggle direction if same column, otherwise reset to ascending
        if (this.state.column === column) {
            this.state.direction = this.state.direction === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.column = column;
            this.state.direction = 'asc';
        }

        // Sort the data
        const sortedData = this.sortData(this.data, column, this.state.direction);

        // Update visual indicators
        this.updateSortIndicators(column, this.state.direction);

        // Notify consumer
        this.onSort(sortedData, column, this.state.direction);
    }

    /**
     * Sort data by column and direction.
     * @param {Array} data - Array of data objects
     * @param {string} column - Column name
     * @param {string} direction - 'asc' or 'desc'
     * @returns {Array} Sorted data
     */
    sortData(data, column, direction) {
        const columnConfig = this.columns[column] || {};
        const dataType = columnConfig.type || 'string';

        const sorted = [...data].sort((a, b) => {
            let aVal = a[column];
            let bVal = b[column];

            // Handle null/undefined - sort to end
            if (aVal == null && bVal == null) return 0;
            if (aVal == null) return 1;
            if (bVal == null) return -1;

            // Sort based on data type
            switch (dataType) {
                case 'date':
                    return this.compareDates(aVal, bVal, direction);
                case 'number':
                    return this.compareNumbers(aVal, bVal, direction);
                case 'string':
                default:
                    return this.compareStrings(aVal, bVal, direction);
            }
        });

        return sorted;
    }

    /**
     * Compare date values.
     * Handles ISO 8601 date strings.
     * @param {string|Date} aVal - First value
     * @param {string|Date} bVal - Second value
     * @param {string} direction - Sort direction
     * @returns {number} Comparison result
     */
    compareDates(aVal, bVal, direction) {
        // Check for ISO date strings FIRST (before number check)
        // ISO dates look like: "2024-01-15", "2025-11-27T10:30:00" or "2025-11-27T10:30:00.000Z"
        const isoDateRegex = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2})?/;
        if (typeof aVal === 'string' && typeof bVal === 'string' &&
            isoDateRegex.test(aVal) && isoDateRegex.test(bVal)) {
            const aDate = new Date(aVal);
            const bDate = new Date(bVal);
            if (!isNaN(aDate.getTime()) && !isNaN(bDate.getTime())) {
                return direction === 'asc' ? aDate - bDate : bDate - aDate;
            }
        }

        // Fallback to string comparison if dates are invalid
        return this.compareStrings(aVal, bVal, direction);
    }

    /**
     * Compare numeric values.
     * @param {number|string} aVal - First value
     * @param {number|string} bVal - Second value
     * @param {string} direction - Sort direction
     * @returns {number} Comparison result
     */
    compareNumbers(aVal, bVal, direction) {
        // Try to parse as number (only if both are purely numeric)
        const aNum = parseFloat(aVal);
        const bNum = parseFloat(bVal);
        const aIsNum = !isNaN(aNum) && isFinite(aNum) && String(aVal).trim() === String(aNum);
        const bIsNum = !isNaN(bNum) && isFinite(bNum) && String(bVal).trim() === String(bNum);

        if (aIsNum && bIsNum) {
            // Numeric comparison
            return direction === 'asc' ? aNum - bNum : bNum - aNum;
        }

        // Fallback to string comparison if not valid numbers
        return this.compareStrings(aVal, bVal, direction);
    }

    /**
     * Compare string values (case-insensitive).
     * @param {*} aVal - First value
     * @param {*} bVal - Second value
     * @param {string} direction - Sort direction
     * @returns {number} Comparison result
     */
    compareStrings(aVal, bVal, direction) {
        const aStr = String(aVal).toLowerCase();
        const bStr = String(bVal).toLowerCase();

        if (direction === 'asc') {
            return aStr.localeCompare(bStr);
        }
        return bStr.localeCompare(aStr);
    }

    /**
     * Update visual sort indicators on table headers.
     * @param {string} column - Currently sorted column
     * @param {string} direction - Sort direction ('asc' or 'desc')
     */
    updateSortIndicators(column, direction) {
        if (!this.table) return;

        // Remove existing sort classes
        this.table.querySelectorAll('th.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });

        // Add sort class to current column
        const currentHeader = this.table.querySelector(`th.sortable[data-column="${column}"]`);
        if (currentHeader) {
            currentHeader.classList.add(`sort-${direction}`);
        }
    }

    /**
     * Update the table data and re-sort if needed.
     * @param {Array} data - New data array
     */
    update(data) {
        this.data = data || [];

        // If we have an active sort, re-apply it
        if (this.state.column) {
            const sortedData = this.sortData(this.data, this.state.column, this.state.direction);
            this.onSort(sortedData, this.state.column, this.state.direction);
        }
    }

    /**
     * Get current sorted data.
     * @returns {Array} Currently sorted data
     */
    getData() {
        if (this.state.column) {
            return this.sortData(this.data, this.state.column, this.state.direction);
        }
        return this.data;
    }
}
