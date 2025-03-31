
import time
from typing import Callable, Dict, Optional, Tuple, Union
import redis
from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
import os

# Initialize Redis client
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = redis.from_url(REDIS_URL)

# Initialize slowapi limiter
limiter = Limiter(key_func=get_remote_address)

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware for rate limiting based on API keys or JWT tokens
    with Redis as a backend store.
    """
    
    def __init__(self, app, rate_limit_per_hour: int = 300):
        super().__init__(app)
        self.rate_limit_per_hour = rate_limit_per_hour
        # Convert to requests per second for more granular control
        self.rate_limit_per_second = rate_limit_per_hour / 3600
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for certain paths or methods
        if request.method == "OPTIONS":
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
        # Create Redis key for this user
        key = f"ratelimit:{identifier}"
        
        # Get current time
        now = time.time()
        
        # Calculate window expiry (1 hour from now)
        window_expiry = now + 3600
        
        # Get current count and expiry time from Redis
        pipe = redis_client.pipeline()
        pipe.get(key)
        pipe.ttl(key)
        count_bytes, ttl = pipe.execute()
        
        # Convert count from bytes to int if it exists
        count = int(count_bytes) if count_bytes else 0
        
        # If key doesn't exist or TTL is -1 (no expiry), set expiry to 1 hour
        if ttl < 0:
            pipe.expire(key, 3600)
            pipe.execute()
            ttl = 3600
        
        # Calculate when the window resets
        reset_time = now + ttl
        
        # Check if we're over the limit
        if count >= self.rate_limit_per_hour:
            return False, reset_time, 0
        
        # Increment the counter
        redis_client.incr(key)
        
        # Calculate remaining requests
        remaining = self.rate_limit_per_hour - count - 1
        
        return True, reset_time, remaining
