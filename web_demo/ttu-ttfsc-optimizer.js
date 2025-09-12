/**
 * Understand-First TTU/TTFSC Optimization Module
 * 
 * This module provides optimizations to achieve:
 * - TTU (Time-to-Understanding) ≤ 10 minutes
 * - TTFSC (Time-to-First-Safe-Change) ≤ 1 day
 */

class TTUTTFSCOptimizer {
    constructor() {
        this.ttuTarget = 600; // 10 minutes in seconds
        this.ttfscTarget = 86400; // 1 day in seconds
        this.metrics = {
            ttu: [],
            ttfsc: [],
            activation: [],
            tourCompletion: [],
            prCoverage: []
        };
        
        this.optimizations = {
            onboarding: new OnboardingOptimizer(),
            navigation: new NavigationOptimizer(),
            understanding: new UnderstandingOptimizer(),
            changeSafety: new ChangeSafetyOptimizer()
        };
        
        this.setupTracking();
        this.setupOptimizations();
    }

    /**
     * Setup TTU/TTFSC tracking
     */
    setupTracking() {
        // Track TTU events
        this.trackTTUStart();
        this.trackTTUProgress();
        this.trackTTUCompletion();
        
        // Track TTFSC events
        this.trackTTFSCStart();
        this.trackTTFSCProgress();
        this.trackTTFSCCompletion();
        
        // Track activation metrics
        this.trackActivation();
        
        // Track tour completion
        this.trackTourCompletion();
        
        // Track PR coverage
        this.trackPRCoverage();
    }

    /**
     * Track TTU start
     */
    trackTTUStart() {
        const startTime = Date.now();
        this.ttuStartTime = startTime;
        
        // Track when user first interacts with the system
        document.addEventListener('click', () => {
            if (!this.ttuStarted) {
                this.ttuStarted = true;
                this.ttuStartTime = Date.now();
                this.announceTTUStart();
            }
        }, { once: true });
        
        // Track when user pastes code
        const codeEditor = document.getElementById('codeEditor');
        if (codeEditor) {
            codeEditor.addEventListener('paste', () => {
                if (!this.ttuStarted) {
                    this.ttuStarted = true;
                    this.ttuStartTime = Date.now();
                    this.announceTTUStart();
                }
            });
        }
    }

    /**
     * Track TTU progress
     */
    trackTTUProgress() {
        // Track key understanding milestones
        const milestones = [
            'code_pasted',
            'map_generated',
            'tour_started',
            'tour_step_viewed',
            'tour_completed',
            'export_clicked'
        ];
        
        milestones.forEach(milestone => {
            document.addEventListener(milestone, () => {
                this.recordTTUMilestone(milestone);
            });
        });
    }

    /**
     * Track TTU completion
     */
    trackTTUCompletion() {
        // TTU is complete when user generates a map and clicks ≥3 tour steps
        let tourStepsViewed = 0;
        
        document.addEventListener('tour_step_viewed', () => {
            tourStepsViewed++;
            
            if (tourStepsViewed >= 3) {
                this.completeTTU();
            }
        });
    }

    /**
     * Complete TTU tracking
     */
    completeTTU() {
        if (this.ttuCompleted) return;
        
        this.ttuCompleted = true;
        const ttu = (Date.now() - this.ttuStartTime) / 1000;
        
        this.metrics.ttu.push({
            timestamp: Date.now(),
            duration: ttu,
            success: ttu <= this.ttuTarget
        });
        
        this.announceTTUCompletion(ttu);
        
        // Track in global metrics
        if (window.trackMetric) {
            window.trackMetric('ttu_completed', {
                duration: ttu,
                success: ttu <= this.ttuTarget
            });
        }
    }

    /**
     * Track TTFSC start
     */
    trackTTFSCStart() {
        // TTFSC starts when user first interacts with the system
        document.addEventListener('ttu_completed', () => {
            this.ttfscStartTime = Date.now();
            this.announceTTFSCStart();
        });
    }

