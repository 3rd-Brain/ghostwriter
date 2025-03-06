
// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');
  initLucideIcons();
});

// Also initialize on window load to catch any delayed elements
window.addEventListener('load', function() {
  console.log('Window loaded, reinitializing Lucide icons');
  initLucideIcons();
});

// Function to initialize all icons with the data-lucide attribute
function initLucideIcons() {
  // Check if icons are already loaded
  if (typeof lucide === 'undefined') {
    console.error('Lucide library not found. Make sure to include the Lucide script in your HTML.');
    loadLucideScript();
    return;
  }
  
  try {
    lucide.createIcons();
    console.log('Lucide icons initialized successfully');
  } catch (error) {
    console.error('Error initializing Lucide icons:', error);
  }
}

// Function to dynamically load the Lucide script if it's not present
function loadLucideScript() {
  const script = document.createElement('script');
  script.src = '/static/lucide.min.js';
  script.onload = function() {
    console.log('Lucide script loaded successfully');
    initLucideIcons();
  };
  script.onerror = function() {
    console.error('Failed to load Lucide script');
  };
  document.head.appendChild(script);
}
