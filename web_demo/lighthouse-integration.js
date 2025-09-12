/**
 * Google Lighthouse Integration for Understand-First
 * 
 * This module provides automated performance monitoring using Google Lighthouse
 * to ensure compliance with performance guardrails and accessibility standards.
 */

class LighthouseIntegration {
    constructor() {
        this.lighthouse = null;
        this.config = {
            performance: {
                target: 90,
                thresholds: {
                    'first-contentful-paint': 2000,
                    'largest-contentful-paint': 2500,
                    'cumulative-layout-shift': 0.1,
                    'total-blocking-time': 300,
                    'speed-index': 3000
                }
            },
            accessibility: {
                target: 95,
                thresholds: {
                    'color-contrast': 4.5,
                    'keyboard-navigation': 90,
                    'screen-reader': 90
                }
            },
            bestPractices: {
                target: 90
            },
            seo: {
                target: 90
            }
        };
        
        this.metrics = {
            performance: [],
            accessibility: [],
            bestPractices: [],
            seo: []
        };
        
        this.setupLighthouse();
    }

    /**
     * Setup Lighthouse integration
     */
    async setupLighthouse() {
        try {
            // Load Lighthouse dynamically
            if (typeof window !== 'undefined' && window.lighthouse) {
                this.lighthouse = window.lighthouse;
            } else {
                // Load from CDN if not available
                await this.loadLighthouseFromCDN();
            }
            
            this.setupPeriodicAudits();
            this.setupPerformanceAlerts();
            
        } catch (error) {
            console.warn('Lighthouse integration failed:', error);
        }
    }