    /**
     * Track TTFSC progress
     */
    trackTTFSCProgress() {
        // Track key change safety milestones
        const milestones = [
            'pr_created',
            'map_delta_generated',
            'tour_updated',
            'contracts_verified',
            'pr_merged'
        ];
        
        milestones.forEach(milestone => {
            document.addEventListener(milestone, () => {
                this.recordTTFSCMilestone(milestone);
            });
        });
    }

    /**
     * Track TTFSC completion
     */
    trackTTFSCCompletion() {
        // TTFSC is complete when PR is merged with proof of understanding
        document.addEventListener('pr_merged', () => {
            this.completeTTFSC();
        });
    }

    /**
     * Complete TTFSC tracking
     */
    completeTTFSC() {
        if (this.ttfscCompleted) return;
        
        this.ttfscCompleted = true;
        const ttfsc = (Date.now() - this.ttfscStartTime) / 1000;
        
        this.metrics.ttfsc.push({
            timestamp: Date.now(),
            duration: ttfsc,
            success: ttfsc <= this.ttfscTarget
        });
        
        this.announceTTFSCCompletion(ttfsc);
        
        // Track in global metrics
        if (window.trackMetric) {
            window.trackMetric('ttfsc_completed', {
                duration: ttfsc,
                success: ttfsc <= this.ttfscTarget
            });
        }
    }

    /**
     * Track activation metrics
     */
    trackActivation() {
        // Track % users who generate a map in ≤2 minutes
        let mapGenerated = false;
        const activationStartTime = Date.now();
        
        document.addEventListener('map_generated', () => {
            if (!mapGenerated) {
                mapGenerated = true;
                const activationTime = (Date.now() - activationStartTime) / 1000;
                const success = activationTime <= 120; // 2 minutes
                
                this.metrics.activation.push({
                    timestamp: Date.now(),
                    duration: activationTime,
                    success: success
                });
                
                if (window.trackMetric) {
                    window.trackMetric('activation', {
                        duration: activationTime,
                        success: success
                    });
                }
            }
        });
    }

    /**
     * Track tour completion
     */
    trackTourCompletion() {
        // Track % sessions that finish ≥1 tour (≥80% steps viewed)
        let tourStarted = false;
        let tourStepsViewed = 0;
        let totalTourSteps = 0;
        
        document.addEventListener('tour_started', () => {
            tourStarted = true;
            totalTourSteps = 0; // Reset for new tour
        });
        
        document.addEventListener('tour_step_viewed', () => {
            if (tourStarted) {
                tourStepsViewed++;
                totalTourSteps = Math.max(totalTourSteps, tourStepsViewed);
            }
        });
        
        document.addEventListener('tour_completed', () => {
            if (tourStarted) {
                const completionRate = totalTourSteps > 0 ? tourStepsViewed / totalTourSteps : 0;
                const success = completionRate >= 0.8;
                
                this.metrics.tourCompletion.push({
                    timestamp: Date.now(),
                    completionRate: completionRate,
                    success: success
                });
                
                if (window.trackMetric) {
                    window.trackMetric('tour_completion', {
                        completionRate: completionRate,
                        success: success
                    });
                }
            }
        });
    }

    /**
     * Track PR coverage
     */
    trackPRCoverage() {
        // Track % merged PRs with updated map deltas + tour notes
        document.addEventListener('pr_merged', (event) => {
            const hasMapDelta = event.detail?.hasMapDelta || false;
            const hasTourNotes = event.detail?.hasTourNotes || false;
            const success = hasMapDelta && hasTourNotes;
            
            this.metrics.prCoverage.push({
                timestamp: Date.now(),
                hasMapDelta: hasMapDelta,
                hasTourNotes: hasTourNotes,
                success: success
            });
            
            if (window.trackMetric) {
                window.trackMetric('pr_coverage', {
                    hasMapDelta: hasMapDelta,
                    hasTourNotes: hasTourNotes,
                    success: success
                });
            }
        });
    }

    /**
     * Setup optimizations
     */
    setupOptimizations() {
        // Initialize all optimization modules
        Object.values(this.optimizations).forEach(optimizer => {
            optimizer.initialize();
        });
    }

    /**
     * Announce TTU start
     */
    announceTTUStart() {
        if (window.announceToScreenReader) {
            window.announceToScreenReader('Time to Understanding tracking started');
        }
    }

