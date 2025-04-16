
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
