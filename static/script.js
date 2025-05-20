
// Token refresh handler
document.addEventListener('DOMContentLoaded', function() {
    // Set up automatic token refresh
    function setupTokenRefresh() {
        // First, refresh token immediately to ensure we have a fresh session
        refreshToken();
        
        // Then set up regular refreshes (every 5 minutes)
        setInterval(refreshToken, 300000); // 5 minutes in milliseconds
    }
    
    function refreshToken() {
        fetch('/api/refresh-token', {
            method: 'GET',
            credentials: 'include' // Important: include cookies in the request
        })
        .then(response => {
            if (!response.ok) {
                console.warn('Token refresh failed, may need to login again');
            } else {
                console.log('Access token refreshed at', new Date().toISOString());
            }
        })
        .catch(error => {
            console.error('Error refreshing token:', error);
        });
    }
    
    // Call this function when page loads
    setupTokenRefresh();
    
    // Also refresh on visibility change (when tab becomes active again)
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'visible') {
            refreshToken();
        }
    });
});

// Check if the user needs to set up API keys
function checkApiKeyRequirement() {
    fetch('/api/key-requirement-status')
        .then(response => response.json())
        .then(data => {
            if (data.requires_keys) {
                // Show notification to user that they need to set up API keys
                showNotification('Please set up your API keys in Settings to use AI features', true, 10000);
                
                // Add a visual indicator that keys are required
                const keyIndicator = document.createElement('div');
                keyIndicator.className = 'key-setup-required';
                keyIndicator.innerHTML = '<i data-lucide="key-alert"></i>';
                keyIndicator.title = 'API keys required';
                
                // Add click handler to go to settings
                keyIndicator.addEventListener('click', function() {
                    window.location.href = '/settings#api-keys-tab';
                });
                
                // Add to navbar if it doesn't exist already
                if (!document.querySelector('.key-setup-required')) {
                    document.querySelector('.navbar-items').appendChild(keyIndicator);
                    lucide.createIcons();
                }
            }
        })
        .catch(error => {
            console.error('Error checking API key requirement:', error);
        });
}

// Call this when the page loads for pages that use AI features
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on a page that uses AI features
    const aiFeaturePages = [
        '/generate-content',
        '/generation/repurpose',
        '/generation/top-content',
        '/generation/posts-templates'
    ];
    
    const currentPath = window.location.pathname;
    
    if (aiFeaturePages.some(page => currentPath.includes(page))) {
        checkApiKeyRequirement();
    }
});
