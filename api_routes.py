
# Add these routes to your api_routes.py file

@app.get("/api/user/social-profiles")
async def get_user_social_profiles(current_user: dict = Depends(get_current_user)):
    try:
        user_id = current_user.get("_id")
        
        # Fetch user data from database
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "findOne": {
                "filter": {"_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("document"):
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "User not found"}
            )
        
        # Extract social profiles
        user_data = data.get("document", {})
        social_profiles = {
            "podcast": user_data.get("podcast_url", ""),
            "youtube": user_data.get("youtube_url", ""),
            "twitter": user_data.get("twitter_url", ""),
            "linkedin": user_data.get("linkedin_url", ""),
            "newsletter": user_data.get("newsletter_url", ""),
            "website": user_data.get("website_url", "")
        }
        
        return {"status": "success", "social_profiles": social_profiles}
    
    except Exception as e:
        print(f"Error fetching social profiles: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to fetch social profiles"}
        )

@app.post("/api/user/social-profiles")
async def update_user_social_profiles(
    profiles: dict,
    current_user: dict = Depends(get_current_user)
):
    try:
        user_id = current_user.get("_id")
        
        # Prepare update data
        update_data = {
            "podcast_url": profiles.get("podcast", ""),
            "youtube_url": profiles.get("youtube", ""),
            "twitter_url": profiles.get("twitter", ""),
            "linkedin_url": profiles.get("linkedin", ""),
            "newsletter_url": profiles.get("newsletter", ""),
            "website_url": profiles.get("website", "")
        }
        
        # Update user in database
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "updateOne": {
                "filter": {"_id": user_id},
                "update": {"$set": update_data}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        # Count connected socials for response
        connected_count = sum(1 for value in update_data.values() if value)
        
        return {
            "status": "success", 
            "message": "Social profiles updated successfully",
            "connected_count": connected_count
        }
    
    except Exception as e:
        print(f"Error updating social profiles: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Failed to update social profiles"}
        )

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from api_middleware import get_current_api_user, get_admin_api_user, check_api_key_or_jwt
from schemas import SuccessResponse
import os
import requests
from typing import List, Dict, Any
from pydantic import BaseModel
from social_writer import extractProfileTopTweets, topTweetsToTemplate

class ProfileURLRequest(BaseModel):
    profile_url: str

router = APIRouter(prefix="/api")

class TwitterProfilesRequest(BaseModel):
    twitter_urls: List[str]

class IndustryReportUploadRequest(BaseModel):
    user_id: str = None
    webViewLink: str = None
    IndustryInsights: Dict[str, Any]
    OverallInsights: Any  # Accept any type instead of string


@router.get("/protected", response_model=SuccessResponse, include_in_schema=False)
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

@router.get("/admin", response_model=SuccessResponse, include_in_schema=False)
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

@router.get("/flexible", response_model=SuccessResponse, include_in_schema=False)
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

