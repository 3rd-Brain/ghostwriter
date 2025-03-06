
/**
 * Lucide Icons initialization script
 * This script initializes Lucide icons on page load and provides an API to create icons dynamically
 */

// Function to initialize all icons with the data-lucide attribute
function initLucideIcons() {
  document.querySelectorAll('[data-lucide]').forEach(function(element) {
    const iconName = element.getAttribute('data-lucide');
    if (window.lucide && window.lucide[iconName]) {
      element.innerHTML = window.lucide[iconName].toSvg({
        stroke: 'currentColor',
        strokeWidth: 2,
        size: 24
      });
    }
  });
}

// Initialize icons when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', initLucideIcons);

// Function to create an icon dynamically
window.createLucideIcon = function(iconName, options = {}) {
  if (!window.lucide || !window.lucide[iconName]) {
    console.error(`Lucide icon "${iconName}" not found. Make sure to load the icon script.`);
    return null;
  }
  
  const defaultOptions = {
    stroke: 'currentColor',
    strokeWidth: 2,
    size: 24
  };
  
  return window.lucide[iconName].toSvg({...defaultOptions, ...options});
};

// Function to replace icon in an element
window.replaceLucideIcon = function(element, iconName, options = {}) {
  const iconSvg = window.createLucideIcon(iconName, options);
  if (iconSvg) {
    element.innerHTML = iconSvg;
  }
};
