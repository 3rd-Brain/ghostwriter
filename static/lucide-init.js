
// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');
  initLucideIcons();
});

// Function to initialize all icons with the data-lucide attribute
function initLucideIcons() {
  if (typeof lucide === 'undefined') {
    console.error('Lucide library not found. Loading it now...');
    loadLucideScript();
    return;
  }
  
  try {
    console.log('Lucide library found, creating icons...');
    lucide.createIcons();
    console.log('Lucide icons initialized successfully');
    
    // Debug which icons are available
    if (lucide.icons) {
      console.log('Available icons:', Object.keys(lucide.icons).slice(0, 10), '... and more');
    }
  } catch (error) {
    console.error('Error initializing Lucide icons:', error);
  }
}

// Function to dynamically load the Lucide script if it's not present
function loadLucideScript() {
  const script = document.createElement('script');
  script.src = '/static/lucide.min.js';
  script.async = true;
  
  script.onload = function() {
    console.log('Lucide script loaded successfully');
    // Add a small delay to ensure library is fully initialized
    setTimeout(initLucideIcons, 100);
  };
  
  script.onerror = function() {
    console.error('Failed to load Lucide script');
  };
  
  document.head.appendChild(script);
}
