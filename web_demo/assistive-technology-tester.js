/**
 * Assistive Technology Tester for Understand-First
 * 
 * This module provides testing capabilities for screen readers and other
 * assistive technologies to ensure proper accessibility support.
 */

class AssistiveTechnologyTester {
    constructor() {
        this.screenReader = null;
        this.voiceOver = null;
        this.nvda = null;
        this.jaws = null;
        
        this.testResults = {
            screenReader: [],
            keyboard: [],
            voiceControl: [],
            highContrast: [],
            zoom: []
        };
        
        this.setupTesting();
    }

    /**
     * Setup assistive technology testing
     */
    setupTesting() {
        // Detect available assistive technologies
        this.detectAssistiveTechnologies();
        
        // Setup keyboard testing
        this.setupKeyboardTesting();
        
        // Setup voice control testing
        this.setupVoiceControlTesting();
        
        // Setup high contrast testing
        this.setupHighContrastTesting();
        
        // Setup zoom testing
        this.setupZoomTesting();
        
        // Run initial tests
        this.runInitialTests();
    }

    /**
     * Detect available assistive technologies
     */
    detectAssistiveTechnologies() {
        // Detect screen readers
        this.detectScreenReaders();
        
        // Detect voice control
        this.detectVoiceControl();
        
        // Detect high contrast mode
        this.detectHighContrastMode();
    }

    /**
     * Detect screen readers
     */
    detectScreenReaders() {
        // Detect VoiceOver (macOS)
        if (navigator.userAgent.includes('Mac') && window.speechSynthesis) {
            this.voiceOver = new VoiceOverTester();
        }
        
        // Detect NVDA (Windows)
        if (navigator.userAgent.includes('Windows') && window.speechSynthesis) {
            this.nvda = new NVDATester();
        }
        
        // Detect JAWS (Windows)
        if (navigator.userAgent.includes('Windows') && window.speechSynthesis) {
            this.jaws = new JawsTester();
        }
        
        // Generic screen reader detection
        this.screenReader = new GenericScreenReaderTester();
    }

    /**
     * Detect voice control
     */
    detectVoiceControl() {
        // Check for Web Speech API
        if ('speechRecognition' in window || 'webkitSpeechRecognition' in window) {
            this.voiceControl = new VoiceControlTester();
        }
    }

    /**
     * Detect high contrast mode
     */
    detectHighContrastMode() {
        // Check for high contrast media query
        if (window.matchMedia && window.matchMedia('(prefers-contrast: high)').matches) {
            this.highContrast = new HighContrastTester();
        }
    }

    /**
     * Setup keyboard testing
     */
    setupKeyboardTesting() {
        // Test tab navigation
        this.testTabNavigation();
        
        // Test arrow key navigation
        this.testArrowKeyNavigation();
        
        // Test escape key functionality
        this.testEscapeKeyFunctionality();
        
        // Test enter/space key functionality
        this.testEnterSpaceKeyFunctionality();
    }

    /**
     * Setup voice control testing
     */
    setupVoiceControlTesting() {
        if (this.voiceControl) {
            this.voiceControl.testVoiceCommands();
        }
    }

    /**
     * Setup high contrast testing
     */
    setupHighContrastTesting() {
        if (this.highContrast) {
            this.highContrast.testHighContrastMode();
        }
    }

    /**
     * Setup zoom testing
     */
    setupZoomTesting() {
        this.testZoomLevels();
    }

    /**
     * Run initial tests
     */
    runInitialTests() {
        // Test screen reader compatibility
        this.testScreenReaderCompatibility();
        
        // Test keyboard accessibility
        this.testKeyboardAccessibility();
        
        // Test focus management
        this.testFocusManagement();
        
        // Test ARIA implementation
        this.testARIAImplementation();
    }

