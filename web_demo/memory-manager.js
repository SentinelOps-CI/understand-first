/**
 * Understand-First Memory Management Module
 * 
 * This module provides intelligent memory management for large graphs,
 * including object pooling, lazy loading, and garbage collection optimization.
 */

class MemoryManager {
    constructor() {
        this.pools = {
            nodes: new ObjectPool('node'),
            edges: new ObjectPool('edge'),
            styles: new ObjectPool('style'),
            positions: new ObjectPool('position'),
            callbacks: new ObjectPool('callback')
        };
        
        this.caches = {
            layout: new LRUCache(1000),
            styles: new LRUCache(500),
            search: new LRUCache(200),
            metrics: new LRUCache(100)
        };
        
        this.lazyLoaders = new Map();
        this.memoryThresholds = {
            warning: 0.7,    // 70% of available memory
            critical: 0.85,  // 85% of available memory
            max: 0.95        // 95% of available memory
        };
        
        this.memoryStats = {
            allocated: 0,
            freed: 0,
            peak: 0,
            current: 0
        };
        
        this.setupMemoryMonitoring();
        this.setupGarbageCollection();
    }

    /**
     * Setup memory monitoring
     */
    setupMemoryMonitoring() {
        // Monitor memory usage every 5 seconds
        setInterval(() => {
            this.checkMemoryUsage();
        }, 5000);
        
        // Monitor for memory pressure
        if ('memory' in performance) {
            setInterval(() => {
                this.analyzeMemoryPressure();
            }, 10000);
        }
    }

    /**
     * Setup garbage collection optimization
     */
    setupGarbageCollection() {
        // Weak references for cleanup
        this.weakRefs = new WeakMap();
        
        // Cleanup intervals
        this.cleanupIntervals = {
            pools: 30000,    // 30 seconds
            caches: 60000,   // 1 minute
            lazyLoaders: 120000 // 2 minutes
        };
        
        // Start cleanup timers
        Object.entries(this.cleanupIntervals).forEach(([type, interval]) => {
            setInterval(() => {
                this.cleanup(type);
            }, interval);
        });
    }

    /**
     * Check current memory usage
     */
    checkMemoryUsage() {
        if (!performance.memory) return;
        
        const memory = performance.memory;
        const usedRatio = memory.usedJSHeapSize / memory.jsHeapSizeLimit;
        
        this.memoryStats.current = memory.usedJSHeapSize;
        this.memoryStats.peak = Math.max(this.memoryStats.peak, memory.usedJSHeapSize);
        
        if (usedRatio > this.memoryThresholds.max) {
            this.handleCriticalMemory();
        } else if (usedRatio > this.memoryThresholds.critical) {
            this.handleCriticalMemory();
        } else if (usedRatio > this.memoryThresholds.warning) {
            this.handleMemoryWarning();
        }
    }

    /**
     * Analyze memory pressure patterns
     */
    analyzeMemoryPressure() {
        if (!performance.memory) return;
        
        const memory = performance.memory;
        const trend = this.calculateMemoryTrend();
        
        if (trend > 0.1) { // Growing by more than 10% per check
            this.handleMemoryGrowth();
        }
    }

    /**
     * Calculate memory usage trend
     */
    calculateMemoryTrend() {
        // This would track memory usage over time
        // For now, return a simple calculation
        return 0;
    }

    /**
     * Handle memory warning
     */
    handleMemoryWarning() {
        console.warn('Memory usage is high, optimizing...');
        
        // Clear least recently used caches
        this.caches.layout.evict(0.3); // Evict 30%
        this.caches.styles.evict(0.2); // Evict 20%
        
        // Optimize pools
        this.optimizePools();
    }

    /**
     * Handle critical memory situation
     */
    handleCriticalMemory() {
        console.error('Critical memory usage, aggressive cleanup...');
        
        // Aggressive cache clearing
        Object.values(this.caches).forEach(cache => {
            cache.evict(0.5); // Evict 50%
        });
        
        // Force pool cleanup
        Object.values(this.pools).forEach(pool => {
            pool.cleanup();
        });
        
        // Clear lazy loaders
        this.clearLazyLoaders();
        
        // Force garbage collection if available
        if (window.gc) {
            window.gc();
        }
    }

    /**
     * Handle memory growth
     */
    handleMemoryGrowth() {
        console.warn('Memory growing rapidly, preemptive cleanup...');
        
        // Preemptive cache clearing
        this.caches.search.evict(0.4);
        this.caches.metrics.evict(0.3);
        
        // Cleanup unused pools
        this.cleanupUnusedPools();
    }

    /**
     * Get object from pool
     */
    getFromPool(type, constructor) {
        if (!this.pools[type]) {
            this.pools[type] = new ObjectPool(type);
        }
        
        return this.pools[type].get(constructor);
    }

    /**
     * Return object to pool
     */
    returnToPool(type, obj) {
        if (this.pools[type]) {
            this.pools[type].return(obj);
        }
    }

