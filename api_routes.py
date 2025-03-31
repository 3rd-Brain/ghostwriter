
from fastapi import APIRouter, Depends, HTTPException
from api_middleware import get_current_api_user, get_admin_api_user, check_api_key_or_jwt
from schemas import SuccessResponse

router = APIRouter(prefix="/api", tags=["API"])

@router.get("/protected", response_model=SuccessResponse)
async def protected_endpoint(current_user: dict = Depends(get_current_api_user)):
    """
    A protected endpoint that requires a valid API key.
    
    This endpoint demonstrates basic API key authentication.
    The user must provide a valid API key in the X-API-Key header.
    """
    return {
        "status": "success",
        "message": f"Authenticated as user {current_user.get('user_id')} with scope {current_user.get('scope')}"
    }

@router.get("/admin", response_model=SuccessResponse)
async def admin_endpoint(admin_user: dict = Depends(get_admin_api_user)):
    """
    An admin-only endpoint that requires an API key with admin scope.
    
    This endpoint demonstrates role-based API key authentication.
    The user must provide a valid API key with 'admin' scope in the X-API-Key header.
    """
    return {
        "status": "success",
        "message": f"Authenticated as admin user {admin_user.get('user_id')}"
    }

@router.get("/flexible", response_model=SuccessResponse)
async def flexible_auth_endpoint(user: dict = Depends(check_api_key_or_jwt)):
    """
    An endpoint that accepts either API key or JWT authentication.
    
    This endpoint demonstrates flexible authentication.
    The user can authenticate with either an API key or a JWT token.
    """
    auth_method = user.get("auth_source", "unknown")
    return {
        "status": "success",
        "message": f"Authenticated as user {user.get('user_id')} using {auth_method}"
    }