    /**
     * Test screen reader compatibility
     */
    testScreenReaderCompatibility() {
        const results = [];
        
        // Test heading structure
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        let lastLevel = 0;
        
        headings.forEach((heading, index) => {
            const level = parseInt(heading.tagName.charAt(1));
            
            if (level > lastLevel + 1) {
                results.push({
                    type: 'heading-skip',
                    message: `Heading level skipped from h${lastLevel} to h${level}`,
                    element: heading,
                    severity: 'error'
                });
            }
            
            lastLevel = level;
        });
        
        // Test form labels
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach((input) => {
            const id = input.getAttribute('id');
            const label = id ? document.querySelector(`label[for="${id}"]`) : null;
            const ariaLabel = input.getAttribute('aria-label');
            const ariaLabelledBy = input.getAttribute('aria-labelledby');
            
            if (!label && !ariaLabel && !ariaLabelledBy) {
                results.push({
                    type: 'missing-form-label',
                    message: 'Form input lacks accessible label',
                    element: input,
                    severity: 'error'
                });
            }
        });
        
        // Test ARIA landmarks
        const landmarks = document.querySelectorAll('[role="banner"], [role="main"], [role="contentinfo"], [role="navigation"], [role="complementary"]');
        if (landmarks.length === 0) {
            results.push({
                type: 'missing-landmarks',
                message: 'No ARIA landmarks found',
                element: document.body,
                severity: 'warning'
            });
        }
        
        this.testResults.screenReader = results;
    }

    /**
     * Test keyboard accessibility
     */
    testKeyboardAccessibility() {
        const results = [];
        const interactiveElements = document.querySelectorAll('button, input, select, textarea, a[href], [tabindex], [role="button"], [role="menuitem"], [role="tab"]');
        
        interactiveElements.forEach((element, index) => {
            // Test if element is focusable
            if (!this.isFocusable(element)) {
                results.push({
                    type: 'not-focusable',
                    message: 'Interactive element is not keyboard focusable',
                    element: element,
                    severity: 'error'
                });
            }
            
            // Test focus indicators
            if (!this.hasFocusIndicator(element)) {
                results.push({
                    type: 'no-focus-indicator',
                    message: 'Interactive element lacks visible focus indicator',
                    element: element,
                    severity: 'warning'
                });
            }
            
            // Test keyboard event handlers
            if (!this.hasKeyboardEventHandlers(element)) {
                results.push({
                    type: 'no-keyboard-handlers',
                    message: 'Interactive element lacks keyboard event handlers',
                    element: element,
                    severity: 'warning'
                });
            }
        });
        
        this.testResults.keyboard = results;
    }

    /**
     * Test focus management
     */
    testFocusManagement() {
        const results = [];
        
        // Test focus trap in modals
        const modals = document.querySelectorAll('[role="dialog"], [role="alertdialog"]');
        modals.forEach((modal) => {
            if (!this.hasFocusTrap(modal)) {
                results.push({
                    type: 'no-focus-trap',
                    message: 'Modal dialog lacks focus trap',
                    element: modal,
                    severity: 'warning'
                });
            }
        });
        
        // Test focus restoration
        const focusableElements = document.querySelectorAll('button, input, select, textarea, a[href]');
        if (focusableElements.length > 0) {
            const firstElement = focusableElements[0];
            const lastElement = focusableElements[focusableElements.length - 1];
            
            // Test if focus can be moved from first to last element
            if (!this.canMoveFocus(firstElement, lastElement)) {
                results.push({
                    type: 'focus-navigation-issue',
                    message: 'Focus navigation may be broken',
                    element: document.body,
                    severity: 'warning'
                });
            }
        }
        
        this.testResults.focus = results;
    }

    /**
     * Test ARIA implementation
     */
    testARIAImplementation() {
        const results = [];
        
        // Test ARIA labels
        const elementsWithRoles = document.querySelectorAll('[role]');
        elementsWithRoles.forEach((element) => {
            const role = element.getAttribute('role');
            const ariaLabel = element.getAttribute('aria-label');
            const ariaLabelledBy = element.getAttribute('aria-labelledby');
            const textContent = element.textContent?.trim();
            
            if (!ariaLabel && !ariaLabelledBy && !textContent) {
                results.push({
                    type: 'missing-aria-label',
                    message: `Element with role "${role}" lacks accessible name`,
                    element: element,
                    severity: 'error'
                });
            }
        });
        
        // Test ARIA states
        const elementsWithStates = document.querySelectorAll('[aria-expanded], [aria-selected], [aria-checked], [aria-pressed]');
        elementsWithStates.forEach((element) => {
            const state = element.getAttribute('aria-expanded') || 
                         element.getAttribute('aria-selected') || 
                         element.getAttribute('aria-checked') || 
                         element.getAttribute('aria-pressed');
            
            if (state !== 'true' && state !== 'false') {
                results.push({
                    type: 'invalid-aria-state',
                    message: `Invalid ARIA state value: ${state}`,
                    element: element,
                    severity: 'error'
                });
            }
        });
        
        this.testResults.aria = results;
    }

