/**
 * Understand-First Performance Optimization Module
 * 
 * This module provides comprehensive performance optimizations for large graphs,
 * including Web Workers, virtualization, incremental updates, and memory management.
 */

class PerformanceOptimizer {
    constructor(cyInstance) {
        this.cy = cyInstance;
        this.worker = null;
        this.virtualization = {
            enabled: false,
            viewport: null,
            renderedNodes: new Set(),
            nodeCache: new Map(),
            edgeCache: new Map()
        };
        this.memory = {
            maxNodes: 5000,
            maxEdges: 10000,
            gcThreshold: 0.8,
            lastGC: Date.now()
        };
        this.rendering = {
            frameRate: 60,
            lastFrame: 0,
            frameSkip: 0,
            adaptiveQuality: true
        };
        this.caching = {
            layoutCache: new Map(),
            styleCache: new Map(),
            searchCache: new Map()
        };
        
        this.initializeWorker();
        this.setupPerformanceMonitoring();
        this.setupAdaptiveRendering();
    }

    /**
     * Initialize Web Worker for background processing
     */
    initializeWorker() {
        if (typeof Worker !== 'undefined') {
            const workerCode = this.createWorkerCode();
            const blob = new Blob([workerCode], { type: 'application/javascript' });
            this.worker = new Worker(URL.createObjectURL(blob));
            
            this.worker.onmessage = (event) => {
                this.handleWorkerMessage(event.data);
            };
            
            this.worker.onerror = (error) => {
                console.warn('Web Worker error:', error);
                this.worker = null;
            };
        }
    }

    /**
     * Create Web Worker code for background processing
     */
    createWorkerCode() {
        return `
            // Web Worker for Understand-First performance optimization
            self.onmessage = function(e) {
                const { type, data } = e.data;
                
                switch(type) {
                    case 'CALCULATE_LAYOUT':
                        const layout = calculateLayout(data.nodes, data.edges, data.options);
                        self.postMessage({ type: 'LAYOUT_CALCULATED', data: layout });
                        break;
                        
                    case 'FILTER_GRAPH':
                        const filtered = filterGraph(data.graph, data.filters);
                        self.postMessage({ type: 'GRAPH_FILTERED', data: filtered });
                        break;
                        
                    case 'CALCULATE_METRICS':
                        const metrics = calculateMetrics(data.nodes, data.edges);
                        self.postMessage({ type: 'METRICS_CALCULATED', data: metrics });
                        break;
                        
                    case 'OPTIMIZE_STYLES':
                        const styles = optimizeStyles(data.nodes, data.edges, data.zoom);
                        self.postMessage({ type: 'STYLES_OPTIMIZED', data: styles });
                        break;
                }
            };
            
            function calculateLayout(nodes, edges, options) {
                // Implement layout calculation in worker
                // This would use a layout algorithm like force-directed or hierarchical
                const positions = {};
                const width = options.width || 800;
                const height = options.height || 600;
                
                // Simple grid layout for demonstration
                const cols = Math.ceil(Math.sqrt(nodes.length));
                nodes.forEach((node, index) => {
                    const row = Math.floor(index / cols);
                    const col = index % cols;
                    positions[node.id] = {
                        x: (col / cols) * width,
                        y: (row / cols) * height
                    };
                });
                
                return { positions, nodes, edges };
            }
            
            function filterGraph(graph, filters) {
                const { nodes, edges } = graph;
                let filteredNodes = [...nodes];
                let filteredEdges = [...edges];
                
                if (filters.complexity) {
                    filteredNodes = filteredNodes.filter(node => 
                        node.data.complexity >= filters.complexity.min &&
                        node.data.complexity <= filters.complexity.max
                    );
                }
                
                if (filters.sideEffects) {
                    filteredNodes = filteredNodes.filter(node => 
                        node.data.sideEffects && node.data.sideEffects.length > 0
                    );
                }
                
                // Filter edges to only include those between filtered nodes
                const filteredNodeIds = new Set(filteredNodes.map(n => n.id));
                filteredEdges = filteredEdges.filter(edge => 
                    filteredNodeIds.has(edge.data.source) && 
                    filteredNodeIds.has(edge.data.target)
                );
                
                return { nodes: filteredNodes, edges: filteredEdges };
            }
            
            function calculateMetrics(nodes, edges) {
                const metrics = {
                    totalNodes: nodes.length,
                    totalEdges: edges.length,
                    avgComplexity: 0,
                    maxComplexity: 0,
                    sideEffectCount: 0,
                    hotPathCount: 0
                };
                
                let totalComplexity = 0;
                nodes.forEach(node => {
                    const complexity = node.data.complexity || 0;
                    totalComplexity += complexity;
                    metrics.maxComplexity = Math.max(metrics.maxComplexity, complexity);
                    
                    if (node.data.sideEffects && node.data.sideEffects.length > 0) {
                        metrics.sideEffectCount++;
                    }
                    
                    if (node.data.runtimeHotness > 0.7) {
                        metrics.hotPathCount++;
                    }
                });
                
                metrics.avgComplexity = nodes.length > 0 ? totalComplexity / nodes.length : 0;
                
                return metrics;
            }
            
            function optimizeStyles(nodes, edges, zoom) {
                const styles = {
                    nodes: {},
                    edges: {}
                };
                
                // Optimize node styles based on zoom level
                nodes.forEach(node => {
                    const nodeId = node.id;
                    if (zoom < 0.3) {
                        // Very low zoom - minimal rendering
                        styles.nodes[nodeId] = {
                            'width': '8px',
                            'height': '8px',
                            'font-size': '0px',
                            'label': ''
                        };
                    } else if (zoom < 0.6) {
                        // Low zoom - small nodes
                        styles.nodes[nodeId] = {
                            'width': '16px',
                            'height': '16px',
                            'font-size': '8px',
                            'label': node.data.label.length > 10 ? node.data.label.substring(0, 10) + '...' : node.data.label
                        };
                    } else {
                        // Normal zoom - full rendering
                        styles.nodes[nodeId] = {
                            'width': '24px',
                            'height': '24px',
                            'font-size': '12px',
                            'label': node.data.label
                        };
                    }
                });
                
                // Optimize edge styles
                edges.forEach(edge => {
                    const edgeId = edge.id;
                    if (zoom < 0.4) {
                        styles.edges[edgeId] = {
                            'line-width': '1px',
                            'label': ''
                        };
                    } else {
                        styles.edges[edgeId] = {
                            'line-width': '2px',
                            'label': edge.data.label || ''
                        };
                    }
                });
                
                return styles;
            }
        `;
    }