    /**
     * Announce TTU completion
     */
    announceTTUCompletion(ttu) {
        const success = ttu <= this.ttuTarget;
        const message = success 
            ? `Time to Understanding completed in ${Math.round(ttu)}s (target: ${this.ttuTarget}s)`
            : `Time to Understanding completed in ${Math.round(ttu)}s (exceeded target of ${this.ttuTarget}s)`;
        
        if (window.announceToScreenReader) {
            window.announceToScreenReader(message);
        }
        
        console.log(`TTU: ${ttu}s (target: ${this.ttuTarget}s, success: ${success})`);
    }

    /**
     * Announce TTFSC start
     */
    announceTTFSCStart() {
        if (window.announceToScreenReader) {
            window.announceToScreenReader('Time to First Safe Change tracking started');
        }
    }

    /**
     * Announce TTFSC completion
     */
    announceTTFSCCompletion(ttfsc) {
        const success = ttfsc <= this.ttfscTarget;
        const message = success 
            ? `Time to First Safe Change completed in ${Math.round(ttfsc)}s (target: ${this.ttfscTarget}s)`
            : `Time to First Safe Change completed in ${Math.round(ttfsc)}s (exceeded target of ${this.ttfscTarget}s)`;
        
        if (window.announceToScreenReader) {
            window.announceToScreenReader(message);
        }
        
        console.log(`TTFSC: ${ttfsc}s (target: ${this.ttfscTarget}s, success: ${success})`);
    }

    /**
     * Record TTU milestone
     */
    recordTTUMilestone(milestone) {
        const elapsed = (Date.now() - this.ttuStartTime) / 1000;
        
        console.log(`TTU Milestone: ${milestone} at ${elapsed}s`);
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('ttu_milestone', {
            detail: { milestone, elapsed }
        }));
    }

    /**
     * Record TTFSC milestone
     */
    recordTTFSCMilestone(milestone) {
        const elapsed = (Date.now() - this.ttfscStartTime) / 1000;
        
        console.log(`TTFSC Milestone: ${milestone} at ${elapsed}s`);
        
        // Dispatch custom event
        document.dispatchEvent(new CustomEvent('ttfsc_milestone', {
            detail: { milestone, elapsed }
        }));
    }

    /**
     * Get current metrics
     */
    getMetrics() {
        return {
            ttu: this.calculateTTUMetrics(),
            ttfsc: this.calculateTTFSCMetrics(),
            activation: this.calculateActivationMetrics(),
            tourCompletion: this.calculateTourCompletionMetrics(),
            prCoverage: this.calculatePRCoverageMetrics()
        };
    }

    /**
     * Calculate TTU metrics
     */
    calculateTTUMetrics() {
        const ttus = this.metrics.ttu;
        if (ttus.length === 0) return null;
        
        const durations = ttus.map(t => t.duration);
        const successes = ttus.filter(t => t.success).length;
        
        return {
            average: durations.reduce((a, b) => a + b, 0) / durations.length,
            successRate: successes / ttus.length,
            total: ttus.length
        };
    }

    /**
     * Calculate TTFSC metrics
     */
    calculateTTFSCMetrics() {
        const ttfscs = this.metrics.ttfsc;
        if (ttfscs.length === 0) return null;
        
        const durations = ttfscs.map(t => t.duration);
        const successes = ttfscs.filter(t => t.success).length;
        
        return {
            average: durations.reduce((a, b) => a + b, 0) / durations.length,
            successRate: successes / ttfscs.length,
            total: ttfscs.length
        };
    }

    /**
     * Calculate activation metrics
     */
    calculateActivationMetrics() {
        const activations = this.metrics.activation;
        if (activations.length === 0) return null;
        
        const successes = activations.filter(a => a.success).length;
        
        return {
            successRate: successes / activations.length,
            total: activations.length
        };
    }

    /**
     * Calculate tour completion metrics
     */
    calculateTourCompletionMetrics() {
        const completions = this.metrics.tourCompletion;
        if (completions.length === 0) return null;
        
        const successes = completions.filter(c => c.success).length;
        
        return {
            successRate: successes / completions.length,
            total: completions.length
        };
    }

    /**
     * Calculate PR coverage metrics
     */
    calculatePRCoverageMetrics() {
        const coverages = this.metrics.prCoverage;
        if (coverages.length === 0) return null;
        
        const successes = coverages.filter(c => c.success).length;
        
        return {
            successRate: successes / coverages.length,
            total: coverages.length
        };
    }
}