    /**
     * Test tab navigation
     */
    testTabNavigation() {
        const results = [];
        const focusableElements = document.querySelectorAll('button, input, select, textarea, a[href], [tabindex]');
        
        // Test tab order
        for (let i = 0; i < focusableElements.length - 1; i++) {
            const current = focusableElements[i];
            const next = focusableElements[i + 1];
            
            if (!this.canTabToNext(current, next)) {
                results.push({
                    type: 'tab-order-issue',
                    message: 'Tab order may be incorrect',
                    element: current,
                    severity: 'warning'
                });
            }
        }
        
        this.testResults.keyboard.push(...results);
    }

    /**
     * Test arrow key navigation
     */
    testArrowKeyNavigation() {
        const results = [];
        const menuItems = document.querySelectorAll('[role="menuitem"], [role="tab"]');
        
        if (menuItems.length > 1) {
            // Test arrow key navigation in menus
            for (let i = 0; i < menuItems.length - 1; i++) {
                const current = menuItems[i];
                const next = menuItems[i + 1];
                
                if (!this.canNavigateWithArrowKeys(current, next)) {
                    results.push({
                        type: 'arrow-navigation-issue',
                        message: 'Arrow key navigation may be broken',
                        element: current,
                        severity: 'warning'
                    });
                }
            }
        }
        
        this.testResults.keyboard.push(...results);
    }

    /**
     * Test escape key functionality
     */
    testEscapeKeyFunctionality() {
        const results = [];
        const modals = document.querySelectorAll('[role="dialog"], [role="alertdialog"]');
        
        modals.forEach((modal) => {
            if (!this.hasEscapeKeyHandler(modal)) {
                results.push({
                    type: 'no-escape-handler',
                    message: 'Modal dialog lacks escape key handler',
                    element: modal,
                    severity: 'warning'
                });
            }
        });
        
        this.testResults.keyboard.push(...results);
    }

    /**
     * Test enter/space key functionality
     */
    testEnterSpaceKeyFunctionality() {
        const results = [];
        const buttons = document.querySelectorAll('button, [role="button"]');
        
        buttons.forEach((button) => {
            if (!this.hasEnterSpaceKeyHandler(button)) {
                results.push({
                    type: 'no-enter-space-handler',
                    message: 'Button lacks enter/space key handler',
                    element: button,
                    severity: 'warning'
                });
            }
        });
        
        this.testResults.keyboard.push(...results);
    }

    /**
     * Test zoom levels
     */
    testZoomLevels() {
        const results = [];
        const zoomLevels = [100, 125, 150, 200, 300];
        
        zoomLevels.forEach((zoom) => {
            // Simulate zoom level
            document.body.style.zoom = `${zoom}%`;
            
            // Test if content is still accessible
            const issues = this.testContentAccessibility();
            if (issues.length > 0) {
                results.push({
                    type: 'zoom-accessibility-issue',
                    message: `Content accessibility issues at ${zoom}% zoom`,
                    zoom: zoom,
                    issues: issues,
                    severity: 'warning'
                });
            }
        });
        
        // Reset zoom
        document.body.style.zoom = '100%';
        
        this.testResults.zoom = results;
    }

    /**
     * Test content accessibility at current zoom level
     */
    testContentAccessibility() {
        const issues = [];
        
        // Test if text is readable
        const textElements = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6');
        textElements.forEach((element) => {
            const computedStyle = window.getComputedStyle(element);
            const fontSize = parseFloat(computedStyle.fontSize);
            
            if (fontSize < 12) {
                issues.push({
                    type: 'text-too-small',
                    message: 'Text may be too small to read',
                    element: element,
                    fontSize: fontSize
                });
            }
        });
        
        // Test if interactive elements are clickable
        const interactiveElements = document.querySelectorAll('button, input, select, textarea, a[href]');
        interactiveElements.forEach((element) => {
            const rect = element.getBoundingClientRect();
            const minSize = 44; // WCAG minimum touch target size
            
            if (rect.width < minSize || rect.height < minSize) {
                issues.push({
                    type: 'target-too-small',
                    message: 'Interactive element may be too small to click',
                    element: element,
                    size: { width: rect.width, height: rect.height }
                });
            }
        });
        
        return issues;
    }

