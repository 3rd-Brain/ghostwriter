// Wait for the DOM content to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');

  // Check if Lucide library exists
  if (typeof lucide !== 'undefined') {
    console.log('Lucide found, initializing icons');
    try {
      lucide.createIcons();
      console.log('Icons initialized successfully');
    } catch (e) {
      console.error('Error initializing icons:', e);
    }
  } else {
    console.error('Lucide library not found');

    // Attempt to load Lucide
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/lucide@latest/dist/umd/lucide.min.js';
    script.onload = function() {
      console.log('Lucide loaded from CDN');
      setTimeout(function() {
        if (typeof lucide !== 'undefined') {
          lucide.createIcons();
          console.log('Icons initialized after loading');
        }
      }, 100);
    };
    document.head.appendChild(script);
  }
});