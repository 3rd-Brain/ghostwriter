
from fastapi import APIRouter, Depends, HTTPException
from api_middleware import get_current_api_user
from pydantic import BaseModel, Field
from schemas import SuccessResponse
from typing import Optional, List
import third_party_keys
from main import get_current_user

router = APIRouter(prefix="/api/third-party-keys", tags=["Third Party API Keys"])

class ThirdPartyKeyCreateRequest(BaseModel):
    service: str = Field(..., description="Service name (e.g., 'openai', 'anthropic')")
    api_key: str = Field(..., description="API key to store")
    description: Optional[str] = Field("", description="Optional description")

class ThirdPartyKeyResponse(BaseModel):
    key_id: str = Field(..., description="Unique identifier for the key")
    service: str = Field(..., description="Service name")
    key_prefix: str = Field(..., description="First few characters of the key")
    created_at: str = Field(..., description="Creation timestamp")
    is_active: bool = Field(..., description="Whether the key is active")
    description: Optional[str] = Field("", description="Optional description")

class ThirdPartyKeyListResponse(BaseModel):
    keys: List[ThirdPartyKeyResponse] = Field(..., description="List of third-party API keys")

class ThirdPartyKeyUpdateRequest(BaseModel):
    api_key: str = Field(..., description="New API key value")

@router.post("", response_model=ThirdPartyKeyResponse)
async def create_third_party_key(
    request: ThirdPartyKeyCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Store a third-party API key for the authenticated user.
    
    This endpoint allows users to securely store API keys for external services
    like OpenAI, Anthropic, etc.
    """
    try:
        user_id = current_user["user_id"]
        
        key_data = third_party_keys.store_third_party_key(
            user_id=user_id,
            service=request.service,
            api_key=request.api_key,
            description=request.description
        )
        
        return key_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=ThirdPartyKeyListResponse)
async def list_third_party_keys(current_user: dict = Depends(get_current_user)):
    """
    List all third-party API keys for the authenticated user.
    
    This endpoint returns information about all third-party API keys owned by the user,
    but does not include the actual key values for security reasons.
    """
    user_id = current_user["user_id"]
    keys = third_party_keys.list_third_party_keys(user_id)
    return {"keys": keys}

@router.get("/{service}", response_model=str)
async def get_third_party_key(
    service: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve a specific third-party API key by service name.
    
    This endpoint returns the decrypted API key for use in API calls.
    """
    user_id = current_user["user_id"]
    key = third_party_keys.get_third_party_key(user_id, service)
    
    if not key:
        raise HTTPException(status_code=404, detail=f"No active API key found for service: {service}")
    
    return key

@router.put("/{key_id}", response_model=SuccessResponse)
async def update_third_party_key(
    key_id: str,
    request: ThirdPartyKeyUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a third-party API key.
    
    This endpoint allows users to update the value of an existing API key.
    """
    user_id = current_user["user_id"]
    success = third_party_keys.update_third_party_key(user_id, key_id, request.api_key)
    
    if success:
        return {"status": "success", "message": "API key updated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update API key")

@router.delete("/{key_id}", response_model=SuccessResponse)
async def deactivate_third_party_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Deactivate a third-party API key.
    
    This endpoint allows users to deactivate an API key they own.
    Deactivated keys will no longer work for API calls.
    """
    user_id = current_user["user_id"]
    success = third_party_keys.deactivate_third_party_key(user_id, key_id)
    
    if success:
        return {"status": "success", "message": "API key deactivated successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to deactivate API key")

@router.delete("/{key_id}/permanent", response_model=SuccessResponse)
async def delete_third_party_key(
    key_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Permanently delete a third-party API key.
    
    This endpoint allows users to completely delete an API key they own.
    This action cannot be undone.
    """
    user_id = current_user["user_id"]
    success = third_party_keys.delete_third_party_key(user_id, key_id)
    
    if success:
        return {"status": "success", "message": "API key deleted successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete API key")
