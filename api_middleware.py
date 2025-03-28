
from fastapi import Depends, HTTPException, Header, Request, status
from typing import Optional
from api_auth import verify_api_key

async def get_api_key_header(x_api_key: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency to extract the API key from the header.
    
    Args:
        x_api_key: API key from the X-API-Key header
        
    Returns:
        The API key if valid
        
    Raises:
        HTTPException: If the API key is invalid or missing
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key missing",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return x_api_key

async def get_current_api_user(
    x_api_key: str = Depends(get_api_key_header)
) -> dict:
    """
    FastAPI dependency to validate the API key and return the user.
    
    Args:
        x_api_key: API key from the header
        
    Returns:
        User details if the API key is valid
        
    Raises:
        HTTPException: If the API key is invalid
    """
    user = verify_api_key(x_api_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return user

async def get_admin_api_user(
    current_user: dict = Depends(get_current_api_user)
) -> dict:
    """
    FastAPI dependency to validate the API key has admin scope.
    
    Args:
        current_user: User details from API key validation
        
    Returns:
        User details if the API key has admin scope
        
    Raises:
        HTTPException: If the API key doesn't have admin scope
    """
    if current_user.get("scope") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user

async def check_api_key_or_jwt(request: Request):
    """
    Flexible authentication that checks for either API key or JWT.
    This allows both API clients and web UI users to authenticate.
    
    Args:
        request: The FastAPI request object
        
    Returns:
        User details dictionary
        
    Raises:
        HTTPException: If neither authentication method is valid
    """
    # Try API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        user = verify_api_key(api_key)
        if user:
            # Add a source field to indicate this is API authentication
            user["auth_source"] = "api_key"
            return user
    
    # Fall back to JWT cookie
    from main import get_current_user  # Import here to avoid circular imports
    try:
        jwt_user = await get_current_user(request)
        jwt_user["auth_source"] = "jwt"
        return jwt_user
    except HTTPException:
        # If both methods fail, raise the API key error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication",
            headers={"WWW-Authenticate": "ApiKey, Bearer"},
        )
