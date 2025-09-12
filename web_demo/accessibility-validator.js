/**
 * Accessibility Validator for Understand-First
 * 
 * This module provides comprehensive accessibility validation including
 * alt text validation, contrast checking, and assistive technology testing.
 */

class AccessibilityValidator {
    constructor() {
        this.issues = [];
        this.contrastChecker = new ContrastChecker();
        this.altTextValidator = new AltTextValidator();
        this.keyboardValidator = new KeyboardValidator();
        this.screenReaderValidator = new ScreenReaderValidator();
        
        this.setupValidation();
    }

    /**
     * Setup accessibility validation
     */
    setupValidation() {
        // Run validation on page load
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                this.runFullValidation();
            });
        } else {
            this.runFullValidation();
        }
        
        // Run validation on content changes
        this.setupMutationObserver();
        
        // Run validation on theme changes
        document.addEventListener('themeChanged', () => {
            this.runFullValidation();
        });
    }

    /**
     * Setup mutation observer for dynamic content
     */
    setupMutationObserver() {
        const observer = new MutationObserver((mutations) => {
            let shouldValidate = false;
            
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    shouldValidate = true;
                }
            });
            
            if (shouldValidate) {
                setTimeout(() => this.runFullValidation(), 100);
            }
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    /**
     * Run full accessibility validation
     */
    runFullValidation() {
        this.issues = [];
        
        // Validate alt text
        this.validateAltText();
        
        // Validate color contrast
        this.validateColorContrast();
        
        // Validate keyboard navigation
        this.validateKeyboardNavigation();
        
        // Validate ARIA labels
        this.validateARIALabels();
        
        // Validate semantic HTML
        this.validateSemanticHTML();
        
        // Report issues
        this.reportIssues();
    }

    /**
     * Validate alt text for images
     */
    validateAltText() {
        const images = document.querySelectorAll('img');
        
        images.forEach((img, index) => {
            const alt = img.getAttribute('alt');
            const src = img.getAttribute('src');
            
            if (!alt) {
                this.addIssue('alt-text-missing', {
                    element: img,
                    message: 'Image missing alt text',
                    severity: 'error',
                    fix: 'Add descriptive alt text to image'
                });
            } else if (alt.trim() === '') {
                this.addIssue('alt-text-empty', {
                    element: img,
                    message: 'Image has empty alt text',
                    severity: 'warning',
                    fix: 'Add descriptive alt text or use alt="" for decorative images'
                });
            } else if (alt.length < 3) {
                this.addIssue('alt-text-too-short', {
                    element: img,
                    message: 'Alt text is too short to be descriptive',
                    severity: 'warning',
                    fix: 'Provide more descriptive alt text'
                });
            }
        });
    }

    /**
     * Validate color contrast
     */
    validateColorContrast() {
        const elements = document.querySelectorAll('*');
        
        elements.forEach((element) => {
            const computedStyle = window.getComputedStyle(element);
            const color = computedStyle.color;
            const backgroundColor = computedStyle.backgroundColor;
            
            if (color && backgroundColor && color !== 'rgba(0, 0, 0, 0)' && backgroundColor !== 'rgba(0, 0, 0, 0)') {
                const contrast = this.contrastChecker.calculateContrast(color, backgroundColor);
                
                if (contrast < 4.5) {
                    this.addIssue('contrast-insufficient', {
                        element: element,
                        message: `Insufficient color contrast: ${contrast.toFixed(2)}:1`,
                        severity: contrast < 3 ? 'error' : 'warning',
                        fix: 'Increase color contrast to at least 4.5:1 for normal text'
                    });
                }
            }
        });
    }

    /**
     * Validate keyboard navigation
     */
    validateKeyboardNavigation() {
        const interactiveElements = document.querySelectorAll('button, input, select, textarea, a[href], [tabindex], [role="button"], [role="menuitem"], [role="tab"]');
        
        interactiveElements.forEach((element) => {
            // Check if element is focusable
            if (!this.isFocusable(element)) {
                this.addIssue('not-focusable', {
                    element: element,
                    message: 'Interactive element is not keyboard focusable',
                    severity: 'error',
                    fix: 'Add tabindex="0" or make element focusable'
                });
            }
            
            // Check for focus indicators
            if (!this.hasFocusIndicator(element)) {
                this.addIssue('no-focus-indicator', {
                    element: element,
                    message: 'Interactive element lacks visible focus indicator',
                    severity: 'warning',
                    fix: 'Add visible focus indicator'
                });
            }
        });
    }

    /**
     * Validate ARIA labels
     */
    validateARIALabels() {
        const elementsWithRoles = document.querySelectorAll('[role]');
        
        elementsWithRoles.forEach((element) => {
            const role = element.getAttribute('role');
            const ariaLabel = element.getAttribute('aria-label');
            const ariaLabelledBy = element.getAttribute('aria-labelledby');
            const textContent = element.textContent?.trim();
            
            if (!ariaLabel && !ariaLabelledBy && !textContent) {
                this.addIssue('missing-aria-label', {
                    element: element,
                    message: `Element with role "${role}" lacks accessible name`,
                    severity: 'error',
                    fix: 'Add aria-label or aria-labelledby attribute'
                });
            }
        });
    }

    /**
     * Validate semantic HTML
     */
    validateSemanticHTML() {
        // Check for proper heading hierarchy
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        let lastLevel = 0;
        
        headings.forEach((heading) => {
            const level = parseInt(heading.tagName.charAt(1));
            
            if (level > lastLevel + 1) {
                this.addIssue('heading-skip', {
                    element: heading,
                    message: `Heading level skipped from h${lastLevel} to h${level}`,
                    severity: 'warning',
                    fix: 'Use proper heading hierarchy'
                });
            }
            
            lastLevel = level;
        });
        
        // Check for proper form labels
        const inputs = document.querySelectorAll('input, select, textarea');
        
        inputs.forEach((input) => {
            const id = input.getAttribute('id');
            const ariaLabel = input.getAttribute('aria-label');
            const ariaLabelledBy = input.getAttribute('aria-labelledby');
            const label = id ? document.querySelector(`label[for="${id}"]`) : null;
            
            if (!ariaLabel && !ariaLabelledBy && !label) {
                this.addIssue('missing-form-label', {
                    element: input,
                    message: 'Form input lacks accessible label',
                    severity: 'error',
                    fix: 'Add label element or aria-label attribute'
                });
            }
        });
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
     * Add accessibility issue
     */
    addIssue(type, issue) {
        this.issues.push({
            type: type,
            ...issue,
            timestamp: Date.now()
        });
    }

    /**
     * Report accessibility issues
     */
    reportIssues() {
        if (this.issues.length === 0) {
            console.log('✅ No accessibility issues found');
            return;
        }
        
        console.group('🔍 Accessibility Issues Found');
        
        const errors = this.issues.filter(issue => issue.severity === 'error');
        const warnings = this.issues.filter(issue => issue.severity === 'warning');
        
        if (errors.length > 0) {
            console.group('❌ Errors');
            errors.forEach(issue => {
                console.error(`${issue.type}: ${issue.message}`, issue.element);
                console.log(`Fix: ${issue.fix}`);
            });
            console.groupEnd();
        }
        
        if (warnings.length > 0) {
            console.group('⚠️ Warnings');
            warnings.forEach(issue => {
                console.warn(`${issue.type}: ${issue.message}`, issue.element);
                console.log(`Fix: ${issue.fix}`);
            });
            console.groupEnd();
        }
        
        console.groupEnd();
        
        // Dispatch accessibility report event
        document.dispatchEvent(new CustomEvent('accessibilityReport', {
            detail: {
                errors: errors.length,
                warnings: warnings.length,
                total: this.issues.length,
                issues: this.issues
            }
        }));
        
        // Track in metrics
        if (window.trackMetric) {
            window.trackMetric('accessibility_validation', {
                errors: errors.length,
                warnings: warnings.length,
                total: this.issues.length
            });
        }
    }

    /**
     * Get accessibility report
     */
    getReport() {
        return {
            timestamp: Date.now(),
            total: this.issues.length,
            errors: this.issues.filter(issue => issue.severity === 'error').length,
            warnings: this.issues.filter(issue => issue.severity === 'warning').length,
            issues: this.issues
        };
    }
}