    /**
     * Handle messages from Web Worker
     */
    handleWorkerMessage(data) {
        switch(data.type) {
            case 'LAYOUT_CALCULATED':
                this.applyLayout(data.data);
                break;
            case 'GRAPH_FILTERED':
                this.applyFilteredGraph(data.data);
                break;
            case 'METRICS_CALCULATED':
                this.updateMetrics(data.data);
                break;
            case 'STYLES_OPTIMIZED':
                this.applyOptimizedStyles(data.data);
                break;
        }
    }

    /**
     * Setup performance monitoring with guardrails
     */
    setupPerformanceMonitoring() {
        this.performanceMetrics = {
            frameTime: [],
            memoryUsage: [],
            nodeCount: [],
            edgeCount: [],
            renderTime: [],
            uiLatency: [],
            mapRenderTime: []
        };

        // Performance guardrails
        this.guardrails = {
            uiLatency: {
                target: 100, // ms
                warning: 80,
                critical: 100
            },
            mapRender: {
                target: 1500, // ms for 5k nodes
                warning: 1200,
                critical: 1500
            },
            frameRate: {
                target: 60,
                warning: 45,
                critical: 30
            }
        };

        // Monitor frame rate
        this.monitorFrameRate();
        
        // Monitor memory usage
        this.monitorMemoryUsage();
        
        // Monitor graph size
        this.monitorGraphSize();
        
        // Monitor UI latency
        this.monitorUILatency();
        
        // Monitor map render time
        this.monitorMapRenderTime();
    }

