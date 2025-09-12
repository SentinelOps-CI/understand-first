/**
 * Understand-First Virtual Scrolling Module
 * 
 * This module provides efficient virtual scrolling for large lists of nodes,
 * functions, and other data to maintain smooth performance.
 */

class VirtualScroll {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            itemHeight: options.itemHeight || 40,
            bufferSize: options.bufferSize || 5,
            threshold: options.threshold || 100, // Enable virtual scrolling for lists > 100 items
            renderFunction: options.renderFunction || this.defaultRenderFunction,
            updateFunction: options.updateFunction || this.defaultUpdateFunction,
            ...options
        };
        
        this.data = [];
        this.visibleItems = [];
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.totalHeight = 0;
        this.startIndex = 0;
        this.endIndex = 0;
        this.isVirtual = false;
        
        this.setupContainer();
        this.setupEventListeners();
    }

    /**
     * Setup container for virtual scrolling
     */
    setupContainer() {
        this.container.style.position = 'relative';
        this.container.style.overflow = 'auto';
        
        // Create viewport element
        this.viewport = document.createElement('div');
        this.viewport.style.position = 'relative';
        this.viewport.style.width = '100%';
        this.container.appendChild(this.viewport);
        
        // Create spacer for total height
        this.spacer = document.createElement('div');
        this.spacer.style.position = 'absolute';
        this.spacer.style.top = '0';
        this.spacer.style.left = '0';
        this.spacer.style.width = '1px';
        this.spacer.style.pointerEvents = 'none';
        this.container.appendChild(this.spacer);
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        this.container.addEventListener('scroll', this.handleScroll.bind(this));
        window.addEventListener('resize', this.handleResize.bind(this));
    }

    /**
     * Set data for virtual scrolling
     */
    setData(data) {
        this.data = data;
        this.totalHeight = data.length * this.options.itemHeight;
        
        // Determine if virtual scrolling is needed
        this.isVirtual = data.length > this.options.threshold;
        
        if (this.isVirtual) {
            this.setupVirtualScrolling();
        } else {
            this.setupNormalRendering();
        }
        
        this.updateSpacer();
        this.updateVisibleItems();
    }

    /**
     * Setup virtual scrolling
     */
    setupVirtualScrolling() {
        this.containerHeight = this.container.clientHeight;
        this.calculateVisibleRange();
        this.renderVisibleItems();
    }

    /**
     * Setup normal rendering for small lists
     */
    setupNormalRendering() {
        // Clear viewport
        this.viewport.innerHTML = '';
        
        // Render all items
        this.data.forEach((item, index) => {
            const element = this.options.renderFunction(item, index);
            this.viewport.appendChild(element);
        });
    }

    /**
     * Handle scroll events
     */
    handleScroll() {
        this.scrollTop = this.container.scrollTop;
        
        if (this.isVirtual) {
            this.updateVisibleItems();
        }
    }

    /**
     * Handle resize events
     */
    handleResize() {
        this.containerHeight = this.container.clientHeight;
        
        if (this.isVirtual) {
            this.calculateVisibleRange();
            this.updateVisibleItems();
        }
    }

    /**
     * Calculate visible range
     */
    calculateVisibleRange() {
        const visibleCount = Math.ceil(this.containerHeight / this.options.itemHeight);
        const bufferCount = this.options.bufferSize;
        
        this.startIndex = Math.max(0, Math.floor(this.scrollTop / this.options.itemHeight) - bufferCount);
        this.endIndex = Math.min(this.data.length - 1, this.startIndex + visibleCount + bufferCount * 2);
    }

    /**
     * Update visible items
     */
    updateVisibleItems() {
        if (!this.isVirtual) return;
        
        const newStartIndex = Math.max(0, Math.floor(this.scrollTop / this.options.itemHeight) - this.options.bufferSize);
        const newEndIndex = Math.min(this.data.length - 1, newStartIndex + Math.ceil(this.containerHeight / this.options.itemHeight) + this.options.bufferSize * 2);
        
        // Check if we need to update
        if (newStartIndex !== this.startIndex || newEndIndex !== this.endIndex) {
            this.startIndex = newStartIndex;
            this.endIndex = newEndIndex;
            this.renderVisibleItems();
        }
    }

    /**
     * Render visible items
     */
    renderVisibleItems() {
        // Clear viewport
        this.viewport.innerHTML = '';
        
        // Create fragment for efficient DOM manipulation
        const fragment = document.createDocumentFragment();
        
        // Render visible items
        for (let i = this.startIndex; i <= this.endIndex; i++) {
            const item = this.data[i];
            const element = this.options.renderFunction(item, i);
            
            // Set position
            element.style.position = 'absolute';
            element.style.top = (i * this.options.itemHeight) + 'px';
            element.style.left = '0';
            element.style.right = '0';
            element.style.height = this.options.itemHeight + 'px';
            
            fragment.appendChild(element);
        }
        
        this.viewport.appendChild(fragment);
        
        // Update viewport position
        this.viewport.style.transform = `translateY(${this.startIndex * this.options.itemHeight}px)`;
    }

    /**
     * Update spacer height
     */
    updateSpacer() {
        this.spacer.style.height = this.totalHeight + 'px';
    }

    /**
     * Default render function
     */
    defaultRenderFunction(item, index) {
        const element = document.createElement('div');
        element.className = 'virtual-item';
        element.textContent = item.label || item.name || item.toString();
        element.dataset.index = index;
        return element;
    }

    /**
     * Default update function
     */
    defaultUpdateFunction(element, item, index) {
        element.textContent = item.label || item.name || item.toString();
        element.dataset.index = index;
    }

    /**
     * Update item at specific index
     */
    updateItem(index, newItem) {
        if (index >= 0 && index < this.data.length) {
            this.data[index] = newItem;
            
            if (this.isVirtual && index >= this.startIndex && index <= this.endIndex) {
                // Update visible item
                const element = this.viewport.children[index - this.startIndex];
                if (element) {
                    this.options.updateFunction(element, newItem, index);
                }
            } else if (!this.isVirtual) {
                // Update in normal rendering
                const element = this.viewport.children[index];
                if (element) {
                    this.options.updateFunction(element, newItem, index);
                }
            }
        }
    }

    /**
     * Insert item at specific index
     */
    insertItem(index, item) {
        this.data.splice(index, 0, item);
        this.totalHeight = this.data.length * this.options.itemHeight;
        
        this.updateSpacer();
        
        if (this.isVirtual) {
            this.calculateVisibleRange();
            this.renderVisibleItems();
        } else {
            this.setupNormalRendering();
        }
    }

    /**
     * Remove item at specific index
     */
    removeItem(index) {
        if (index >= 0 && index < this.data.length) {
            this.data.splice(index, 1);
            this.totalHeight = this.data.length * this.options.itemHeight;
            
            this.updateSpacer();
            
            if (this.isVirtual) {
                this.calculateVisibleRange();
                this.renderVisibleItems();
            } else {
                this.setupNormalRendering();
            }
        }
    }

    /**
     * Scroll to specific index
     */
    scrollToIndex(index, behavior = 'smooth') {
        if (index >= 0 && index < this.data.length) {
            const scrollTop = index * this.options.itemHeight;
            this.container.scrollTo({
                top: scrollTop,
                behavior: behavior
            });
        }
    }

    /**
     * Scroll to top
     */
    scrollToTop(behavior = 'smooth') {
        this.container.scrollTo({
            top: 0,
            behavior: behavior
        });
    }

    /**
     * Scroll to bottom
     */
    scrollToBottom(behavior = 'smooth') {
        this.container.scrollTo({
            top: this.totalHeight,
            behavior: behavior
        });
    }

    /**
     * Get visible range
     */
    getVisibleRange() {
        return {
            start: this.startIndex,
            end: this.endIndex,
            total: this.data.length
        };
    }

    /**
     * Get item at specific index
     */
    getItem(index) {
        return this.data[index];
    }

    /**
     * Get all data
     */
    getData() {
        return [...this.data];
    }

    /**
     * Clear all data
     */
    clear() {
        this.data = [];
        this.totalHeight = 0;
        this.viewport.innerHTML = '';
        this.updateSpacer();
    }

    /**
     * Destroy virtual scroll instance
     */
    destroy() {
        this.container.removeEventListener('scroll', this.handleScroll);
        window.removeEventListener('resize', this.handleResize);
        
        if (this.viewport.parentNode) {
            this.viewport.parentNode.removeChild(this.viewport);
        }
        
        if (this.spacer.parentNode) {
            this.spacer.parentNode.removeChild(this.spacer);
        }
    }
}

