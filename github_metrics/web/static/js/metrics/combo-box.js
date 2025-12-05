/* global Event */

/**
 * ComboBox Component - Unified dropdown + free text input with fuzzy search
 *
 * Features:
 * - Opens dropdown on focus
 * - Free text input with fuzzy search filtering
 * - Keyboard navigation (Arrow Up/Down, Enter, Escape)
 * - Click outside to close
 * - Light/dark theme support via CSS variables
 * - ARIA accessibility attributes
 * - Multi-select mode with chips/tags
 * - Pure vanilla JavaScript - NO external libraries
 */

class ComboBox {
    /**
     * Create a ComboBox instance
     * @param {Object} config - Configuration options
     * @param {HTMLElement} config.container - Container element for the combo-box
     * @param {string} config.inputId - ID of the input element to transform
     * @param {string} config.placeholder - Placeholder text for the input
     * @param {Array<{value: string, label: string}>} config.options - Array of options
     * @param {boolean} config.allowFreeText - Allow free text input (default: true)
     * @param {boolean} config.multiSelect - Enable multi-select mode with chips (default: false)
     * @param {boolean} config.debug - Enable debug logging (default: false)
     * @param {Function} config.onSelect - Callback when option is selected
     * @param {Function} config.onInput - Callback when input value changes
     */
    constructor(config) {
        // Guard against missing config object
        if (!config) {
            throw new Error('ComboBox: config object is required');
        }

        // Validate container
        if (!config.container || !(config.container instanceof HTMLElement)) {
            throw new Error('ComboBox: config.container must be a valid DOM element');
        }

        this.container = config.container;
        this.inputId = config.inputId;
        this.placeholder = config.placeholder || '';
        this.options = config.options || [];
        this.allowFreeText = config.allowFreeText !== false;
        this.multiSelect = config.multiSelect || false;
        this.debug = config.debug || false;
        this.onSelect = config.onSelect || (() => {});
        this.onInput = config.onInput || (() => {});

        this.input = null;
        this.dropdown = null;
        this.clearButton = null;
        this.chipsContainer = null;
        this.highlightedIndex = -1;
        this.filteredOptions = [];
        this.isOpen = false;
        this.blurTimeout = null;
        this._isInitialized = false;

        // Multi-select state
        this.selectedItems = [];

        // Bound event handlers for cleanup
        this.scrollHandler = null;
        this.resizeHandler = null;
        this._boundHandleClickOutside = null;
        this._boundHandleFocus = null;
        this._boundHandleInput = null;
        this._boundHandleBlur = null;
        this._boundHandleKeydown = null;
        this._onClearClick = null;

        this._initialize();
    }

    /**
     * Initialize the combo-box
     * @private
     */
    _initialize() {
        // Find the input element
        this.input = document.getElementById(this.inputId);
        if (!this.input) {
            throw new Error(`ComboBox: Input element not found: ${this.inputId}`);
        }

        // Validate container contains input element
        if (!this.container.contains(this.input)) {
            throw new Error(`ComboBox: container must contain input element #${this.inputId}`);
        }

        // Set placeholder
        this.input.placeholder = this.placeholder;

        // Add combo-box wrapper class to container
        this.container.classList.add('combo-box');

        // Add combo-box class to input
        this.input.classList.add('combo-box-input');

        // Set ARIA attributes
        this.input.setAttribute('role', 'combobox');
        this.input.setAttribute('aria-autocomplete', 'list');
        this.input.setAttribute('aria-expanded', 'false');
        this.input.setAttribute('aria-haspopup', 'listbox');

        // Create dropdown element
        this._createDropdown();

        // Create chips container for multi-select mode
        if (this.multiSelect) {
            this._createChipsContainer();
        }

        // Create clear button
        this._createClearButton();

        // Set up event listeners
        this._setupEventListeners();

        // Sync clear button visibility with initial input value
        this._updateClearButtonVisibility();

        if (this.debug) {
            console.log(`[ComboBox] Initialized for input #${this.inputId}`);
        }
        this._isInitialized = true;
    }