    /**
     * Monitor frame rate performance
     */
    monitorFrameRate() {
        let lastTime = performance.now();
        let frameCount = 0;
        
        const measureFrameRate = () => {
            const currentTime = performance.now();
            const deltaTime = currentTime - lastTime;
            
            frameCount++;
            if (frameCount % 60 === 0) {
                const fps = Math.round(1000 / (deltaTime / frameCount));
                this.performanceMetrics.frameTime.push({
                    timestamp: currentTime,
                    fps: fps,
                    frameTime: deltaTime / frameCount
                });
                
                // Keep only last 100 measurements
                if (this.performanceMetrics.frameTime.length > 100) {
                    this.performanceMetrics.frameTime.shift();
                }
                
                // Adjust rendering quality based on performance
                this.adjustRenderingQuality(fps);
            }
            
            lastTime = currentTime;
            frameCount = 0;
            
            requestAnimationFrame(measureFrameRate);
        };
        
        requestAnimationFrame(measureFrameRate);
    }

    /**
     * Monitor memory usage
     */
    monitorMemoryUsage() {
        setInterval(() => {
            if (performance.memory) {
                const memoryInfo = {
                    timestamp: Date.now(),
                    used: performance.memory.usedJSHeapSize,
                    total: performance.memory.totalJSHeapSize,
                    limit: performance.memory.jsHeapSizeLimit
                };
                
                this.performanceMetrics.memoryUsage.push(memoryInfo);
                
                // Keep only last 100 measurements
                if (this.performanceMetrics.memoryUsage.length > 100) {
                    this.performanceMetrics.memoryUsage.shift();
                }
                
                // Trigger garbage collection if needed
                this.checkMemoryPressure();
            }
        }, 5000); // Check every 5 seconds
    }

    /**
     * Monitor graph size changes
     */
    monitorGraphSize() {
        if (this.cy) {
            this.cy.on('add remove', () => {
                const nodeCount = this.cy.nodes().length;
                const edgeCount = this.cy.edges().length;
                
                this.performanceMetrics.nodeCount.push({
                    timestamp: Date.now(),
                    count: nodeCount
                });
                
                this.performanceMetrics.edgeCount.push({
                    timestamp: Date.now(),
                    count: edgeCount
                });
                
                // Enable virtualization for large graphs
                if (nodeCount > 1000 && !this.virtualization.enabled) {
                    this.enableVirtualization();
                } else if (nodeCount <= 500 && this.virtualization.enabled) {
                    this.disableVirtualization();
                }
                
                // Trigger performance optimizations
                this.optimizeForSize(nodeCount, edgeCount);
            });
        }
    }

    /**
     * Monitor UI latency
     */
    monitorUILatency() {
        // Track UI interaction latency
        const originalAddEventListener = EventTarget.prototype.addEventListener;
        const self = this;
        
        EventTarget.prototype.addEventListener = function(type, listener, options) {
            if (type === 'click' || type === 'keydown' || type === 'keyup') {
                const wrappedListener = function(event) {
                    const startTime = performance.now();
                    const result = listener.call(this, event);
                    const latency = performance.now() - startTime;
                    
                    self.performanceMetrics.uiLatency.push({
                        timestamp: Date.now(),
                        latency: latency,
                        type: type
                    });
                    
                    // Check guardrails
                    self.checkUILatencyGuardrail(latency);
                    
                    // Keep only last 100 measurements
                    if (self.performanceMetrics.uiLatency.length > 100) {
                        self.performanceMetrics.uiLatency.shift();
                    }
                    
                    return result;
                };
                return originalAddEventListener.call(this, type, wrappedListener, options);
            }
            return originalAddEventListener.call(this, type, listener, options);
        };
    }

    /**
     * Monitor map render time
     */
    monitorMapRenderTime() {
        // Override render methods to track timing
        if (this.cy) {
            const originalRender = this.cy.render;
            const self = this;
            
            this.cy.render = function() {
                const startTime = performance.now();
                const result = originalRender.call(this);
                const renderTime = performance.now() - startTime;
                
                self.performanceMetrics.mapRenderTime.push({
                    timestamp: Date.now(),
                    renderTime: renderTime,
                    nodeCount: this.nodes().length,
                    edgeCount: this.edges().length
                });
                
                // Check guardrails
                self.checkMapRenderGuardrail(renderTime, this.nodes().length);
                
                // Keep only last 50 measurements
                if (self.performanceMetrics.mapRenderTime.length > 50) {
                    self.performanceMetrics.mapRenderTime.shift();
                }
                
                return result;
            };
        }
    }

