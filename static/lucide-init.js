// Wait for the DOM to be fully loaded before initializing icons
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');
  initLucideIcons();
});

// Also initialize when window is fully loaded to catch any dynamic changes
window.addEventListener('load', function() {
  console.log('Window loaded, reinitializing Lucide icons');
  initLucideIcons();
});

// Function to initialize all icons with the data-lucide attribute
function initLucideIcons() {
  if (typeof lucide !== 'undefined' && lucide.createIcons) {
    try {
      lucide.createIcons();
      console.log('Lucide icons initialized successfully');
    } catch (error) {
      console.error('Error initializing Lucide icons:', error);
    }
  } else {
    console.warn('Lucide library not found or createIcons method not available');
  }
}

// Function to create an icon dynamically if needed
window.createLucideIcon = function(name, options = {}) {
  if (typeof lucide === 'undefined' || !lucide.icons || !lucide.icons[name]) {
    console.error(`Lucide icon "${name}" not found. Make sure the library is loaded.`);
    return '';
  }

  const defaultOptions = {
    stroke: 'currentColor',
    strokeWidth: 2,
    size: 24
  };

  const element = document.createElement('div');
  const iconOptions = {...defaultOptions, ...options};

  // Create the icon SVG
  element.innerHTML = lucide.icons[name].toSvg(iconOptions);

  return element.innerHTML;
};

// Function to replace an icon in an element
window.replaceIconInElement = function(element, iconName, options = {}) {
  if (!element) return;

  const iconSvg = window.createLucideIcon(iconName, options);
  if (iconSvg) {
    element.innerHTML = iconSvg;
  }
};

// Function to reinitialize icons (call this after adding new elements to the DOM)
window.reinitLucideIcons = initLucideIcons;