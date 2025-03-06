
/**
 * Lucide Icons initialization script
 * This script initializes Lucide icons on page load and provides an API to create icons dynamically
 */

// Function to initialize all icons with the data-lucide attribute
function initLucideIcons() {
  if (typeof lucide !== 'undefined' && lucide.createIcons) {
    lucide.createIcons({
      attrs: {
        stroke: 'currentColor',
        strokeWidth: 2,
        size: 24
      }
    });
    console.log('Lucide icons initialized successfully');
  } else {
    console.warn('Lucide library not found or createIcons method not available');
  }
}

// Initialize icons when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');
  setTimeout(initLucideIcons, 100); // Small delay to ensure all icon scripts are loaded
});

// Additional initialization for dynamic content
window.addEventListener('load', function() {
  console.log('Window loaded, reinitializing Lucide icons');
  initLucideIcons();
});

// Function to create an icon dynamically
window.createLucideIcon = function(iconName, options = {}) {
  if (typeof lucide === 'undefined') {
    console.error('Lucide library not found');
    return null;
  }
  
  const element = document.createElement('div');
  element.setAttribute('data-lucide', iconName);
  
  // Apply the Lucide icon
  lucide.createIcons({
    selector: '[data-lucide="' + iconName + '"]',
    attrs: {
      stroke: options.stroke || 'currentColor',
      strokeWidth: options.strokeWidth || 2,
      width: options.size || 24,
      height: options.size || 24
    }
  });
  
  return element.innerHTML;
};

// Function to replace icon in an element
window.replaceLucideIcon = function(element, iconName, options = {}) {
  const iconSvg = window.createLucideIcon(iconName, options);
  if (iconSvg) {
    element.innerHTML = iconSvg;
  }
};

// Function to reinitialize icons (call this after adding new elements to the DOM)
window.reinitLucideIcons = initLucideIcons;