    /**
     * Check if element is focusable
     */
    isFocusable(element) {
        const tabIndex = element.getAttribute('tabindex');
        
        if (tabIndex === '0' || tabIndex === '') {
            return true;
        }
        
        if (tabIndex && parseInt(tabIndex) >= 0) {
            return true;
        }
        
        // Check if element is naturally focusable
        const naturallyFocusable = ['button', 'input', 'select', 'textarea', 'a[href]'];
        return naturallyFocusable.some(selector => element.matches(selector));
    }

    /**
     * Check if element has focus indicator
     */
    hasFocusIndicator(element) {
        const computedStyle = window.getComputedStyle(element, ':focus');
        return computedStyle.outline !== 'none' || computedStyle.boxShadow !== 'none';
    }

    /**
     * Check if element has keyboard event handlers
     */
    hasKeyboardEventHandlers(element) {
        // This is a simplified check - in practice, you'd need to inspect the event listeners
        return element.onkeydown !== null || element.onkeyup !== null || element.onkeypress !== null;
    }

    /**
     * Check if modal has focus trap
     */
    hasFocusTrap(modal) {
        // This is a simplified check - in practice, you'd need to test the actual focus behavior
        return modal.querySelector('[tabindex="-1"]') !== null;
    }

    /**
     * Check if focus can be moved from one element to another
     */
    canMoveFocus(from, to) {
        // This is a simplified check - in practice, you'd need to test the actual focus behavior
        return from && to && this.isFocusable(from) && this.isFocusable(to);
    }

    /**
     * Check if element can tab to next element
     */
    canTabToNext(current, next) {
        // This is a simplified check - in practice, you'd need to test the actual tab behavior
        return current && next && this.isFocusable(current) && this.isFocusable(next);
    }

    /**
     * Check if element can navigate with arrow keys
     */
    canNavigateWithArrowKeys(current, next) {
        // This is a simplified check - in practice, you'd need to test the actual arrow key behavior
        return current && next && this.isFocusable(current) && this.isFocusable(next);
    }

    /**
     * Check if element has escape key handler
     */
    hasEscapeKeyHandler(element) {
        // This is a simplified check - in practice, you'd need to test the actual escape key behavior
        return element.onkeydown !== null;
    }

    /**
     * Check if element has enter/space key handler
     */
    hasEnterSpaceKeyHandler(element) {
        // This is a simplified check - in practice, you'd need to test the actual enter/space key behavior
        return element.onkeydown !== null;
    }

    /**
     * Get test results
     */
    getTestResults() {
        return {
            timestamp: Date.now(),
            screenReader: this.testResults.screenReader,
            keyboard: this.testResults.keyboard,
            focus: this.testResults.focus || [],
            aria: this.testResults.aria || [],
            zoom: this.testResults.zoom,
            voiceControl: this.testResults.voiceControl || [],
            highContrast: this.testResults.highContrast || []
        };
    }

    /**
     * Run comprehensive test suite
     */
    runComprehensiveTest() {
        console.log('🔍 Running comprehensive assistive technology test...');
        
        // Run all tests
        this.runInitialTests();
        this.testTabNavigation();
        this.testArrowKeyNavigation();
        this.testEscapeKeyFunctionality();
        this.testEnterSpaceKeyFunctionality();
        this.testZoomLevels();
        
        // Get results
        const results = this.getTestResults();
        
        // Report results
        this.reportResults(results);
        
        return results;
    }

    /**
     * Report test results
     */
    reportResults(results) {
        console.group('🔍 Assistive Technology Test Results');
        
        const totalIssues = Object.values(results).reduce((total, category) => {
            return total + (Array.isArray(category) ? category.length : 0);
        }, 0);
        
        if (totalIssues === 0) {
            console.log('✅ No accessibility issues found');
        } else {
            console.log(`❌ Found ${totalIssues} accessibility issues`);
            
            Object.entries(results).forEach(([category, issues]) => {
                if (Array.isArray(issues) && issues.length > 0) {
                    console.group(`${category} (${issues.length} issues)`);
                    issues.forEach(issue => {
                        console.error(`${issue.type}: ${issue.message}`, issue.element);
                    });
                    console.groupEnd();
                }
            });
        }
        
        console.groupEnd();
        
        // Dispatch test results event
        document.dispatchEvent(new CustomEvent('assistiveTechnologyTestResults', {
            detail: results
        }));
        
        // Track in metrics
        if (window.trackMetric) {
            window.trackMetric('assistive_technology_test', {
                totalIssues: totalIssues,
                categories: Object.keys(results)
            });
        }
    }
}

