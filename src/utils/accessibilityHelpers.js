/**
 * Accessibility Helpers
 * 
 * Utility functions for accessibility best practices.
 */

/**
 * Generate aria-describedby string from multiple IDs
 */
export function generateAriaDescribedBy(...ids) {
  const validIds = ids.filter(Boolean);
  return validIds.length > 0 ? validIds.join(' ') : null;
}

/**
 * Announce message to screen readers
 */
export function announceToScreenReader(message, priority = 'polite') {
  const announcement = document.createElement('div');
  announcement.setAttribute('role', 'status');
  announcement.setAttribute('aria-live', priority);
  announcement.setAttribute('aria-atomic', 'true');
  announcement.className = 'sr-only';
  announcement.textContent = message;

  document.body.appendChild(announcement);

  // Remove after announcement
  setTimeout(() => {
    document.body.removeChild(announcement);
  }, 1000);
}

/**
 * Focus management - move focus to element
 */
export function moveFocusTo(elementOrId) {
  const element =
    typeof elementOrId === 'string'
      ? document.getElementById(elementOrId)
      : elementOrId;

  if (element) {
    element.focus();
    return true;
  }
  return false;
}

/**
 * Trap focus within a container (for modals)
 */
export function trapFocus(containerElement) {
  const focusableElements = containerElement.querySelectorAll(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
  );

  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  function handleKeyDown(event) {
    if (event.key !== 'Tab') return;

    if (event.shiftKey) {
      if (document.activeElement === firstElement) {
        event.preventDefault();
        lastElement.focus();
      }
    } else {
      if (document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
      }
    }
  }

  containerElement.addEventListener('keydown', handleKeyDown);

  // Return cleanup function
  return () => {
    containerElement.removeEventListener('keydown', handleKeyDown);
  };
}

/**
 * Generate unique ID for form elements
 */
export function generateUniqueId(prefix = 'id') {
  return `${prefix}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Check if element is visible to screen readers
 */
export function isVisibleToScreenReader(element) {
  if (!element) return false;

  const style = window.getComputedStyle(element);
  
  // Check for common hiding techniques
  if (style.display === 'none') return false;
  if (style.visibility === 'hidden') return false;
  if (element.getAttribute('aria-hidden') === 'true') return false;
  
  return true;
}

/**
 * Get accessible name for element
 */
export function getAccessibleName(element) {
  // Check aria-labelledby
  const labelledById = element.getAttribute('aria-labelledby');
  if (labelledById) {
    const labelElement = document.getElementById(labelledById);
    if (labelElement) return labelElement.textContent;
  }

  // Check aria-label
  const ariaLabel = element.getAttribute('aria-label');
  if (ariaLabel) return ariaLabel;

  // Check for associated label
  if (element.id) {
    const label = document.querySelector(`label[for="${element.id}"]`);
    if (label) return label.textContent;
  }

  // Check for placeholder (less preferred)
  if (element.placeholder) return element.placeholder;

  // Check for title
  if (element.title) return element.title;

  return null;
}

/**
 * Add skip link for keyboard navigation
 */
export function createSkipLink(targetId, text = 'Skip to main content') {
  const skipLink = document.createElement('a');
  skipLink.href = `#${targetId}`;
  skipLink.className = 'skip-link';
  skipLink.textContent = text;

  skipLink.addEventListener('click', (event) => {
    event.preventDefault();
    const target = document.getElementById(targetId);
    if (target) {
      target.setAttribute('tabindex', '-1');
      target.focus();
    }
  });

  return skipLink;
}

/**
 * Screen reader only CSS class
 */
export const srOnlyStyles = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: '0',
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  border: '0',
};

export default {
  generateAriaDescribedBy,
  announceToScreenReader,
  moveFocusTo,
  trapFocus,
  generateUniqueId,
  isVisibleToScreenReader,
  getAccessibleName,
  createSkipLink,
  srOnlyStyles,
};