    /**
     * Load Lighthouse from CDN
     */
    async loadLighthouseFromCDN() {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://unpkg.com/lighthouse@10.4.0/dist/lighthouse.min.js';
            script.onload = () => {
                this.lighthouse = window.lighthouse;
                resolve();
            };
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    /**
     * Setup periodic audits
     */
    setupPeriodicAudits() {
        // Run audit every 5 minutes
        setInterval(() => {
            this.runAudit();
        }, 5 * 60 * 1000);
        
        // Run audit on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                setTimeout(() => this.runAudit(), 2000);
            });
        } else {
            setTimeout(() => this.runAudit(), 2000);
        }
    }

    /**
     * Setup performance alerts
     */
    setupPerformanceAlerts() {
        // Listen for performance alerts from our custom monitoring
        document.addEventListener('performanceAlert', (event) => {
            this.handlePerformanceAlert(event.detail);
        });
        
        // Listen for accessibility issues
        document.addEventListener('accessibilityIssue', (event) => {
            this.handleAccessibilityIssue(event.detail);
        });
    }

    /**
     * Run Lighthouse audit
     */
    async runAudit() {
        if (!this.lighthouse) {
            console.warn('Lighthouse not available for audit');
            return;
        }

        try {
            const url = window.location.href;
            const options = {
                onlyCategories: ['performance', 'accessibility', 'best-practices', 'seo'],
                disableStorageReset: true,
                throttlingMethod: 'devtools',
                throttling: {
                    rttMs: 40,
                    throughputKbps: 10240,
                    cpuSlowdownMultiplier: 1,
                    requestLatencyMs: 0,
                    downloadThroughputKbps: 0,
                    uploadThroughputKbps: 0
                }
            };

            const results = await this.lighthouse(url, options);
            this.processAuditResults(results);
            
        } catch (error) {
            console.error('Lighthouse audit failed:', error);
        }
    }

    /**
     * Process audit results
     */
    processAuditResults(results) {
        const categories = results.lhr.categories;
        
        // Process performance metrics
        this.processPerformanceMetrics(categories.performance);
        
        // Process accessibility metrics
        this.processAccessibilityMetrics(categories.accessibility);
        
        // Process best practices metrics
        this.processBestPracticesMetrics(categories['best-practices']);
        
        // Process SEO metrics
        this.processSEOMetrics(categories.seo);
        
        // Update dashboard
        this.updateLighthouseDashboard(results);
        
        // Check thresholds
        this.checkThresholds(results);
    }

    /**
     * Process performance metrics
     */
    processPerformanceMetrics(performance) {
        const score = Math.round(performance.score * 100);
        const audits = performance.auditRefs;
        
        const metrics = {
            score: score,
            firstContentfulPaint: this.getAuditValue(audits, 'first-contentful-paint'),
            largestContentfulPaint: this.getAuditValue(audits, 'largest-contentful-paint'),
            cumulativeLayoutShift: this.getAuditValue(audits, 'cumulative-layout-shift'),
            totalBlockingTime: this.getAuditValue(audits, 'total-blocking-time'),
            speedIndex: this.getAuditValue(audits, 'speed-index')
        };
        
        this.metrics.performance.push({
            timestamp: Date.now(),
            ...metrics
        });
        
        // Keep only last 10 measurements
        if (this.metrics.performance.length > 10) {
            this.metrics.performance.shift();
        }
        
        // Dispatch performance update event
        document.dispatchEvent(new CustomEvent('lighthousePerformanceUpdate', {
            detail: metrics
        }));
    }

    /**
     * Process accessibility metrics
     */
    processAccessibilityMetrics(accessibility) {
        const score = Math.round(accessibility.score * 100);
        const audits = accessibility.auditRefs;
        
        const metrics = {
            score: score,
            colorContrast: this.getAuditValue(audits, 'color-contrast'),
            keyboardNavigation: this.getAuditValue(audits, 'keyboard-navigation'),
            screenReader: this.getAuditValue(audits, 'screen-reader')
        };
        
        this.metrics.accessibility.push({
            timestamp: Date.now(),
            ...metrics
        });
        
        // Keep only last 10 measurements
        if (this.metrics.accessibility.length > 10) {
            this.metrics.accessibility.shift();
        }
        
        // Dispatch accessibility update event
        document.dispatchEvent(new CustomEvent('lighthouseAccessibilityUpdate', {
            detail: metrics
        }));
    }

    /**
     * Process best practices metrics
     */
    processBestPracticesMetrics(bestPractices) {
        const score = Math.round(bestPractices.score * 100);
        
        this.metrics.bestPractices.push({
            timestamp: Date.now(),
            score: score
        });
        
        // Keep only last 10 measurements
        if (this.metrics.bestPractices.length > 10) {
            this.metrics.bestPractices.shift();
        }
    }

    /**
     * Process SEO metrics
     */
    processSEOMetrics(seo) {
        const score = Math.round(seo.score * 100);
        
        this.metrics.seo.push({
            timestamp: Date.now(),
            score: score
        });
        
        // Keep only last 10 measurements
        if (this.metrics.seo.length > 10) {
            this.metrics.seo.shift();
        }
    }

    /**
     * Get audit value from audit references
     */
    getAuditValue(audits, auditId) {
        const audit = audits.find(a => a.id === auditId);
        return audit ? audit.result.numericValue : null;
    }

    /**
     * Update Lighthouse dashboard
     */
    updateLighthouseDashboard(results) {
        // Update performance dashboard with Lighthouse metrics
        const performance = results.lhr.categories.performance;
        const accessibility = results.lhr.categories.accessibility;
        
        // Update UI latency based on FCP
        const fcp = this.getAuditValue(performance.auditRefs, 'first-contentful-paint');
        if (fcp) {
            updateGuardrailValue('ui-latency', fcp, fcp < 100 ? 'success' : 'critical');
        }
        
        // Update map render based on LCP
        const lcp = this.getAuditValue(performance.auditRefs, 'largest-contentful-paint');
        if (lcp) {
            updateGuardrailValue('map-render', lcp, lcp < 1500 ? 'success' : 'critical');
        }
        
        // Update frame rate based on TBT
        const tbt = this.getAuditValue(performance.auditRefs, 'total-blocking-time');
        if (tbt) {
            const fps = Math.max(0, 60 - (tbt / 16.67)); // Rough FPS calculation
            updateGuardrailValue('frame-rate', fps, fps > 45 ? 'success' : 'critical');
        }
    }

    /**
     * Check thresholds and trigger alerts
     */
    checkThresholds(results) {
        const performance = results.lhr.categories.performance;
        const accessibility = results.lhr.categories.accessibility;
        
        // Check performance thresholds
        if (performance.score < this.config.performance.target / 100) {
            this.triggerAlert('performance', 'Performance score below target', {
                score: Math.round(performance.score * 100),
                target: this.config.performance.target
            });
        }
        
        // Check accessibility thresholds
        if (accessibility.score < this.config.accessibility.target / 100) {
            this.triggerAlert('accessibility', 'Accessibility score below target', {
                score: Math.round(accessibility.score * 100),
                target: this.config.accessibility.target
            });
        }
    }

    /**
     * Handle performance alert
     */
    handlePerformanceAlert(alert) {
        // Log performance alert for Lighthouse correlation
        console.log('Performance alert received:', alert);
        
        // Trigger additional Lighthouse audit if critical
        if (alert.type.includes('critical')) {
            setTimeout(() => this.runAudit(), 1000);
        }
    }

    /**
     * Handle accessibility issue
     */
    handleAccessibilityIssue(issue) {
        // Log accessibility issue for Lighthouse correlation
        console.log('Accessibility issue received:', issue);
        
        // Trigger additional Lighthouse audit
        setTimeout(() => this.runAudit(), 1000);
    }

    /**
     * Trigger alert
     */
    triggerAlert(type, message, data) {
        const alert = {
            type: type,
            message: message,
            data: data,
            timestamp: Date.now()
        };
        
        console.warn(`Lighthouse ${type} alert:`, alert);
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('lighthouseAlert', {
            detail: alert
        }));
        
        // Track in metrics
        if (window.trackMetric) {
            window.trackMetric('lighthouse_alert', alert);
        }
    }

    /**
     * Get current metrics
     */
    getMetrics() {
        return {
            performance: this.calculateAverageMetrics(this.metrics.performance),
            accessibility: this.calculateAverageMetrics(this.metrics.accessibility),
            bestPractices: this.calculateAverageMetrics(this.metrics.bestPractices),
            seo: this.calculateAverageMetrics(this.metrics.seo)
        };
    }

    /**
     * Calculate average metrics
     */
    calculateAverageMetrics(metrics) {
        if (metrics.length === 0) return null;
        
        const latest = metrics[metrics.length - 1];
        const average = metrics.reduce((acc, metric) => {
            Object.keys(metric).forEach(key => {
                if (typeof metric[key] === 'number') {
                    acc[key] = (acc[key] || 0) + metric[key];
                }
            });
            return acc;
        }, {});
        
        Object.keys(average).forEach(key => {
            average[key] = average[key] / metrics.length;
        });
        
        return {
            latest: latest,
            average: average,
            count: metrics.length
        };
    }

    /**
     * Run manual audit
     */
    async runManualAudit() {
        console.log('Running manual Lighthouse audit...');
        await this.runAudit();
    }

    /**
     * Export metrics
     */
    exportMetrics() {
        const data = {
            timestamp: Date.now(),
            metrics: this.getMetrics(),
            raw: this.metrics
        };
        
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `lighthouse-metrics-${Date.now()}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
    }
}

// Initialize Lighthouse integration when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.lighthouseIntegration = new LighthouseIntegration();
});

// Export for global access
window.LighthouseIntegration = LighthouseIntegration;
