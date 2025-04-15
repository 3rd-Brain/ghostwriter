
// Token refresh handler
document.addEventListener('DOMContentLoaded', function() {
    // Set up automatic token refresh
    function setupTokenRefresh() {
        // Check for token expiration every minute
        setInterval(function() {
            // Only call refresh if we're close to token expiration (after 14 minutes)
            // We don't have direct access to token expiry on client side, so we assume worst case
            fetch('/api/refresh-token')
                .then(response => {
                    if (!response.ok) {
                        console.log('Token refresh failed, may need to login again');
                    } else {
                        console.log('Access token refreshed');
                    }
                })
                .catch(error => {
                    console.error('Error refreshing token:', error);
                });
        }, 840000); // 14 minutes in milliseconds
    }
    
    // Call this function when page loads
    setupTokenRefresh();
});