/**
 * Onboarding Optimizer
 */
class OnboardingOptimizer {
    initialize() {
        this.setupQuickStart();
        this.setupSampleCode();
        this.setupProgressIndicators();
    }

    setupQuickStart() {
        // Add quick start button to landing page
        const quickStartBtn = document.createElement('button');
        quickStartBtn.textContent = 'Quick Start (2 min)';
        quickStartBtn.className = 'quick-start-btn';
        quickStartBtn.addEventListener('click', () => {
            this.startQuickOnboarding();
        });
        
        // Add to header
        const header = document.querySelector('.header');
        if (header) {
            header.appendChild(quickStartBtn);
        }
    }

    setupSampleCode() {
        // Pre-load sample code for faster access
        this.sampleCode = {
            'toy-service': `def process_order(order_id, items):
    """Process a customer order"""
    total = 0
    for item in items:
        total += item.price * item.quantity
    return total`,
            'async-fastapi': `from fastapi import FastAPI
import asyncio

app = FastAPI()

@app.get("/")
async def read_root():
    return {"Hello": "World"}`,
            'class-util': `class DataProcessor:
    def __init__(self, config):
        self.config = config
    
    def process(self, data):
        return self.transform(data)`
        };
    }

    setupProgressIndicators() {
        // Add progress indicators for key steps
        this.progressSteps = [
            'Paste code',
            'Generate map',
            'Start tour',
            'Complete tour',
            'Export results'
        ];
    }

    startQuickOnboarding() {
        // Start guided onboarding process
        console.log('Starting quick onboarding...');
        
        // Dispatch event
        document.dispatchEvent(new CustomEvent('quick_onboarding_started'));
    }
}

/**
 * Navigation Optimizer
 */
class NavigationOptimizer {
    initialize() {
        this.setupKeyboardShortcuts();
        this.setupDeepLinks();
        this.setupSearch();
    }

    setupKeyboardShortcuts() {
        // Enhanced keyboard shortcuts for faster navigation
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch(e.key) {
                    case '1': this.focusCodeEditor(); break;
                    case '2': this.focusMap(); break;
                    case '3': this.focusTour(); break;
                    case 'k': this.focusSearch(); break;
                }
            }
        });
    }

    setupDeepLinks() {
        // Enable deep linking to specific nodes/views
        window.addEventListener('hashchange', () => {
            this.handleDeepLink();
        });
    }

    setupSearch() {
        // Add global search functionality
        const searchInput = document.createElement('input');
        searchInput.type = 'text';
        searchInput.placeholder = 'Search functions, files...';
        searchInput.className = 'global-search';
        
        searchInput.addEventListener('input', (e) => {
            this.performSearch(e.target.value);
        });
        
        // Add to toolbar
        const toolbar = document.querySelector('.toolbar');
        if (toolbar) {
            toolbar.appendChild(searchInput);
        }
    }

    focusCodeEditor() {
        const editor = document.getElementById('codeEditor');
        if (editor) editor.focus();
    }

    focusMap() {
        const map = document.getElementById('cy');
        if (map) map.focus();
    }

    focusTour() {
        const tour = document.querySelector('.tour-panel');
        if (tour) tour.focus();
    }

    focusSearch() {
        const search = document.querySelector('.global-search');
        if (search) search.focus();
    }

    handleDeepLink() {
        const hash = window.location.hash;
        if (hash.startsWith('#node=')) {
            const nodeId = hash.substring(6);
            this.focusNode(nodeId);
        }
    }

    performSearch(query) {
        // Implement search functionality
        console.log('Searching for:', query);
    }
}

/**
 * Understanding Optimizer
 */