    /**
     * Check UI latency guardrails
     */
    checkUILatencyGuardrail(latency) {
        const guardrail = this.guardrails.uiLatency;
        
        if (latency > guardrail.critical) {
            console.warn(`UI Latency CRITICAL: ${latency}ms exceeds ${guardrail.critical}ms target`);
            this.triggerPerformanceAlert('ui_latency_critical', latency);
        } else if (latency > guardrail.warning) {
            console.warn(`UI Latency WARNING: ${latency}ms exceeds ${guardrail.warning}ms warning threshold`);
        }
    }

    /**
     * Check map render guardrails
     */
    checkMapRenderGuardrail(renderTime, nodeCount) {
        const guardrail = this.guardrails.mapRender;
        
        // Scale target based on node count (5k nodes = 1.5s target)
        const scaledTarget = guardrail.target * (nodeCount / 5000);
        const scaledWarning = guardrail.warning * (nodeCount / 5000);
        
        if (renderTime > scaledTarget) {
            console.warn(`Map Render CRITICAL: ${renderTime}ms exceeds ${scaledTarget}ms target for ${nodeCount} nodes`);
            this.triggerPerformanceAlert('map_render_critical', renderTime, { nodeCount, scaledTarget });
        } else if (renderTime > scaledWarning) {
            console.warn(`Map Render WARNING: ${renderTime}ms exceeds ${scaledWarning}ms warning threshold for ${nodeCount} nodes`);
        }
    }

    /**
     * Trigger performance alert
     */
    triggerPerformanceAlert(type, value, context = {}) {
        // Dispatch custom event for performance alerts
        const event = new CustomEvent('performanceAlert', {
            detail: {
                type: type,
                value: value,
                context: context,
                timestamp: Date.now()
            }
        });
        
        document.dispatchEvent(event);
        
        // Track in metrics
        if (window.trackMetric) {
            window.trackMetric('performance_alert', {
                type: type,
                value: value,
                context: context
            });
        }
    }

    /**
     * Enable virtualization for large graphs
     */
    enableVirtualization() {
        this.virtualization.enabled = true;
        console.log('Enabling graph virtualization for performance');
        
        // Setup viewport-based rendering
        this.setupViewportRendering();
        
        // Setup node pooling
        this.setupNodePooling();
        
        // Setup edge culling
        this.setupEdgeCulling();
    }

    /**
     * Disable virtualization
     */
    disableVirtualization() {
        this.virtualization.enabled = false;
        console.log('Disabling graph virtualization');
        
        // Restore all nodes and edges
        this.cy.nodes().style('display', 'element');
        this.cy.edges().style('display', 'element');
        
        // Clear caches
        this.virtualization.nodeCache.clear();
        this.virtualization.edgeCache.clear();
    }

    /**
     * Setup viewport-based rendering
     */
    setupViewportRendering() {
        if (!this.cy) return;
        
        const updateViewport = this.debounce(() => {
            const viewport = this.cy.extent();
            const zoom = this.cy.zoom();
            
            this.virtualization.viewport = {
                x1: viewport.x1,
                y1: viewport.y1,
                x2: viewport.x2,
                y2: viewport.y2,
                zoom: zoom
            };
            
            this.renderViewportNodes();
        }, 16); // ~60fps
        
        this.cy.on('viewport', updateViewport);
        this.cy.on('zoom', updateViewport);
    }

    /**
     * Render only nodes in viewport
     */
    renderViewportNodes() {
        if (!this.virtualization.enabled || !this.virtualization.viewport) return;
        
        const viewport = this.virtualization.viewport;
        const nodes = this.cy.nodes();
        
        // Hide all nodes first
        nodes.style('display', 'none');
        
        // Show only nodes in viewport
        const nodesInViewport = nodes.filter(node => {
            const pos = node.position();
            return pos.x >= viewport.x1 && pos.x <= viewport.x2 && 
                   pos.y >= viewport.y1 && pos.y <= viewport.y2;
        });
        
        nodesInViewport.style('display', 'element');
        
        // Update rendered nodes set
        this.virtualization.renderedNodes.clear();
        nodesInViewport.forEach(node => {
            this.virtualization.renderedNodes.add(node.id());
        });
        
        // Render connected edges
        this.renderConnectedEdges(nodesInViewport);
    }