/**
 * Virtual Scroll Manager for multiple lists
 */
class VirtualScrollManager {
    constructor() {
        this.instances = new Map();
        this.globalOptions = {
            itemHeight: 40,
            bufferSize: 5,
            threshold: 100
        };
    }

    /**
     * Create virtual scroll instance
     */
    create(id, container, options = {}) {
        const mergedOptions = { ...this.globalOptions, ...options };
        const instance = new VirtualScroll(container, mergedOptions);
        this.instances.set(id, instance);
        return instance;
    }

    /**
     * Get virtual scroll instance
     */
    get(id) {
        return this.instances.get(id);
    }

    /**
     * Destroy virtual scroll instance
     */
    destroy(id) {
        const instance = this.instances.get(id);
        if (instance) {
            instance.destroy();
            this.instances.delete(id);
        }
    }

    /**
     * Destroy all instances
     */
    destroyAll() {
        this.instances.forEach((instance, id) => {
            instance.destroy();
        });
        this.instances.clear();
    }

    /**
     * Update global options
     */
    updateGlobalOptions(options) {
        this.globalOptions = { ...this.globalOptions, ...options };
        
        // Update existing instances
        this.instances.forEach(instance => {
            instance.options = { ...instance.options, ...options };
        });
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { VirtualScroll, VirtualScrollManager };
} else if (typeof window !== 'undefined') {
    window.VirtualScroll = VirtualScroll;
    window.VirtualScrollManager = VirtualScrollManager;
}
