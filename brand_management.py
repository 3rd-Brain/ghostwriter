
from fastapi import APIRouter, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import requests
import uuid
from datetime import datetime
from typing import Dict, Optional
from api_middleware import check_api_key_or_jwt
from main import get_current_user

# Create router
router = APIRouter()

# Templates configuration
templates = Jinja2Templates(directory="templates")

@router.get("/brand-management", response_class=HTMLResponse, include_in_schema=False)
async def brand_management_page(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Render the brand management page
    """
    return templates.TemplateResponse("brand_management.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "brand_management"
    })

@router.post("/api/create-brand", tags=["Brand Management"])
async def create_brand(
    brand_name: str = Form(...),
    brand_voice: str = Form(...),
    sample_content: str = Form(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new brand for the current user
    """
    # Get environment variables for AstraDB
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        raise HTTPException(status_code=500, detail="Database configuration error")

    # Generate brand_id
    brand_id = str(uuid.uuid4())
    
    # Create the document
    document = {
        "_id": str(uuid.uuid4()),
        "brand_id": brand_id,
        "user_id": current_user["user_id"],
        "brand_name": brand_name,
        "brand_voice": brand_voice,
        "sample_content": sample_content or "",
        "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    }
    
    # Prepare the API request to AstraDB
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "insertOne": {
            "document": document
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return {"status": "success", "message": f"Brand '{brand_name}' created successfully", "brand_id": brand_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create brand: {str(e)}")

@router.delete("/api/delete-brand/{brand_id}", tags=["Brand Management"])
async def delete_brand(brand_id: str, current_user: dict = Depends(get_current_user)):
    """
    Delete a brand by brand_id, ensuring it belongs to the current user
    """
    # Get environment variables for AstraDB
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        raise HTTPException(status_code=500, detail="Database configuration error")

    # Prepare the API request to AstraDB
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Only allow deletion if the brand belongs to the current user
    payload = {
        "deleteOne": {
            "filter": {
                "$and": [
                    {"brand_id": brand_id},
                    {"user_id": current_user["user_id"]}
                ]
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Check if any document was deleted
        if result.get("status", {}).get("deletedCount", 0) > 0:
            return {"status": "success", "message": "Brand deleted successfully"}
        else:
            return {"status": "error", "message": "Brand not found or you don't have permission to delete it"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete brand: {str(e)}")

@router.get("/api/brand/{brand_id}", tags=["Brand Management"])
async def get_brand(brand_id: str, current_user: dict = Depends(get_current_user)):
    """
    Get details of a specific brand by brand_id
    """
    # Get environment variables for AstraDB
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        raise HTTPException(status_code=500, detail="Database configuration error")

    # Prepare the API request to AstraDB
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Only allow retrieval if the brand belongs to the current user
    payload = {
        "findOne": {
            "filter": {
                "$and": [
                    {"brand_id": brand_id},
                    {"user_id": current_user["user_id"]}
                ]
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Check if a document was found
        if result.get("data", {}).get("document"):
            return {"status": "success", "brand": result["data"]["document"]}
        else:
            raise HTTPException(status_code=404, detail="Brand not found or you don't have permission to access it")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve brand: {str(e)}")