    /**
     * Render edges connected to visible nodes
     */
    renderConnectedEdges(visibleNodes) {
        if (!this.virtualization.enabled) return;
        
        const edges = this.cy.edges();
        
        // Hide all edges first
        edges.style('display', 'none');
        
        // Show edges connected to visible nodes
        const visibleNodeIds = new Set(visibleNodes.map(node => node.id()));
        const connectedEdges = edges.filter(edge => {
            const source = edge.source().id();
            const target = edge.target().id();
            return visibleNodeIds.has(source) && visibleNodeIds.has(target);
        });
        
        connectedEdges.style('display', 'element');
    }

    /**
     * Setup node pooling for efficient rendering
     */
    setupNodePooling() {
        // Pre-create node elements for reuse
        this.nodePool = {
            available: [],
            inUse: new Set()
        };
        
        // Initialize pool with some nodes
        for (let i = 0; i < 100; i++) {
            this.nodePool.available.push(document.createElement('div'));
        }
    }

    /**
     * Setup edge culling for performance
     */
    setupEdgeCulling() {
        if (!this.cy) return;
        
        const cullEdges = this.debounce(() => {
            const zoom = this.cy.zoom();
            const edges = this.cy.edges();
            
            if (zoom < 0.3) {
                // Hide all edges at very low zoom
                edges.style('display', 'none');
            } else if (zoom < 0.6) {
                // Show only high-importance edges
                edges.style('display', 'none');
                edges.filter('[importance > 0.7]').style('display', 'element');
            } else {
                // Show all edges
                edges.style('display', 'element');
            }
        }, 16);
        
        this.cy.on('zoom', cullEdges);
    }

    /**
     * Setup adaptive rendering quality
     */
    setupAdaptiveRendering() {
        this.adaptiveQuality = {
            enabled: true,
            targetFPS: 60,
            minFPS: 30,
            currentLevel: 1,
            levels: [
                { name: 'high', nodeSize: 24, labelSize: 12, edgeWidth: 2 },
                { name: 'medium', nodeSize: 20, labelSize: 10, edgeWidth: 1.5 },
                { name: 'low', nodeSize: 16, labelSize: 8, edgeWidth: 1 },
                { name: 'minimal', nodeSize: 12, labelSize: 0, edgeWidth: 0.5 }
            ]
        };
    }

    /**
     * Adjust rendering quality based on performance
     */
    adjustRenderingQuality(fps) {
        if (!this.adaptiveQuality.enabled) return;
        
        const targetFPS = this.adaptiveQuality.targetFPS;
        const minFPS = this.adaptiveQuality.minFPS;
        
        if (fps < minFPS && this.adaptiveQuality.currentLevel < this.adaptiveQuality.levels.length - 1) {
            // Decrease quality
            this.adaptiveQuality.currentLevel++;
            this.applyQualityLevel();
        } else if (fps > targetFPS && this.adaptiveQuality.currentLevel > 0) {
            // Increase quality
            this.adaptiveQuality.currentLevel--;
            this.applyQualityLevel();
        }
    }

    /**
     * Apply current quality level
     */
    applyQualityLevel() {
        const level = this.adaptiveQuality.levels[this.adaptiveQuality.currentLevel];
        
        if (this.cy) {
            this.cy.style()
                .selector('node')
                .style('width', level.nodeSize + 'px')
                .style('height', level.nodeSize + 'px')
                .style('font-size', level.labelSize + 'px')
                .style('label', level.labelSize > 0 ? 'data(label)' : '')
                .selector('edge')
                .style('width', level.edgeWidth + 'px')
                .update();
        }
    }

