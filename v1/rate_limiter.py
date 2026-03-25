
import time
from typing import Callable, Dict, Optional, Tuple, Union
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import threading
import os

# In-memory storage for rate limiting
class InMemoryStore:
    def __init__(self):
        self.storage = {}
        self.lock = threading.Lock()
        
    def get(self, key):
        with self.lock:
            return self.storage.get(key, (0, 0))  # (count, expiry)
            
    def increment(self, key, expiry):
        with self.lock:
            count, _ = self.storage.get(key, (0, 0))
            count += 1
            self.storage[key] = (count, expiry)
            return count
            
    def ttl(self, key):
        with self.lock:
            _, expiry = self.storage.get(key, (0, 0))
            now = time.time()
            return max(0, expiry - now)

# Initialize in-memory store
store = InMemoryStore()

# Clean up expired items periodically
def cleanup_expired():
    now = time.time()
    with store.lock:
        for key in list(store.storage.keys()):
            _, expiry = store.storage[key]
            if now > expiry:
                del store.storage[key]
    
    # Schedule next cleanup
    threading.Timer(60.0, cleanup_expired).start()

# Start cleanup thread
cleanup_thread = threading.Timer(60.0, cleanup_expired)
cleanup_thread.daemon = True
cleanup_thread.start()

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for rate limiting based on API keys or JWT tokens
    with in-memory storage as a backend.
    """
    
    def __init__(self, app, rate_limit_per_hour: int = 1000):
        super().__init__(app)
        self.rate_limit_per_hour = rate_limit_per_hour
        # Convert to requests per second for more granular control
        self.rate_limit_per_second = rate_limit_per_hour / 3600
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for certain paths or methods
        if request.method == "OPTIONS":
            return await call_next(request)
            
        # Skip rate limiting for common page loads to improve UX
        excluded_paths = [
            "/dashboard", 
            "/settings", 
            "/generate-content",
            "/static/",
            "/login",
            "/source-content-management",
            "/generation/",
            "/template-management",
            "/content-approval",
            "/publish-history",
            "/api-keys"
        ]
        
        # Check if the current path should be excluded
        current_path = request.url.path
        for path in excluded_paths:
            if current_path.startswith(path):
                return await call_next(request)
            
        # Get identifier from either API key or JWT
        identifier = self._get_identifier(request)
        
        # If we couldn't identify the user, let the request through
        # The authentication middleware will handle it
        if not identifier:
            return await call_next(request)
            
        # Check rate limit
        allowed, reset_time, remaining = self._check_rate_limit(identifier)
        
        if not allowed:
            # Return 429 Too Many Requests
            reset_seconds = int(reset_time - time.time())
            return Response(
                content=f"Rate limit exceeded. Try again in {reset_seconds} seconds.",
                status_code=429,
                headers={
                    "X-RateLimit-Limit": str(self.rate_limit_per_hour),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                    "Retry-After": str(reset_seconds)
                }
            )
            
        # Process the request
        response = await call_next(request)
        
        # Add rate limit headers to the response
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit_per_hour)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time - time.time()))
        
        return response
    
    def _get_identifier(self, request: Request) -> Optional[str]:
        """Extract user identifier from request (API key or JWT)"""
        # Try to get API key from header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api:{api_key}"
            
        # Try to get JWT from cookie
        # This is a simplified approach; you might need to decode the JWT
        jwt_token = request.cookies.get("access_token")
        if jwt_token:
            return f"jwt:{jwt_token}"
            
        # If no identifiers found, use IP address as fallback
        client_ip = request.client.host if request.client else None
        if client_ip:
            return f"ip:{client_ip}"
            
        return None
    
    def _check_rate_limit(self, identifier: str) -> Tuple[bool, float, int]:
        """
        Check if the user has exceeded their rate limit
        
        Returns:
            Tuple containing:
            - Boolean indicating if request is allowed
            - Time when the rate limit resets (timestamp)
            - Number of requests remaining
        """
        # Create key for this user
        key = f"ratelimit:{identifier}"
        
        # Get current time
        now = time.time()
        
        # Calculate window expiry (1 hour from now)
        window_expiry = now + 3600
        
        # Get current count and ttl from store
        count, old_expiry = store.get(key)
        
        # If key doesn't exist or expired, reset count
        if now > old_expiry:
            count = 0
            
        # Get ttl
        ttl = window_expiry - now if count == 0 else store.ttl(key)
        
        # Calculate when the window resets
        reset_time = now + ttl
        
        # Check if we're over the limit
        if count >= self.rate_limit_per_hour:
            return False, reset_time, 0
        
        # Increment the counter
        count = store.increment(key, window_expiry)
        
        # Calculate remaining requests
        remaining = self.rate_limit_per_hour - count
        
        return True, reset_time, remaining