    /**
     * Cache value with TTL
     */
    cache(key, value, ttl = 300000) { // 5 minutes default
        const cacheKey = this.generateCacheKey(key);
        const cacheValue = {
            value: value,
            timestamp: Date.now(),
            ttl: ttl
        };
        
        // Determine which cache to use based on key type
        let cache;
        if (key.startsWith('layout:')) {
            cache = this.caches.layout;
        } else if (key.startsWith('style:')) {
            cache = this.caches.styles;
        } else if (key.startsWith('search:')) {
            cache = this.caches.search;
        } else {
            cache = this.caches.metrics;
        }
        
        cache.set(cacheKey, cacheValue);
    }

    /**
     * Get value from cache
     */
    getFromCache(key) {
        const cacheKey = this.generateCacheKey(key);
        
        // Determine which cache to check
        let cache;
        if (key.startsWith('layout:')) {
            cache = this.caches.layout;
        } else if (key.startsWith('style:')) {
            cache = this.caches.styles;
        } else if (key.startsWith('search:')) {
            cache = this.caches.search;
        } else {
            cache = this.caches.metrics;
        }
        
        const cached = cache.get(cacheKey);
        if (cached && (Date.now() - cached.timestamp) < cached.ttl) {
            return cached.value;
        }
        
        // Remove expired entry
        if (cached) {
            cache.delete(cacheKey);
        }
        
        return null;
    }

    /**
     * Generate cache key
     */
    generateCacheKey(key) {
        // Simple hash function for cache keys
        let hash = 0;
        for (let i = 0; i < key.length; i++) {
            const char = key.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash; // Convert to 32-bit integer
        }
        return hash.toString(36);
    }

    /**
     * Setup lazy loading for large datasets
     */
    setupLazyLoader(id, loader, options = {}) {
        const lazyLoader = {
            id: id,
            loader: loader,
            loaded: false,
            data: null,
            options: {
                chunkSize: options.chunkSize || 100,
                delay: options.delay || 100,
                priority: options.priority || 'normal'
            }
        };
        
        this.lazyLoaders.set(id, lazyLoader);
        return lazyLoader;
    }

    /**
     * Load data lazily
     */
    async loadLazy(id, force = false) {
        const loader = this.lazyLoaders.get(id);
        if (!loader) return null;
        
        if (loader.loaded && !force) {
            return loader.data;
        }
        
        try {
            loader.data = await loader.loader();
            loader.loaded = true;
            return loader.data;
        } catch (error) {
            console.error(`Lazy loading failed for ${id}:`, error);
            return null;
        }
    }

    /**
     * Clear lazy loaders
     */
    clearLazyLoaders() {
        this.lazyLoaders.forEach((loader, id) => {
            if (loader.data && !loader.options.persistent) {
                loader.data = null;
                loader.loaded = false;
            }
        });
    }

    /**
     * Optimize object pools
     */
    optimizePools() {
        Object.values(this.pools).forEach(pool => {
            pool.optimize();
        });
    }

    /**
     * Cleanup unused pools
     */
    cleanupUnusedPools() {
        Object.entries(this.pools).forEach(([type, pool]) => {
            if (pool.getUsageRatio() < 0.1) { // Less than 10% usage
                pool.cleanup();
            }
        });
    }

    /**
     * Cleanup based on type
     */
    cleanup(type) {
        switch(type) {
            case 'pools':
                this.optimizePools();
                break;
            case 'caches':
                this.cleanupExpiredCaches();
                break;
            case 'lazyLoaders':
                this.clearLazyLoaders();
                break;
        }
    }

    /**
     * Cleanup expired cache entries
     */
    cleanupExpiredCaches() {
        Object.values(this.caches).forEach(cache => {
            cache.cleanup();
        });
    }

    /**
     * Get memory statistics
     */
    getMemoryStats() {
        const stats = {
            ...this.memoryStats,
            pools: {},
            caches: {},
            performance: null
        };
        
        // Pool statistics
        Object.entries(this.pools).forEach(([type, pool]) => {
            stats.pools[type] = {
                size: pool.size,
                used: pool.used,
                available: pool.available,
                usageRatio: pool.getUsageRatio()
            };
        });
        
        // Cache statistics
        Object.entries(this.caches).forEach(([type, cache]) => {
            stats.caches[type] = {
                size: cache.size,
                maxSize: cache.maxSize,
                hitRate: cache.getHitRate()
            };
        });
        
        // Performance memory info
        if (performance.memory) {
            stats.performance = {
                used: performance.memory.usedJSHeapSize,
                total: performance.memory.totalJSHeapSize,
                limit: performance.memory.jsHeapSizeLimit,
                usedRatio: performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit
            };
        }
        
        return stats;
    }

    /**
     * Force garbage collection
     */
    forceGC() {
        // Clear all caches
        Object.values(this.caches).forEach(cache => cache.clear());
        
        // Clean all pools
        Object.values(this.pools).forEach(pool => pool.cleanup());
        
        // Clear lazy loaders
        this.clearLazyLoaders();
        
        // Force browser GC if available
        if (window.gc) {
            window.gc();
        }
        
        console.log('Forced garbage collection completed');
    }

