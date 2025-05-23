
// Wait for the DOM content to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');

  // Load Lucide from CDN
  const script = document.createElement('script');
  script.src = 'https://unpkg.com/lucide@latest/dist/umd/lucide.min.js';
  script.onload = function() {
    console.log('Lucide loaded from CDN');
    
    // Register the key-alert icon to prevent errors
    if (typeof lucide !== 'undefined') {
      // Add the key-alert icon if it doesn't exist
      if (!lucide.icons['key-alert']) {
        lucide.icons['key-alert'] = {
          name: 'key-alert',
          toSvg: function() {
            return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16.2 11c1.8-1.5 3-3.8 3-6.4a7 7 0 1 0-11.9 5"></path><path d="M13 14h-5.8l-2.9 2.9a2.3 2.3 0 0 0 3.2 3.2l4.5-4.5"></path><circle cx="15" cy="9" r=".5"></circle><path d="M17 17v.01"></path><path d="M17 14v-2"></path></svg>`;
          }
        };
      }
      
      lucide.createIcons();
      console.log('Icons initialized after loading');
    }
  };
  document.head.appendChild(script);
});