@router.post("/extract-top-tweets", tags=["Utility"])
async def extract_top_tweets(request: ProfileURLRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Extract top tweets from a Twitter/X profile**

    This endpoint extracts top tweets from a Twitter/X profile by their engagement metrics.

    ## When to use
    Use this endpoint when you need to:
    * Analyze a Twitter/X user's best performing content
    * Research content strategy for a Twitter/X profile
    * Find popular tweets from specific accounts

    ## Required Input
    * `profile_url`: A valid Twitter/X profile URL (e.g., "https://x.com/elonmusk")

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured in environment")

        # Call the extractProfileTopTweets function
        result = extractProfileTopTweets(request.profile_url)

        # Return the results
        return {
            "status": "success",
            "profile_url": request.profile_url,
            "tweet_count": len(result),
            "tweets": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CreateBrandRequest(BaseModel):
    profile_url: str
    brand_name: str = None

# Storage endpoints
@router.get("/storage-files", tags=["Storage"])
async def get_storage_files(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Get files from Object Storage for the current user**

    This endpoint retrieves a list of files stored in the user's object storage directory.

    ## When to use
    Use this endpoint when you need to:
    * View all files uploaded to object storage
    * Manage your uploaded documents

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from replit.object_storage import Client

        # Initialize the storage client
        storage_client = Client()
        user_id = user.get("user_id")

        # List all objects with prefix for user's directory
        prefix = f"documents/{user_id}/"
        objects = storage_client.list(prefix=prefix)

        # Process the objects to create a file list
        files = []
        for obj in objects:
            # Skip directory markers or empty items
            if obj.name.endswith('/') or not obj.name:
                continue

            # Extract filename from path
            path_parts = obj.name.split('/')
            if len(path_parts) >= 3:  # Format is documents/user_id/file_id/filename
                file_id = path_parts[2]
                filename = path_parts[3] if len(path_parts) > 3 else file_id

                # Get metadata if available
                try:
                    metadata = storage_client.get_metadata(obj.name)
                    uploaded_at = metadata.get('created', None)
                except:
                    uploaded_at = None

                files.append({
                    "name": filename,
                    "path": obj.name,
                    "file_id": file_id,
                    "uploaded_at": uploaded_at or obj.updated_at.isoformat() if hasattr(obj, 'updated_at') else None
                })

        return {
            "status": "success",
            "files": files
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving storage files: {str(e)}")

@router.get("/file-preview", tags=["Storage"])
async def get_file_preview(path: str, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Get a preview of a file from Object Storage**

    This endpoint retrieves the content of a file for preview purposes.

    ## When to use
    Use this endpoint when you need to:
    * Preview a file's contents before processing
    * View the raw text of uploaded files

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from replit.object_storage import Client

        # Initialize the storage client
        storage_client = Client()
        user_id = user.get("user_id")

        # Verify the file belongs to the user (security check)
        if not path.startswith(f"documents/{user_id}/"):
            raise HTTPException(status_code=403, detail="Access denied to this file")

        # Get the content based on file type
        file_extension = path.split('.')[-1].lower() if '.' in path else ''

        if file_extension in ['txt', 'md']:
            # Text files can be displayed directly
            content = storage_client.download_as_text(path)
        elif file_extension == 'pdf':
            # PDF files need text extraction
            import io
            import fitz  # PyMuPDF

            file_bytes = storage_client.download_as_bytes(path)
            pdf_file = io.BytesIO(file_bytes)

            try:
                doc = fitz.open(stream=pdf_file, filetype="pdf")
                content = ""
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    content += page.get_text()
                doc.close()
            except Exception as e:
                return {"status": "error", "message": f"Failed to extract PDF text: {str(e)}"}
        elif file_extension == 'docx':
            # DOCX files need text extraction
            import io
            from docx import Document

            file_bytes = storage_client.download_as_bytes(path)
            docx_file = io.BytesIO(file_bytes)

            try:
                doc = Document(docx_file)
                content = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            except Exception as e:
                return {"status": "error", "message": f"Failed to extract DOCX text: {str(e)}"}
        else:
            return {"status": "error", "message": "Preview not available for this file type"}

        return {
            "status": "success",
            "content": content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file preview: {str(e)}")

@router.delete("/delete-file", tags=["Storage"])
async def delete_file(request: dict, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Delete a file from Object Storage**

    This endpoint deletes a file from the user's storage.

    ## When to use
    Use this endpoint when you need to:
    * Remove unwanted files from storage
    * Clean up your storage space

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from replit.object_storage import Client

        # Get the file path from the request
        path = request.get("path")
        if not path:
            raise HTTPException(status_code=400, detail="File path is required")

        # Initialize the storage client
        storage_client = Client()
        user_id = user.get("user_id")

        # Verify the file belongs to the user (security check)
        if not path.startswith(f"documents/{user_id}/"):
            raise HTTPException(status_code=403, detail="Access denied to this file")

        # Delete the file
        storage_client.delete(path)

        return {
            "status": "success",
            "message": "File deleted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

# Template Management endpoints
@router.post("/top-tweets-to-template", tags=["Template Management"])
async def top_tweets_to_template(request: ProfileURLRequest, background_tasks: BackgroundTasks, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Convert top tweets from a Twitter/X profile into templates**

    This endpoint extracts top tweets from a Twitter/X profile, converts them to templates,
    and uploads them to the template database.

    ## When to use
    Use this endpoint when you need to:
    * Learn from high-performing content on Twitter/X
    * Generate templates based on successful tweets
    * Build a library of templates from specific content creators
    * Analyze content patterns from influential accounts

    ## Required Input
    * `profile_url`: A valid Twitter/X profile URL (e.g., "https://x.com/elonmusk")

    *This endpoint supports both JWT and API key authentication.*
    *The processing happens in the background for a better user experience.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured in environment")

        # First, extract top tweets
        tweets_data = extractProfileTopTweets(request.profile_url)
        total_tweets = len(tweets_data)

        # Add the template generation task to background
        background_tasks.add_task(topTweetsToTemplate, request.profile_url)

        # Return immediate success response
        return {
            "status": "success",
            "message": f"Processing {total_tweets} tweets in the background. Template generation has started.",
            "profile_url": request.profile_url,
            "total_tweets": total_tweets
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Brand Management endpoints
@router.post("/create-brand-from-twitter", tags=["Brand Management"])
async def create_brand_from_twitter(request: CreateBrandRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Create a brand voice from a Twitter/X profile**

    This endpoint extracts top tweets from a Twitter/X profile, analyzes them,
    and generates a comprehensive brand voice guide.

    ## When to use
    Use this endpoint when you need to:
    * Generate a brand voice based on an existing Twitter/X personality
    * Create writing guidelines from social media content patterns
    * Analyze the communication style of a specific account

    ## Required Input
    * `profile_url`: A valid Twitter/X profile URL (e.g., "https://x.com/elonmusk")
    * `brand_name`: (Optional) Custom name for the brand

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured in environment")

        # Check for ANTHROPIC_API_KEY
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured in environment")

        # Set the current user ID in environment
        os.environ["CURRENT_USER_ID"] = user.get("user_id")

        # Call the createBrandFromAccount function
        from social_writer import createBrandFromAccount
        result = createBrandFromAccount(
            profile_url=request.profile_url,
            brand_name=request.brand_name
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Industry Report Management endpoints
@router.post("/industry-report/upload", tags=["Industry Report Management"])
async def upload_industry_report(request: IndustryReportUploadRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Upload an industry report to the database**

    This endpoint stores a complete industry report in the database.

    ## When to use
    Use this endpoint when you need to:
    * Store industry reports generated by external systems
    * Update existing industry reports with new data
    * Upload reports from third-party integrations

    ## Required Input
    * `report_data`: A complete JSON document containing the industry report

    *This endpoint supports both JWT and API key authentication.*
    *The user_id in the payload will be used if present, otherwise the authenticated user's ID will be used.*
    """
    from industry_report import uploadIndustryReport

    # Get the user ID from the authenticated user
    auth_user_id = user.get("user_id")
    if not auth_user_id:
        return {"status": "error", "message": "User ID not found in authentication context"}

    # Convert the request object to a dictionary
    report_data = request.dict()
    
    # Extract the user_id from the payload if it exists
    payload_user_id = report_data.get("user_id")
    
    # Determine which user_id to use for the report upload
    # If payload contains a user_id, use that; otherwise use authenticated user's ID
    user_id_to_use = payload_user_id if payload_user_id else auth_user_id
    
    # Set the user_id in the report_data if it's not already there
    if not payload_user_id:
        report_data["user_id"] = auth_user_id
    
    # Call the uploadIndustryReport function with the report data
    # Pass the user_id from the auth context as the second parameter for verification/logging
    result = uploadIndustryReport(report_data, payload_user_id)
    return result

@router.get("/industry-reports", tags=["Industry Report Management"])
async def get_industry_reports(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve industry reports for the current user**

    This endpoint fetches all industry reports associated with the current user.

    ## When to use
    Use this endpoint when you need to:
    * List all available industry reports for a user
    * Display industry report data in a dashboard
    * Access previously generated reports

    *This endpoint supports both JWT and API key authentication.*
    """
    from industry_report import getIndustryReports

    # Get the user ID from the authenticated user
    user_id = user.get("user_id")
    if not user_id:
        return {"status": "error", "message": "User ID not found in authentication context"}

    # Call the getIndustryReports function with the user_id
    result = getIndustryReports(user_id)
    return result

@router.post("/industry-report", tags=["Industry Report Management"])
async def generate_industry_report(request: TwitterProfilesRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Generate an industry report from Twitter/X profiles**

    This endpoint analyzes multiple Twitter/X profiles and generates a comprehensive industry report.

    ## When to use
    Use this endpoint when you need to:
    * Analyze content patterns across multiple Twitter/X accounts
    * Generate insights about an industry or niche based on influencer profiles
    * Research engagement patterns across a group of accounts

    ## Required Input
    * `twitter_urls`: A list of valid Twitter/X profile URLs (e.g., ["https://x.com/elonmusk", "https://x.com/jack"])

    *This endpoint supports both JWT and API key authentication.*
    *Processing happens asynchronously, and you'll receive a notification when the report is ready.*
    """
    from industry_report import generateReport

    # Check if we received any Twitter URLs
    if not request.twitter_urls:
        return {"status": "error", "message": "No Twitter/X profile URLs provided"}

    # Get the user ID from the authenticated user
    user_id = user.get("user_id")
    if not user_id:
        return {"status": "error", "message": "User ID not found in authentication context"}

    # Call the generateReport function with the user_id
    result = generateReport(request.twitter_urls, user_id)
    return result

# User Management endpoints
@router.get("/user/profile", tags=["User Management"])
async def get_user_profile(current_user: dict = Depends(get_current_api_user)):
    """
    **Retrieve the user's profile information**
    
    This endpoint fetches the current user's profile data, including Twitter connection status.
    
    ## When to use
    Use this endpoint when you need to:
    * Access user profile information
    * Check Twitter integration status
    * Retrieve user identity details
    
    *This endpoint requires API key authentication with appropriate permissions.*
    """
    try:
        # Get user data from AstraDB
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        payload = {
            "findOne": {
                "filter": {"user_id": current_user["user_id"]}
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        user_data = response.json()

        # Extract relevant user profile data including twitter_processed status
        profile_data = user_data.get("data", {}).get("document", {}).get("profile", {})
        twitter_processed = profile_data.get("twitter_processed", False)

        return {
            "user_id": current_user["user_id"],
            "username": current_user.get("username"),
            "twitter_processed": twitter_processed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving user profile: {e}")