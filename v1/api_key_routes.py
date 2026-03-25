
from fastapi import APIRouter, Depends, HTTPException
from api_middleware import get_current_api_user, get_admin_api_user
from api_auth import create_api_key, get_user_api_keys, deactivate_api_key, delete_api_key
from schemas import ApiKeyCreateRequest, ApiKeyResponse, ApiKeyListResponse, SuccessResponse
from main import get_current_user

router = APIRouter(prefix="/api/keys", tags=["API Keys"])

@router.post("", response_model=ApiKeyResponse)
async def create_key(
    request: ApiKeyCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new API key for the authenticated user.
    
    This endpoint allows users to generate new API keys for accessing the API.
    The key will only be shown once upon creation.
    """
    try:
        # Get user ID from the authenticated user
        user_id = current_user["user_id"]
        
        # Create API key
        key_data = create_api_key(
            user_id=user_id,
            name=request.name,
            scope=request.scope
        )
        
        return key_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=ApiKeyListResponse)
async def list_keys(current_user: dict = Depends(get_current_user)):
    """
    List all API keys for the authenticated user.
    
    This endpoint returns information about all API keys owned by the user,
    but does not include the actual key values for security reasons.
    """
    user_id = current_user["user_id"]
    keys = get_user_api_keys(user_id)
    return {"keys": keys}

@router.delete("/{key_id}", response_model=SuccessResponse)
async def revoke_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoke (deactivate) an API key.
    
    This endpoint allows users to deactivate an API key they own.
    Deactivated keys will no longer work for authentication.
    """
    success = deactivate_api_key(key_id)
    if success:
        return {"status": "success", "message": "API key revoked successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to revoke API key")

@router.delete("/{key_id}/permanent", response_model=SuccessResponse)
async def delete_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Permanently delete an API key.
    
    This endpoint allows users to completely delete an API key they own.
    This action cannot be undone.
    """
    success = delete_api_key(key_id)
    if success:
        return {"status": "success", "message": "API key deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete API key")