    /**
     * Destroy memory manager
     */
    destroy() {
        // Clear all pools
        Object.values(this.pools).forEach(pool => pool.destroy());
        
        // Clear all caches
        Object.values(this.caches).forEach(cache => cache.clear());
        
        // Clear lazy loaders
        this.lazyLoaders.clear();
        
        // Clear intervals
        this.cleanupIntervals = {};
    }
}

/**
 * Object Pool for efficient object reuse
 */
class ObjectPool {
    constructor(type) {
        this.type = type;
        this.available = [];
        this.inUse = new Set();
        this.maxSize = 1000;
        this.constructor = null;
    }

    /**
     * Get object from pool
     */
    get(constructor) {
        if (this.available.length > 0) {
            const obj = this.available.pop();
            this.inUse.add(obj);
            return obj;
        }
        
        // Create new object if pool is empty
        const obj = constructor ? new constructor() : {};
        this.inUse.add(obj);
        return obj;
    }

    /**
     * Return object to pool
     */
    return(obj) {
        if (this.inUse.has(obj)) {
            this.inUse.delete(obj);
            
            if (this.available.length < this.maxSize) {
                // Reset object state
                this.resetObject(obj);
                this.available.push(obj);
            }
        }
    }

    /**
     * Reset object to initial state
     */
    resetObject(obj) {
        // Clear all properties
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                delete obj[key];
            }
        }
    }

    /**
     * Get current usage statistics
     */
    getUsageRatio() {
        const total = this.available.length + this.inUse.size;
        return total > 0 ? this.inUse.size / total : 0;
    }

    /**
     * Get pool size
     */
    get size() {
        return this.available.length + this.inUse.size;
    }

    /**
     * Get used count
     */
    get used() {
        return this.inUse.size;
    }

    /**
     * Get available count
     */
    get available() {
        return this.available.length;
    }

    /**
     * Optimize pool size
     */
    optimize() {
        // Remove excess objects if pool is too large
        const targetSize = Math.min(this.maxSize, this.inUse.size * 2);
        while (this.available.length > targetSize) {
            this.available.pop();
        }
    }

    /**
     * Cleanup pool
     */
    cleanup() {
        this.available.length = 0;
        this.inUse.clear();
    }

    /**
     * Destroy pool
     */
    destroy() {
        this.cleanup();
        this.constructor = null;
    }
}

/**
 * LRU Cache implementation
 */
class LRUCache {
    constructor(maxSize = 100) {
        this.maxSize = maxSize;
        this.cache = new Map();
        this.accessOrder = [];
        this.hits = 0;
        this.misses = 0;
    }

    /**
     * Get value from cache
     */
    get(key) {
        if (this.cache.has(key)) {
            // Move to end of access order
            this.moveToEnd(key);
            this.hits++;
            return this.cache.get(key);
        }
        
        this.misses++;
        return undefined;
    }

    /**
     * Set value in cache
     */
    set(key, value) {
        if (this.cache.has(key)) {
            // Update existing value
            this.cache.set(key, value);
            this.moveToEnd(key);
        } else {
            // Add new value
            if (this.cache.size >= this.maxSize) {
                this.evictLRU();
            }
            
            this.cache.set(key, value);
            this.accessOrder.push(key);
        }
    }

    /**
     * Delete value from cache
     */
    delete(key) {
        if (this.cache.has(key)) {
            this.cache.delete(key);
            const index = this.accessOrder.indexOf(key);
            if (index > -1) {
                this.accessOrder.splice(index, 1);
            }
        }
    }

    /**
     * Clear cache
     */
    clear() {
        this.cache.clear();
        this.accessOrder = [];
        this.hits = 0;
        this.misses = 0;
    }

    /**
     * Move key to end of access order
     */
    moveToEnd(key) {
        const index = this.accessOrder.indexOf(key);
        if (index > -1) {
            this.accessOrder.splice(index, 1);
            this.accessOrder.push(key);
        }
    }

    /**
     * Evict least recently used item
     */
    evictLRU() {
        if (this.accessOrder.length > 0) {
            const lruKey = this.accessOrder[0];
            this.delete(lruKey);
        }
    }

    /**
     * Evict percentage of cache
     */
    evict(percentage) {
        const count = Math.ceil(this.cache.size * percentage);
        for (let i = 0; i < count && this.cache.size > 0; i++) {
            this.evictLRU();
        }
    }

    /**
     * Cleanup expired entries
     */
    cleanup() {
        const now = Date.now();
        for (const [key, value] of this.cache.entries()) {
            if (value.timestamp && (now - value.timestamp) > value.ttl) {
                this.delete(key);
            }
        }
    }

    /**
     * Get hit rate
     */
    getHitRate() {
        const total = this.hits + this.misses;
        return total > 0 ? this.hits / total : 0;
    }

    /**
     * Get cache size
     */
    get size() {
        return this.cache.size;
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { MemoryManager, ObjectPool, LRUCache };
} else if (typeof window !== 'undefined') {
    window.MemoryManager = MemoryManager;
    window.ObjectPool = ObjectPool;
    window.LRUCache = LRUCache;
}