/**
 * VoiceOver Tester (macOS)
 */
class VoiceOverTester {
    testVoiceOverCompatibility() {
        // Test VoiceOver specific features
        const results = [];
        
        // Test rotor navigation
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        if (headings.length === 0) {
            results.push({
                type: 'no-headings-for-rotor',
                message: 'No headings found for VoiceOver rotor navigation',
                severity: 'warning'
            });
        }
        
        // Test landmarks
        const landmarks = document.querySelectorAll('[role="banner"], [role="main"], [role="contentinfo"]');
        if (landmarks.length < 3) {
            results.push({
                type: 'insufficient-landmarks',
                message: 'Insufficient landmarks for VoiceOver navigation',
                severity: 'warning'
            });
        }
        
        return results;
    }
}

/**
 * NVDA Tester (Windows)
 */
class NVDATester {
    testNVDACompatibility() {
        // Test NVDA specific features
        const results = [];
        
        // Test table headers
        const tables = document.querySelectorAll('table');
        tables.forEach((table) => {
            const headers = table.querySelectorAll('th');
            if (headers.length === 0) {
                results.push({
                    type: 'table-without-headers',
                    message: 'Table lacks headers for NVDA screen reader',
                    element: table,
                    severity: 'error'
                });
            }
        });
        
        return results;
    }
}

/**
 * JAWS Tester (Windows)
 */
class JawsTester {
    testJawsCompatibility() {
        // Test JAWS specific features
        const results = [];
        
        // Test skip links
        const skipLinks = document.querySelectorAll('a[href^="#"]');
        if (skipLinks.length === 0) {
            results.push({
                type: 'no-skip-links',
                message: 'No skip links found for JAWS users',
                severity: 'warning'
            });
        }
        
        return results;
    }
}

/**
 * Generic Screen Reader Tester
 */
class GenericScreenReaderTester {
    testScreenReaderCompatibility() {
        // Test generic screen reader features
        const results = [];
        
        // Test alt text
        const images = document.querySelectorAll('img');
        images.forEach((img) => {
            if (!img.getAttribute('alt')) {
                results.push({
                    type: 'missing-alt-text',
                    message: 'Image missing alt text for screen readers',
                    element: img,
                    severity: 'error'
                });
            }
        });
        
        return results;
    }
}

/**
 * Voice Control Tester
 */
class VoiceControlTester {
    testVoiceCommands() {
        // Test voice control compatibility
        const results = [];
        
        // Test if interactive elements have accessible names
        const interactiveElements = document.querySelectorAll('button, input, select, textarea, a[href]');
        interactiveElements.forEach((element) => {
            const accessibleName = this.getAccessibleName(element);
            if (!accessibleName) {
                results.push({
                    type: 'no-accessible-name',
                    message: 'Interactive element lacks accessible name for voice control',
                    element: element,
                    severity: 'warning'
                });
            }
        });
        
        return results;
    }

    getAccessibleName(element) {
        return element.getAttribute('aria-label') || 
               element.getAttribute('aria-labelledby') || 
               element.textContent?.trim() || 
               element.getAttribute('title');
    }
}

/**
 * High Contrast Tester
 */
class HighContrastTester {
    testHighContrastMode() {
        // Test high contrast mode compatibility
        const results = [];
        
        // Test if elements have sufficient contrast
        const textElements = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6');
        textElements.forEach((element) => {
            const computedStyle = window.getComputedStyle(element);
            const color = computedStyle.color;
            const backgroundColor = computedStyle.backgroundColor;
            
            if (color && backgroundColor) {
                const contrast = this.calculateContrast(color, backgroundColor);
                if (contrast < 4.5) {
                    results.push({
                        type: 'insufficient-contrast',
                        message: 'Insufficient color contrast for high contrast mode',
                        element: element,
                        contrast: contrast,
                        severity: 'error'
                    });
                }
            }
        });
        
        return results;
    }

    calculateContrast(color1, color2) {
        // Simplified contrast calculation
        // In practice, you'd use a proper contrast calculation library
        return 4.5; // Placeholder
    }
}

// Initialize assistive technology tester when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.assistiveTechnologyTester = new AssistiveTechnologyTester();
});

// Export for global access
window.AssistiveTechnologyTester = AssistiveTechnologyTester;