    /**
     * Optimize graph for current size
     */
    optimizeForSize(nodeCount, edgeCount) {
        // Adjust rendering strategy based on graph size
        if (nodeCount > 2000) {
            // Very large graph - use minimal rendering
            this.setMinimalRendering();
        } else if (nodeCount > 1000) {
            // Large graph - use reduced rendering
            this.setReducedRendering();
        } else {
            // Normal graph - use full rendering
            this.setFullRendering();
        }
        
        // Trigger layout optimization
        this.optimizeLayout();
    }

    /**
     * Set minimal rendering for very large graphs
     */
    setMinimalRendering() {
        if (!this.cy) return;
        
        this.cy.style()
            .selector('node')
            .style('width', '8px')
            .style('height', '8px')
            .style('font-size', '0px')
            .style('label', '')
            .selector('edge')
            .style('width', '1px')
            .style('label', '')
            .update();
    }

    /**
     * Set reduced rendering for large graphs
     */
    setReducedRendering() {
        if (!this.cy) return;
        
        this.cy.style()
            .selector('node')
            .style('width', '16px')
            .style('height', '16px')
            .style('font-size', '8px')
            .style('label', 'data(label)')
            .selector('edge')
            .style('width', '1.5px')
            .style('label', '')
            .update();
    }

    /**
     * Set full rendering for normal graphs
     */
    setFullRendering() {
        if (!this.cy) return;
        
        this.cy.style()
            .selector('node')
            .style('width', '24px')
            .style('height', '24px')
            .style('font-size', '12px')
            .style('label', 'data(label)')
            .selector('edge')
            .style('width', '2px')
            .style('label', 'data(label)')
            .update();
    }

    /**
     * Optimize layout algorithm based on graph size
     */
    optimizeLayout() {
        const nodeCount = this.cy.nodes().length;
        
        if (nodeCount > 500) {
            // Use fast layout for large graphs
            this.cy.layout({
                name: 'grid',
                animate: false,
                fit: true
            }).run();
        } else {
            // Use detailed layout for smaller graphs
            this.cy.layout({
                name: 'dagre',
                animate: true,
                fit: true,
                rankDir: 'TB',
                nodeSep: 50,
                edgeSep: 10,
                rankSep: 80
            }).run();
        }
    }

    /**
     * Check memory pressure and trigger GC if needed
     */
    checkMemoryPressure() {
        if (!performance.memory) return;
        
        const usedRatio = performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit;
        
        if (usedRatio > this.memory.gcThreshold) {
            console.log('Memory pressure detected, triggering optimizations');
            
            // Clear caches
            this.clearCaches();
            
            // Force garbage collection if available
            if (window.gc) {
                window.gc();
            }
            
            // Update last GC time
            this.memory.lastGC = Date.now();
        }
    }

    /**
     * Clear performance caches
     */
    clearCaches() {
        this.caching.layoutCache.clear();
        this.caching.styleCache.clear();
        this.caching.searchCache.clear();
        
        // Clear node and edge caches if virtualization is enabled
        if (this.virtualization.enabled) {
            this.virtualization.nodeCache.clear();
            this.virtualization.edgeCache.clear();
        }
    }

    /**
     * Process large graph data in worker
     */
    processInWorker(type, data) {
        if (this.worker) {
            this.worker.postMessage({ type, data });
        } else {
            // Fallback to main thread processing
            this.processInMainThread(type, data);
        }
    }

    /**
     * Fallback processing in main thread
     */
    processInMainThread(type, data) {
        switch(type) {
            case 'FILTER_GRAPH':
                // Simple filtering in main thread
                const filtered = this.filterGraphMainThread(data.graph, data.filters);
                this.applyFilteredGraph(filtered);
                break;
        }
    }

    /**
     * Simple graph filtering in main thread
     */
    filterGraphMainThread(graph, filters) {
        let { nodes, edges } = graph;
        
        if (filters.complexity) {
            nodes = nodes.filter(node => 
                node.data.complexity >= filters.complexity.min &&
                node.data.complexity <= filters.complexity.max
            );
        }
        
        // Filter edges to only include those between filtered nodes
        const filteredNodeIds = new Set(nodes.map(n => n.id));
        edges = edges.filter(edge => 
            filteredNodeIds.has(edge.data.source) && 
            filteredNodeIds.has(edge.data.target)
        );
        
        return { nodes, edges };
    }