    /**
     * Create dropdown element
     * @private
     */
    _createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'combo-box-dropdown';
        this.dropdown.setAttribute('role', 'listbox');
        this.dropdown.id = `${this.inputId}-dropdown`;

        // Set ARIA relationship
        this.input.setAttribute('aria-controls', this.dropdown.id);

        // Append dropdown to container
        this.container.appendChild(this.dropdown);
    }

    /**
     * Create chips container for multi-select mode
     * @private
     */
    _createChipsContainer() {
        this.chipsContainer = document.createElement('div');
        this.chipsContainer.className = 'selected-chips';
        this.chipsContainer.setAttribute('role', 'list');
        this.chipsContainer.setAttribute('aria-label', 'Selected items');

        // Insert before input
        this.container.insertBefore(this.chipsContainer, this.input);
    }

    /**
     * Create clear button element
     * @private
     */
    _createClearButton() {
        this.clearButton = document.createElement('button');
        this.clearButton.className = 'combo-box-clear';
        this.clearButton.type = 'button';
        this.clearButton.innerHTML = '&times;';
        this.clearButton.setAttribute('aria-label', 'Clear input');
        this.clearButton.style.display = 'none'; // Initially hidden

        // Insert clear button after input
        this.input.parentNode.insertBefore(this.clearButton, this.input.nextSibling);

        // Store click handler for cleanup
        this._onClearClick = (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (this.multiSelect) {
                this.clearAll();
            } else {
                this.input.value = '';
                this._updateClearButtonVisibility();

                // Trigger input event to update filters
                this.input.dispatchEvent(new Event('input', { bubbles: true }));
            }

            // Focus back on input
            this.input.focus();
        };

        // Attach click handler
        this.clearButton.addEventListener('click', this._onClearClick);
    }

    /**
     * Update clear button visibility based on input value
     * @private
     */
    _updateClearButtonVisibility() {
        if (this.clearButton) {
            if (this.multiSelect) {
                // Show clear button if there are selected items
                this.clearButton.style.display = this.selectedItems.length > 0 ? 'block' : 'none';
            } else {
                this.clearButton.style.display = this.input.value ? 'block' : 'none';
            }
        }
    }

    /**
     * Render selected chips for multi-select mode
     * @private
     */
    _renderSelectedChips() {
        if (!this.multiSelect || !this.chipsContainer) {
            return;
        }

        // Clear existing chips
        this.chipsContainer.innerHTML = '';

        // Render each selected item as a chip
        this.selectedItems.forEach((item, index) => {
            const chip = document.createElement('span');
            chip.className = 'chip';
            chip.setAttribute('role', 'listitem');
            chip.setAttribute('data-index', index);

            const label = document.createElement('span');
            label.className = 'chip-label';
            label.textContent = item.label || item.value;

            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'chip-remove';
            removeBtn.setAttribute('aria-label', `Remove ${item.label || item.value}`);
            removeBtn.textContent = '×';
            removeBtn.dataset.index = index;

            // Remove button click handler
            removeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this._removeSelectedItem(parseInt(e.target.dataset.index, 10));
            });

            chip.appendChild(label);
            chip.appendChild(removeBtn);
            this.chipsContainer.appendChild(chip);
        });
    }

    /**
     * Escape HTML to prevent XSS
     * @private
     */
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Set up event listeners
     * @private
     */
    _setupEventListeners() {
        // Create and store bound handlers
        this._boundHandleFocus = () => this._handleFocus();
        this._boundHandleInput = (e) => this._handleInput(e);
        this._boundHandleBlur = () => this._handleBlur();
        this._boundHandleKeydown = (e) => this._handleKeydown(e);

        // Focus: Open dropdown
        this.input.addEventListener('focus', this._boundHandleFocus);

        // Input: Filter options
        this.input.addEventListener('input', this._boundHandleInput);

        // Blur: Close dropdown (with delay for click handling)
        this.input.addEventListener('blur', this._boundHandleBlur);

        // Keyboard navigation
        this.input.addEventListener('keydown', this._boundHandleKeydown);

        // Click outside to close - capture bound handler for cleanup
        this._boundHandleClickOutside = (e) => this._handleClickOutside(e);
        document.addEventListener('click', this._boundHandleClickOutside);
    }

    /**
     * Handle input focus
     * @private
     */
    _handleFocus() {
        this.open();
    }

    /**
     * Handle input change
     * @private
     */
    _handleInput(e) {
        const value = e.target.value;
        const trimmedValue = value.trim();
        this._filterOptions(value);
        this._renderDropdown();

        // Update clear button visibility
        this._updateClearButtonVisibility();

        // Trigger onInput callback with trimmed value
        if (this.allowFreeText) {
            this.onInput(trimmedValue);
        }

        // Open dropdown if closed
        if (!this.isOpen) {
            this.open();
        }
    }

    /**
     * Handle input blur
     * @private
     */
    _handleBlur() {
        // Delay closing to allow click events on dropdown options
        this.blurTimeout = setTimeout(() => {
            this.close();
        }, 150);
    }

    /**
     * Handle keyboard navigation
     * @private
     */
    _handleKeydown(e) {
        if (!this.isOpen) {
            // Open on Arrow Down
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.open();
            }
            return;
        }

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this._highlightNext();
                break;

            case 'ArrowUp':
                e.preventDefault();
                this._highlightPrevious();
                break;

            case 'Enter':
                e.preventDefault();
                this._selectHighlighted();
                break;

            case 'Escape':
                e.preventDefault();
                this.close();
                break;
        }
    }

    /**
     * Handle click outside
     * @private
     */
    _handleClickOutside(e) {
        if (!this.container.contains(e.target)) {
            this.close();
        }
    }

    /**
     * Filter options based on search query
     * @private
     */
    _filterOptions(query) {
        if (!query || query.trim() === '') {
            this.filteredOptions = [...this.options];
            return;
        }

        const searchTerm = query.toLowerCase();

        // Filter with case-insensitive includes
        const matches = this.options.filter(option =>
            option.label.toLowerCase().includes(searchTerm)
        );

        // Sort: items starting with query first, then others alphabetically
        this.filteredOptions = matches.sort((a, b) => {
            const aLabel = a.label.toLowerCase();
            const bLabel = b.label.toLowerCase();
            const aStarts = aLabel.startsWith(searchTerm);
            const bStarts = bLabel.startsWith(searchTerm);

            if (aStarts && !bStarts) return -1;
            if (!aStarts && bStarts) return 1;
            return aLabel.localeCompare(bLabel);
        });
    }

    /**
     * Render dropdown with filtered options
     * @private
     */
    _renderDropdown() {
        this.dropdown.innerHTML = '';

        if (this.filteredOptions.length === 0) {
            const noResults = document.createElement('div');
            noResults.className = 'combo-box-no-results';
            noResults.textContent = 'No matches found';
            this.dropdown.appendChild(noResults);
            return;
        }

        this.filteredOptions.forEach((option, index) => {
            const optionElement = document.createElement('div');
            optionElement.className = 'combo-box-option';
            optionElement.setAttribute('role', 'option');
            optionElement.setAttribute('data-value', option.value);
            optionElement.setAttribute('data-index', index);
            optionElement.id = `${this.inputId}-option-${index}`;

            // For multi-select mode, add checkbox
            if (this.multiSelect) {
                const isSelected = this.selectedItems.some(item => item.value === option.value);

                // Create checkbox span
                const checkbox = document.createElement('span');
                checkbox.className = `combo-box-checkbox ${isSelected ? 'checked' : ''}`;
                checkbox.setAttribute('aria-hidden', 'true');
                optionElement.appendChild(checkbox);

                // Create label span for text
                const labelSpan = document.createElement('span');
                labelSpan.className = 'combo-box-option-label';
                labelSpan.textContent = option.label;
                optionElement.appendChild(labelSpan);

                if (isSelected) {
                    optionElement.classList.add('selected');
                    optionElement.setAttribute('aria-selected', 'true');
                } else {
                    optionElement.setAttribute('aria-selected', 'false');
                }
            } else {
                // Single-select mode: Original behavior (no checkbox)
                optionElement.textContent = option.label;

                // Highlight if selected
                const isSelected = option.value === this.input.value || option.label === this.input.value;
                if (isSelected) {
                    optionElement.classList.add('selected');
                    // Set aria-selected only for currently selected value
                    optionElement.setAttribute('aria-selected', 'true');
                } else {
                    optionElement.setAttribute('aria-selected', 'false');
                }
            }

            // Click handler
            optionElement.addEventListener('mousedown', (e) => {
                e.preventDefault(); // Prevent blur
                this._selectOption(option);
            });

            this.dropdown.appendChild(optionElement);
        });
    }

    /**
     * Highlight next option
     * @private
     */
    _highlightNext() {
        if (this.filteredOptions.length === 0) return;

        this.highlightedIndex = (this.highlightedIndex + 1) % this.filteredOptions.length;
        this._updateHighlight();
    }

    /**
     * Highlight previous option
     * @private
     */
    _highlightPrevious() {
        if (this.filteredOptions.length === 0) return;

        this.highlightedIndex = this.highlightedIndex <= 0
            ? this.filteredOptions.length - 1
            : this.highlightedIndex - 1;
        this._updateHighlight();
    }

    /**
     * Update visual highlight
     * @private
     */
    _updateHighlight() {
        const options = this.dropdown.querySelectorAll('.combo-box-option');

        if (this.highlightedIndex >= 0 && this.highlightedIndex < options.length) {
            const highlightedOption = options[this.highlightedIndex];

            // Update aria-activedescendant on input
            this.input.setAttribute('aria-activedescendant', highlightedOption.id);

            // Add visual highlight class
            options.forEach((opt, idx) => {
                if (idx === this.highlightedIndex) {
                    opt.classList.add('highlighted');
                    opt.scrollIntoView({ block: 'nearest' });
                } else {
                    opt.classList.remove('highlighted');
                }
            });
        } else {
            // Clear aria-activedescendant when no highlight
            this.input.removeAttribute('aria-activedescendant');

            // Remove all highlights
            options.forEach(opt => opt.classList.remove('highlighted'));
        }
    }

    /**
     * Select highlighted option
     * @private
     */
    _selectHighlighted() {
        if (this.highlightedIndex >= 0 && this.highlightedIndex < this.filteredOptions.length) {
            this._selectOption(this.filteredOptions[this.highlightedIndex]);
        } else if (this.allowFreeText) {
            // Use free text value
            this.onSelect(this.input.value);
            this.close();
        }
    }

    /**
     * Select an option
     * @private
     */
    _selectOption(option) {
        if (this.multiSelect) {
            // Multi-select mode: Add to selected items if not already selected
            const exists = this.selectedItems.some(item => item.value === option.value);
            if (!exists) {
                this.selectedItems.push({
                    value: option.value,
                    label: option.label || option.value
                });
                this._renderSelectedChips();
                this.input.value = ''; // Clear input for next selection
                this._updateClearButtonVisibility();

                // Dispatch input event
                this.input.dispatchEvent(new Event('input', { bubbles: true }));

                // Call onSelect with all selected values
                this.onSelect(this.getSelectedValues());
            }
            // Keep dropdown open for multiple selections
            // Don't close the dropdown - user can continue selecting
        } else {
            // Single-select mode: Original behavior
            // Update all options' aria-selected state
            const options = this.dropdown.querySelectorAll('.combo-box-option');
            options.forEach((opt) => {
                const dataValue = opt.getAttribute('data-value');
                if (dataValue === option.value) {
                    opt.setAttribute('aria-selected', 'true');
                    opt.classList.add('selected');
                } else {
                    opt.setAttribute('aria-selected', 'false');
                    opt.classList.remove('selected');
                }
            });

            this.input.value = option.label;
            this._updateClearButtonVisibility();
            this.input.removeAttribute('aria-activedescendant');

            // Dispatch input event so external listeners (like turnaround.js filters) can react
            this.input.dispatchEvent(new Event('input', { bubbles: true }));

            // Note: onSelect is called AFTER the input event, allowing external
            // listeners to react to value changes before selection-specific logic
            this.onSelect(option.value);
            this.close();
        }
    }

    /**
     * Remove a selected item from multi-select
     * @private
     */
    _removeSelectedItem(index) {
        if (!this.multiSelect) {
            return;
        }

        this.selectedItems.splice(index, 1);
        this._renderSelectedChips();
        this._updateClearButtonVisibility();

        // Dispatch input event for listeners
        this.input.dispatchEvent(new Event('input', { bubbles: true }));

        // Call onSelect with updated values
        this.onSelect(this.getSelectedValues());
    }

    /**
     * Position dropdown using fixed positioning
     * @private
     */
    _positionDropdown() {
        if (!this.dropdown || !this.input) return;

        const rect = this.input.getBoundingClientRect();
        this.dropdown.style.position = 'fixed';
        this.dropdown.style.top = `${rect.bottom + 4}px`;
        this.dropdown.style.left = `${rect.left}px`;
        this.dropdown.style.width = `${rect.width}px`;
    }

    /**
     * Open dropdown
     */
    open() {
        if (this.isOpen) return;

        this.isOpen = true;
        this.container.classList.add('open');
        this.input.setAttribute('aria-expanded', 'true');

        // Filter and render
        this._filterOptions(this.input.value);
        this._renderDropdown();

        // Position dropdown
        this._positionDropdown();

        // Add scroll/resize listeners to keep dropdown positioned
        this.scrollHandler = () => this._positionDropdown();
        this.resizeHandler = () => this._positionDropdown();
        window.addEventListener('scroll', this.scrollHandler, true);
        window.addEventListener('resize', this.resizeHandler);

        // Reset highlight
        this.highlightedIndex = -1;
    }

    /**
     * Close dropdown
     */
    close() {
        if (!this.isOpen) return;

        this.isOpen = false;
        this.container.classList.remove('open');
        this.input.setAttribute('aria-expanded', 'false');
        this.input.removeAttribute('aria-activedescendant');
        this.highlightedIndex = -1;

        // Remove scroll/resize listeners
        if (this.scrollHandler) {
            window.removeEventListener('scroll', this.scrollHandler, true);
            this.scrollHandler = null;
        }
        if (this.resizeHandler) {
            window.removeEventListener('resize', this.resizeHandler);
            this.resizeHandler = null;
        }

        // Clear blur timeout if exists
        if (this.blurTimeout) {
            clearTimeout(this.blurTimeout);
            this.blurTimeout = null;
        }
    }

    /**
     * Set options
     * @param {Array<{value: string, label: string}>} options - New options array
     */
    setOptions(options) {
        this.options = options || [];
        this.filteredOptions = [...this.options];

        if (this.isOpen) {
            this._renderDropdown();
        }
    }

    /**
     * Get initialization status
     * @returns {boolean} True if initialized successfully
     */
    get isInitialized() {
        return this._isInitialized;
    }

    /**
     * Get current value
     * @returns {string} Current input value
     */
    getValue() {
        return this.input.value;
    }

    /**
     * Get selected option value
     * Returns the underlying value of the selected option by searching for
     * an option whose label matches the current input value.
     * @returns {string|null} The selected option's value, or null if no option matches
     */
    getSelectedValue() {
        const currentValue = this.input.value;
        const matchedOption = this.options.find(opt => opt.label === currentValue);
        return matchedOption ? matchedOption.value : null;
    }

    /**
     * Get selected values (for multi-select mode)
     * @returns {Array<string>|string} Array of values in multi-select mode, single value otherwise
     */
    getSelectedValues() {
        if (this.multiSelect) {
            return this.selectedItems.map(item => item.value);
        }
        return this.getSelectedValue();
    }

    /**
     * Set value
     * @param {string} value - Value to set
     */
    setValue(value) {
        const option = this.options.find(opt => opt.value === value);
        if (option) {
            this.input.value = option.label;
        } else {
            this.input.value = value;
        }
        this._updateClearButtonVisibility();
    }

    /**
     * Set selected values (for multi-select mode)
     * @param {Array<string>} values - Array of values to set
     */
    setSelectedValues(values) {
        if (this.multiSelect && Array.isArray(values)) {
            this.selectedItems = values.map(v => {
                const option = this.options.find(opt => opt.value === v);
                return {
                    value: v,
                    label: option ? option.label : v
                };
            });
            this._renderSelectedChips();
            this._updateClearButtonVisibility();
        } else {
            this.setValue(values);
        }
    }

    /**
     * Clear value
     */
    clear() {
        this.input.value = '';
        this._updateClearButtonVisibility();
        this.close();
    }

    /**
     * Clear all selected items (for multi-select mode)
     */
    clearAll() {
        if (this.multiSelect) {
            this.selectedItems = [];
            this._renderSelectedChips();
        }
        this.clear();
        if (this.onSelect) {
            this.onSelect(this.multiSelect ? [] : null);
        }
    }

    /**
     * Destroy combo-box and clean up
     */
    destroy() {
        // Close to clean up event listeners
        this.close();

        // Remove input event listeners
        if (this.input) {
            if (this._boundHandleFocus) {
                this.input.removeEventListener('focus', this._boundHandleFocus);
                this._boundHandleFocus = null;
            }
            if (this._boundHandleInput) {
                this.input.removeEventListener('input', this._boundHandleInput);
                this._boundHandleInput = null;
            }
            if (this._boundHandleBlur) {
                this.input.removeEventListener('blur', this._boundHandleBlur);
                this._boundHandleBlur = null;
            }
            if (this._boundHandleKeydown) {
                this.input.removeEventListener('keydown', this._boundHandleKeydown);
                this._boundHandleKeydown = null;
            }
        }

        // Remove click outside listener
        if (this._boundHandleClickOutside) {
            document.removeEventListener('click', this._boundHandleClickOutside);
            this._boundHandleClickOutside = null;
        }

        // Remove dropdown
        if (this.dropdown && this.dropdown.parentNode) {
            this.dropdown.parentNode.removeChild(this.dropdown);
        }

        // Remove clear button click listener
        if (this.clearButton && this._onClearClick) {
            this.clearButton.removeEventListener('click', this._onClearClick);
            this._onClearClick = null;
        }

        // Remove clear button
        if (this.clearButton && this.clearButton.parentNode) {
            this.clearButton.parentNode.removeChild(this.clearButton);
        }

        // Remove chips container
        if (this.chipsContainer && this.chipsContainer.parentNode) {
            this.chipsContainer.parentNode.removeChild(this.chipsContainer);
        }

        // Remove classes
        this.container.classList.remove('combo-box', 'open');
        if (this.input) {
            this.input.classList.remove('combo-box-input');

            // Remove ARIA attributes
            this.input.removeAttribute('role');
            this.input.removeAttribute('aria-autocomplete');
            this.input.removeAttribute('aria-expanded');
            this.input.removeAttribute('aria-haspopup');
            this.input.removeAttribute('aria-controls');
        }

        // Clear timeout
        if (this.blurTimeout) {
            clearTimeout(this.blurTimeout);
        }

        if (this.debug) {
            console.log(`[ComboBox] Destroyed for input #${this.inputId}`);
        }

        // Reset initialization flag
        this._isInitialized = false;
    }
}

// Export to global window object for use in other modules
window.ComboBox = ComboBox;

export default ComboBox;