/**
 * Contrast Checker
 */
class ContrastChecker {
    /**
     * Calculate contrast ratio between two colors
     */
    calculateContrast(color1, color2) {
        const rgb1 = this.parseColor(color1);
        const rgb2 = this.parseColor(color2);
        
        if (!rgb1 || !rgb2) return 0;
        
        const lum1 = this.getLuminance(rgb1);
        const lum2 = this.getLuminance(rgb2);
        
        const lighter = Math.max(lum1, lum2);
        const darker = Math.min(lum1, lum2);
        
        return (lighter + 0.05) / (darker + 0.05);
    }

    /**
     * Parse color string to RGB
     */
    parseColor(color) {
        // Remove spaces and convert to lowercase
        color = color.replace(/\s/g, '').toLowerCase();
        
        // Handle rgb() format
        if (color.startsWith('rgb(')) {
            const values = color.match(/rgb\((\d+),(\d+),(\d+)\)/);
            if (values) {
                return {
                    r: parseInt(values[1]),
                    g: parseInt(values[2]),
                    b: parseInt(values[3])
                };
            }
        }
        
        // Handle rgba() format
        if (color.startsWith('rgba(')) {
            const values = color.match(/rgba\((\d+),(\d+),(\d+),([\d.]+)\)/);
            if (values) {
                return {
                    r: parseInt(values[1]),
                    g: parseInt(values[2]),
                    b: parseInt(values[3])
                };
            }
        }
        
        // Handle hex format
        if (color.startsWith('#')) {
            const hex = color.substring(1);
            if (hex.length === 3) {
                return {
                    r: parseInt(hex[0] + hex[0], 16),
                    g: parseInt(hex[1] + hex[1], 16),
                    b: parseInt(hex[2] + hex[2], 16)
                };
            } else if (hex.length === 6) {
                return {
                    r: parseInt(hex.substring(0, 2), 16),
                    g: parseInt(hex.substring(2, 4), 16),
                    b: parseInt(hex.substring(4, 6), 16)
                };
            }
        }
        
        return null;
    }