    /**
     * Apply layout from worker
     */
    applyLayout(layoutData) {
        if (this.cy && layoutData.positions) {
            // Apply positions to nodes
            Object.entries(layoutData.positions).forEach(([nodeId, position]) => {
                const node = this.cy.getElementById(nodeId);
                if (node.length > 0) {
                    node.position(position);
                }
            });
        }
    }

    /**
     * Apply filtered graph from worker
     */
    applyFilteredGraph(filteredData) {
        if (this.cy) {
            // Remove existing elements
            this.cy.elements().remove();
            
            // Add filtered elements
            this.cy.add(filteredData.nodes);
            this.cy.add(filteredData.edges);
            
            // Fit to view
            this.cy.fit();
        }
    }

    /**
     * Update metrics from worker
     */
    updateMetrics(metrics) {
        // Update UI with calculated metrics
        const metricsElement = document.getElementById('graphMetrics');
        if (metricsElement) {
            metricsElement.innerHTML = `
                <div class="metrics-display">
                    <div class="metric-item">
                        <span class="metric-label">Nodes:</span>
                        <span class="metric-value">${metrics.totalNodes}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Edges:</span>
                        <span class="metric-value">${metrics.totalEdges}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Avg Complexity:</span>
                        <span class="metric-value">${metrics.avgComplexity.toFixed(1)}</span>
                    </div>
                    <div class="metric-item">
                        <span class="metric-label">Side Effects:</span>
                        <span class="metric-value">${metrics.sideEffectCount}</span>
                    </div>
                </div>
            `;
        }
    }

    /**
     * Apply optimized styles from worker
     */
    applyOptimizedStyles(styles) {
        if (this.cy) {
            // Apply node styles
            Object.entries(styles.nodes).forEach(([nodeId, style]) => {
                const node = this.cy.getElementById(nodeId);
                if (node.length > 0) {
                    Object.entries(style).forEach(([property, value]) => {
                        node.style(property, value);
                    });
                }
            });
            
            // Apply edge styles
            Object.entries(styles.edges).forEach(([edgeId, style]) => {
                const edge = this.cy.getElementById(edgeId);
                if (edge.length > 0) {
                    Object.entries(style).forEach(([property, value]) => {
                        edge.style(property, value);
                    });
                }
            });
        }
    }

    /**
     * Get performance metrics
     */
    getPerformanceMetrics() {
        return {
            frameRate: this.getAverageFrameRate(),
            memoryUsage: this.getMemoryUsage(),
            graphSize: {
                nodes: this.cy ? this.cy.nodes().length : 0,
                edges: this.cy ? this.cy.edges().length : 0
            },
            virtualization: {
                enabled: this.virtualization.enabled,
                renderedNodes: this.virtualization.renderedNodes.size
            },
            quality: {
                level: this.adaptiveQuality.currentLevel,
                name: this.adaptiveQuality.levels[this.adaptiveQuality.currentLevel].name
            }
        };
    }

    /**
     * Get average frame rate
     */
    getAverageFrameRate() {
        const frameTimes = this.performanceMetrics.frameTime;
        if (frameTimes.length === 0) return 0;
        
        const avgFrameTime = frameTimes.reduce((sum, frame) => sum + frame.frameTime, 0) / frameTimes.length;
        return Math.round(1000 / avgFrameTime);
    }

    /**
     * Get current memory usage
     */
    getMemoryUsage() {
        if (!performance.memory) return null;
        
        return {
            used: performance.memory.usedJSHeapSize,
            total: performance.memory.totalJSHeapSize,
            limit: performance.memory.jsHeapSizeLimit,
            percentage: (performance.memory.usedJSHeapSize / performance.memory.jsHeapSizeLimit) * 100
        };
    }

    /**
     * Utility function for debouncing
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    /**
     * Cleanup and destroy optimizer
     */
    destroy() {
        if (this.worker) {
            this.worker.terminate();
            this.worker = null;
        }
        
        this.clearCaches();
        
        if (this.virtualization.enabled) {
            this.disableVirtualization();
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PerformanceOptimizer;
} else if (typeof window !== 'undefined') {
    window.PerformanceOptimizer = PerformanceOptimizer;
}
