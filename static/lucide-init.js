// Wait for the DOM content to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
  console.log('DOM loaded, initializing Lucide icons');

  // Load Lucide from CDN
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
});