    /**
     * Calculate relative luminance
     */
    getLuminance(rgb) {
        const { r, g, b } = rgb;
        
        // Convert to sRGB
        const rsRGB = r / 255;
        const gsRGB = g / 255;
        const bsRGB = b / 255;
        
        // Apply gamma correction
        const rLinear = rsRGB <= 0.03928 ? rsRGB / 12.92 : Math.pow((rsRGB + 0.055) / 1.055, 2.4);
        const gLinear = gsRGB <= 0.03928 ? gsRGB / 12.92 : Math.pow((gsRGB + 0.055) / 1.055, 2.4);
        const bLinear = bsRGB <= 0.03928 ? bsRGB / 12.92 : Math.pow((bsRGB + 0.055) / 1.055, 2.4);
        
        return 0.2126 * rLinear + 0.7152 * gLinear + 0.0722 * bLinear;
    }
}

/**
 * Alt Text Validator
 */
class AltTextValidator {
    /**
     * Validate alt text quality
     */
    validateAltText(altText, context) {
        const issues = [];
        
        if (!altText) {
            issues.push('Missing alt text');
            return issues;
        }
        
        if (altText.trim() === '') {
            issues.push('Empty alt text');
            return issues;
        }
        
        if (altText.length < 3) {
            issues.push('Alt text too short');
        }
        
        if (altText.length > 125) {
            issues.push('Alt text too long');
        }
        
        if (altText.toLowerCase().includes('image of') || altText.toLowerCase().includes('picture of')) {
            issues.push('Redundant "image of" or "picture of" in alt text');
        }
        
        return issues;
    }
}

/**
 * Keyboard Validator
 */
class KeyboardValidator {
    /**
     * Validate keyboard navigation
     */
    validateKeyboardNavigation() {
        const issues = [];
        const focusableElements = document.querySelectorAll('button, input, select, textarea, a[href], [tabindex]');
        
        focusableElements.forEach((element, index) => {
            if (!this.isFocusable(element)) {
                issues.push(`Element ${index} is not keyboard focusable`);
            }
        });
        
        return issues;
    }

    /**
     * Check if element is focusable
     */
    isFocusable(element) {
        const tabIndex = element.getAttribute('tabindex');
        return tabIndex !== '-1' && (tabIndex === '0' || tabIndex === '' || parseInt(tabIndex) >= 0);
    }
}

/**
 * Screen Reader Validator
 */
class ScreenReaderValidator {
    /**
     * Validate screen reader compatibility
     */
    validateScreenReaderCompatibility() {
        const issues = [];
        
        // Check for proper heading structure
        const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
        let lastLevel = 0;
        
        headings.forEach((heading) => {
            const level = parseInt(heading.tagName.charAt(1));
            if (level > lastLevel + 1) {
                issues.push(`Heading level skipped from h${lastLevel} to h${level}`);
            }
            lastLevel = level;
        });
        
        // Check for proper form labels
        const inputs = document.querySelectorAll('input, select, textarea');
        inputs.forEach((input) => {
            const id = input.getAttribute('id');
            const label = id ? document.querySelector(`label[for="${id}"]`) : null;
            const ariaLabel = input.getAttribute('aria-label');
            
            if (!label && !ariaLabel) {
                issues.push(`Form input lacks accessible label`);
            }
        });
        
        return issues;
    }
}

// Initialize accessibility validator when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.accessibilityValidator = new AccessibilityValidator();
});

// Export for global access
window.AccessibilityValidator = AccessibilityValidator;