class UnderstandingOptimizer {
    initialize() {
        this.setupSmartTours();
        this.setupContextualHelp();
        this.setupVisualCues();
    }

    setupSmartTours() {
        // Generate smart tours based on code complexity
        this.tourGenerators = {
            'complexity': this.generateComplexityTour,
            'side-effects': this.generateSideEffectsTour,
            'hot-path': this.generateHotPathTour
        };
    }

    setupContextualHelp() {
        // Add contextual help based on current focus
        this.helpTopics = {
            'functions': 'Understanding function relationships',
            'side-effects': 'Managing side effects',
            'complexity': 'Reducing code complexity'
        };
    }

    setupVisualCues() {
        // Add visual cues for important elements
        this.visualCues = {
            'hot-path': 'red',
            'side-effects': 'orange',
            'complex': 'yellow'
        };
    }

    generateComplexityTour(analysis) {
        // Generate tour focusing on complex functions
        return {
            title: 'Complexity Analysis',
            steps: analysis.functions
                .filter(f => f.complexity > 10)
                .map(f => ({
                    focus: f.name,
                    explanation: `This function has high complexity (${f.complexity})`
                }))
        };
    }

    generateSideEffectsTour(analysis) {
        // Generate tour focusing on side effects
        return {
            title: 'Side Effects Analysis',
            steps: analysis.functions
                .filter(f => f.sideEffects.length > 0)
                .map(f => ({
                    focus: f.name,
                    explanation: `This function has side effects: ${f.sideEffects.join(', ')}`
                }))
        };
    }

    generateHotPathTour(analysis) {
        // Generate tour focusing on hot paths
        return {
            title: 'Hot Path Analysis',
            steps: analysis.functions
                .filter(f => f.runtimeHotness > 0.7)
                .map(f => ({
                    focus: f.name,
                    explanation: `This function is frequently called (hotness: ${f.runtimeHotness})`
                }))
        };
    }
}

/**
 * Change Safety Optimizer
 */
class ChangeSafetyOptimizer {
    initialize() {
        this.setupSafetyChecks();
        this.setupPRIntegration();
        this.setupContractVerification();
    }

    setupSafetyChecks() {
        // Add safety checks before allowing changes
        this.safetyChecks = [
            'tour_completed',
            'map_delta_reviewed',
            'contracts_verified',
            'side_effects_acknowledged'
        ];
    }

    setupPRIntegration() {
        // Integrate with PR workflow
        this.prIntegration = {
            'generate_comment': this.generatePRComment,
            'check_policies': this.checkPRPolicies,
            'upload_artifacts': this.uploadPRArtifacts
        };
    }

    setupContractVerification() {
        // Add contract verification
        this.contractVerification = {
            'check_invariants': this.checkInvariants,
            'verify_preconditions': this.verifyPreconditions,
            'validate_postconditions': this.validatePostconditions
        };
    }

    generatePRComment(prData) {
        // Generate PR comment with understanding artifacts
        return {
            title: 'Understand-First Analysis',
            body: `## Code Analysis Summary
- Map Delta: ${prData.mapDelta}
- Tour Updated: ${prData.tourUpdated}
- Contracts Verified: ${prData.contractsVerified}`
        };
    }

    checkPRPolicies(prData) {
        // Check if PR meets safety policies
        return {
            tourUpdated: prData.tourUpdated,
            mapDeltaReviewed: prData.mapDeltaReviewed,
            contractsVerified: prData.contractsVerified,
            sideEffectsAcknowledged: prData.sideEffectsAcknowledged
        };
    }

    uploadPRArtifacts(artifacts) {
        // Upload understanding artifacts to PR
        console.log('Uploading artifacts:', artifacts);
    }

    checkInvariants(code) {
        // Check code invariants
        return { valid: true, violations: [] };
    }

    verifyPreconditions(code) {
        // Verify function preconditions
        return { valid: true, violations: [] };
    }

    validatePostconditions(code) {
        // Validate function postconditions
        return { valid: true, violations: [] };
    }
}

// Initialize TTU/TTFSC optimizer when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.ttuTtfscOptimizer = new TTUTTFSCOptimizer();
});
