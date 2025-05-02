from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
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


@router.get("/protected",
            response_model=SuccessResponse,
            include_in_schema=False)
async def protected_endpoint(
        current_user: dict = Depends(get_current_api_user)):
    """
    A protected endpoint that requires a valid API key.

    This endpoint demonstrates basic API key authentication.
    The user must provide a valid API key in the X-API-Key header.
    """
    return {
        "status":
        "success",
        "message":
        f"Authenticated as user {current_user.get('user_id')} with scope {current_user.get('scope')}"
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


@router.get("/flexible",
            response_model=SuccessResponse,
            include_in_schema=False)
async def flexible_auth_endpoint(user: dict = Depends(check_api_key_or_jwt)):
    """
    An endpoint that accepts either API key or JWT authentication.

    This endpoint demonstrates flexible authentication.
    The user can authenticate with either an API key or a JWT token.
    """
    auth_method = user.get("auth_source", "unknown")
    return {
        "status":
        "success",
        "message":
        f"Authenticated as user {user.get('user_id')} using {auth_method}"
    }


@router.post("/extract-top-tweets", tags=["Utility"])
async def extract_top_tweets(request: ProfileURLRequest,
                             user: dict = Depends(check_api_key_or_jwt)):
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
            raise HTTPException(
                status_code=500,
                detail="APIFY_API_TOKEN not configured in environment")

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
            if len(path_parts
                   ) >= 3:  # Format is documents/user_id/file_id/filename
                file_id = path_parts[2]
                filename = path_parts[3] if len(path_parts) > 3 else file_id

                # Get metadata if available
                try:
                    metadata = storage_client.get_metadata(obj.name)
                    uploaded_at = metadata.get('created', None)
                except:
                    uploaded_at = None

                files.append({
                    "name":
                    filename,
                    "path":
                    obj.name,
                    "file_id":
                    file_id,
                    "uploaded_at":
                    uploaded_at or obj.updated_at.isoformat() if hasattr(
                        obj, 'updated_at') else None
                })

        return {"status": "success", "files": files}

    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Error retrieving storage files: {str(e)}")


@router.get("/file-preview", tags=["Storage"])
async def get_file_preview(path: str,
                           user: dict = Depends(check_api_key_or_jwt)):
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
            raise HTTPException(status_code=403,
                                detail="Access denied to this file")

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
                return {
                    "status": "error",
                    "message": f"Failed to extract PDF text: {str(e)}"
                }
        elif file_extension == 'docx':
            # DOCX files need text extraction
            import io
            from docx import Document

            file_bytes = storage_client.download_as_bytes(path)
            docx_file = io.BytesIO(file_bytes)

            try:
                doc = Document(docx_file)
                content = "\n".join(
                    [paragraph.text for paragraph in doc.paragraphs])
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Failed to extract DOCX text: {str(e)}"
                }
        else:
            return {
                "status": "error",
                "message": "Preview not available for this file type"
            }

        return {"status": "success", "content": content}
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Error retrieving file preview: {str(e)}")


@router.delete("/delete-file", tags=["Storage"])
async def delete_file(request: dict,
                      user: dict = Depends(check_api_key_or_jwt)):
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
            raise HTTPException(status_code=400,
                                detail="File path is required")

        # Initialize the storage client
        storage_client = Client()
        user_id = user.get("user_id")

        # Verify the file belongs to the user (security check)
        if not path.startswith(f"documents/{user_id}/"):
            raise HTTPException(status_code=403,
                                detail="Access denied to this file")

        # Delete the file
        storage_client.delete(path)

        return {"status": "success", "message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Error deleting file: {str(e)}")


# Template Management endpoints
@router.post("/top-tweets-to-template", tags=["Template Management"])
async def top_tweets_to_template(request: ProfileURLRequest,
                                 background_tasks: BackgroundTasks,
                                 user: dict = Depends(check_api_key_or_jwt)):
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
            raise HTTPException(
                status_code=500,
                detail="APIFY_API_TOKEN not configured in environment")

        # First, extract top tweets
        tweets_data = extractProfileTopTweets(request.profile_url)
        total_tweets = len(tweets_data)

        # Add the template generation task to background
        background_tasks.add_task(topTweetsToTemplate, request.profile_url)

        # Return immediate success response
        return {
            "status": "success",
            "message":
            f"Processing {total_tweets} tweets in the background. Template generation has started.",
            "profile_url": request.profile_url,
            "total_tweets": total_tweets
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Brand Management endpoints
@router.post("/create-brand-from-twitter", tags=["Brand Management"])
async def create_brand_from_twitter(
    request: CreateBrandRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(check_api_key_or_jwt)):
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
    *Processing happens in the background for a better user experience.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(
                status_code=500,
                detail="APIFY_API_TOKEN not configured in environment")

        # Check for ANTHROPIC_API_KEY
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise HTTPException(
                status_code=500,
                detail="ANTHROPIC_API_KEY not configured in environment")

        # Call the extractProfileTopTweets function to check if profile exists
        from social_writer import extractProfileTopTweets
        tweets_data = extractProfileTopTweets(request.profile_url)
        total_tweets = len(tweets_data)

        if total_tweets == 0:
            return {
                "status":
                "error",
                "message":
                "No tweets found in this profile. Please try another profile."
            }

        # Set the current user ID in environment
        os.environ["CURRENT_USER_ID"] = user.get("user_id")

        # Add the brand creation task to background tasks
        from social_writer import createBrandFromAccount
        background_tasks.add_task(createBrandFromAccount,
                                  profile_url=request.profile_url,
                                  brand_name=request.brand_name)

        # Return immediate success response
        return {
            "status": "success",
            "message":
            f"Processing {total_tweets} tweets in the background. Brand voice creation has started.",
            "profile_url": request.profile_url,
            "tweet_count": total_tweets
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Industry Report Management endpoints
@router.post("/industry-report/upload", tags=["Industry Report Management"])
async def upload_industry_report(request: IndustryReportUploadRequest,
                                 user: dict = Depends(check_api_key_or_jwt)):
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
        return {
            "status": "error",
            "message": "User ID not found in authentication context"
        }

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
        return {
            "status": "error",
            "message": "User ID not found in authentication context"
        }

    # Call the getIndustryReports function with the user_id
    result = getIndustryReports(user_id)
    return result


@router.post("/industry-report", tags=["Industry Report Management"])
async def generate_industry_report(request: TwitterProfilesRequest,
                                   user: dict = Depends(check_api_key_or_jwt)):
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
        return {
            "status": "error",
            "message": "No Twitter/X profile URLs provided"
        }

    # Get the user ID from the authenticated user
    user_id = user.get("user_id")
    if not user_id:
        return {
            "status": "error",
            "message": "User ID not found in authentication context"
        }

    # Call the generateReport function with the user_id
    result = generateReport(request.twitter_urls, user_id)
    return result


# User Management endpoints
@router.get("/user/profile", tags=["User Management"])
async def get_user_profile(current_user: dict = Depends(check_api_key_or_jwt)):
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
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get(
            "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        payload = {"findOne": {"filter": {"user_id": current_user["user_id"]}}}

        print("Sending DB request...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"DB response status code: {response.status_code}")
        response.raise_for_status()

        user_data = response.json()
        print(
            f"DB response structure keys: {list(user_data.keys()) if user_data else 'None'}"
        )

        if "data" in user_data:
            print(f"Has data key: True")
            data_obj = user_data["data"]
            print(
                f"Data object keys: {list(data_obj.keys()) if data_obj else 'None'}"
            )

            if "document" in data_obj:
                print(f"Has document key: True")
                doc = data_obj["document"]
                print(f"Document keys: {list(doc.keys()) if doc else 'None'}")

                if "profile" in doc:
                    profile = doc.get("profile", {})
                    print(f"Profile object: {profile}")
                    print(
                        f"twitter_processed in profile: {'twitter_processed' in profile}"
                    )
                    print(
                        f"twitter_processed value: {profile.get('twitter_processed')}"
                    )
                else:
                    print("Profile key missing in document")

                # Return profile data
                return {"status": "success", "profile": doc.get("profile", {})}
            else:
                print("Document key missing in data object")
        else:
            print("Data key missing in response")

        # If we reach here, something is wrong with the response structure
        print(f"Full response for debugging: {user_data}")
        return {
            "status": "error",
            "message": "User profile not found",
            "debug_response": user_data
        }
    except Exception as e:
        print(f"Exception in get_user_profile: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}


@router.get("/user/social-profiles", tags=["User Management"])
async def get_user_social_profiles(
        current_user: dict = Depends(check_api_key_or_jwt)):
    try:
        user_id = current_user.get("user_id")

        # Fetch user data from database
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get(
            "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }

        payload = {"findOne": {"filter": {"user_id": user_id}}}

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if not data.get("data", {}).get("document"):
            return {"status": "error", "message": "User not found"}

        # Extract social profiles
        user_data = data.get("data", {}).get("document", {})
        profile_data = user_data.get("profile", {})
        social_profiles = profile_data.get("socials", {})

        return {"status": "success", "social_profiles": social_profiles}

    except Exception as e:
        print(f"Error fetching social profiles: {str(e)}")
        raise HTTPException(status_code=500,
                            detail="Failed to fetch social profiles")


@router.post("/user/social-profiles", tags=["User Management"])
async def update_user_social_profiles(
    profiles: dict, current_user: dict = Depends(check_api_key_or_jwt)):
    try:
        user_id = current_user.get("user_id")

        # Get environment variables
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get(
            "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

        # Update user in database
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }

        payload = {
            "updateOne": {
                "filter": {
                    "user_id": user_id
                },
                "update": {
                    "$set": {
                        "profile.socials": profiles
                    }
                }
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Count connected socials for response
        connected_count = sum(1 for value in profiles.values() if value)

        return {
            "status": "success",
            "message": "Social profiles updated successfully",
            "connected_count": connected_count
        }

    except Exception as e:
        print(f"Error updating social profiles: {str(e)}")
        raise HTTPException(status_code=500,
                            detail="Failed to update social profiles")


@router.delete("/source-content", tags=["Content Management"])
async def delete_source_content_endpoint(
    filename: str, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Delete source content from AstraDB for a specific file**

    This endpoint deletes all source content associated with a specific filename from the database.

    ## When to use
    Use this endpoint when you need to:
    * Remove specific file content from your knowledge base
    * Delete outdated or incorrect source material
    * Clean up content after file deletion

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from source_content_manager import delete_source_content

        # Get the user ID from the authenticated user
        user_id = user.get("user_id")
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in authentication context")

        print(f"\n=== Debug: Delete Source Content API ===")
        print(f"User ID: {user_id}")
        print(f"Filename to delete: {filename}")

        # Call the delete_source_content function
        result = delete_source_content(user_id, filename)

        # Check the deletion count
        deleted_count = result.get("status", {}).get("deletedCount", 0)

        if deleted_count > 0:
            return {
                "status": "success",
                "message":
                f"Successfully deleted {deleted_count} source content documents for file '{filename}'",
                "deleted_count": deleted_count
            }
        else:
            return {
                "status": "warning",
                "message": f"No source content found for file '{filename}'",
                "deleted_count": 0
            }

    except Exception as e:
        print(f"Error deleting source content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/purge-user/{user_id}", tags=["Test"])
async def purge_user(user_id: str,
                     current_user: dict = Depends(check_api_key_or_jwt)):
    """
    **Completely purge a user and all their data**

    This endpoint deletes all user data from all databases, including:
    - User account
    - API keys
    - Brand information
    - Generated content
    - Industry reports
    - Source content
    - Templates
    - Twitter publications
    - Workflows

    ## When to use
    Use this endpoint when you need to:
    * Permanently remove all traces of a user from the system
    * Delete your own account and all associated data
    * Comply with data deletion requests
    * Perform complete account cleanup

    *This action cannot be undone and ALL user data across ALL systems will be permanently deleted.*
    """
    try:
        # Security check: users can only purge their own account, admins can purge any account
        authenticated_user_id = current_user.get("user_id")
        is_admin = current_user.get("scope") == "admin"

        if not is_admin and authenticated_user_id != user_id:
            raise HTTPException(
                status_code=403,
                detail=
                "You can only delete your own account unless you have admin privileges"
            )

        from admin_functions import complete_user_purge

        print(f"\n=== Debug: User Purge Request ===")
        print(f"Authenticated User ID: {authenticated_user_id}")
        print(f"User ID to purge: {user_id}")
        print(f"Is Admin Request: {is_admin}")

        # Call the complete_user_purge function
        result = complete_user_purge(user_id)

        print(f"Purge completed with status: {result.get('status')}")
        return result
    except Exception as e:
        print(f"Error purging user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Keep the admin endpoint for backward compatibility
@router.delete("/admin/purge-user/{user_id}", tags=["User Management"])
async def admin_purge_user(user_id: str,
                           admin_user: dict = Depends(get_admin_api_user)):
    """
    **Admin-only endpoint to completely purge a user and all their data**

    This endpoint deletes all user data from all databases, including:
    - User account
    - API keys
    - Brand information
    - Generated content
    - Industry reports
    - Source content
    - Templates
    - Twitter publications
    - Workflows

    ## When to use
    Use this endpoint when you need to:
    * Permanently remove all traces of a user from the system
    * Comply with data deletion requests
    * Perform complete account cleanup

    *This action cannot be undone and requires admin privileges.
    ALL user data across ALL systems will be permanently deleted.*
    """
    try:
        from admin_functions import complete_user_purge

        print(f"\n=== Debug: Admin Purge User Request ===")
        print(f"Admin ID: {admin_user.get('user_id')}")
        print(f"User ID to purge: {user_id}")

        # Call the complete_user_purge function
        result = complete_user_purge(user_id)

        print(f"Purge completed with status: {result.get('status')}")
        return result
    except Exception as e:
        print(f"Error purging user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/template/{template_id}", tags=["Template Management"])
async def delete_template_endpoint(template_id: str,
                                   db_to_access: str = "user",
                                   user: dict = Depends(check_api_key_or_jwt)):
    """
    **Delete a template from the database**

    This endpoint deletes a template from either the system templates or user templates database.

    ## When to use
    Use this endpoint when you need to:
    * Remove unwanted templates from your library
    * Clean up your template collection

    ## Required Parameters
    * `template_id`: The ID of the template to delete
    * `db_to_access`: Which database to delete from ("sys", "user")

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from social_writer import delete_template

        print(f"\n=== Debug: Delete Template Request ===")
        print(f"User ID: {user.get('user_id')}")
        print(f"Template ID to delete: {template_id}")
        print(f"Database to access: {db_to_access}")

        # Set the current user ID in environment
        os.environ["CURRENT_USER_ID"] = user.get("user_id")

        # For "both" option, try deleting from both databases
        if db_to_access.lower() == "both":
            # Try user database first
            try:
                user_result = delete_template(template_id, "user")
                if user_result.get("status", {}).get("deletedCount", 0) > 0:
                    return {
                        "status": "success",
                        "message":
                        "Template deleted successfully from user templates",
                        "database": "user"
                    }
            except Exception as e:
                print(f"Error deleting from user database: {str(e)}")

            # Then try system database
            try:
                sys_result = delete_template(template_id, "sys")
                if sys_result.get("status", {}).get("deletedCount", 0) > 0:
                    return {
                        "status": "success",
                        "message":
                        "Template deleted successfully from system templates",
                        "database": "sys"
                    }
            except Exception as e:
                print(f"Error deleting from system database: {str(e)}")

            # If we get here, the template wasn't found in either database
            return {
                "status": "error",
                "message": "Template not found in any database"
            }
        else:
            # Delete from the specified database
            result = delete_template(template_id, db_to_access)

            if result.get("status", {}).get("deletedCount", 0) > 0:
                return {
                    "status": "success",
                    "message":
                    f"Template deleted successfully from {db_to_access} database",
                    "database": db_to_access
                }
            else:
                return {
                    "status": "error",
                    "message": f"Template not found in {db_to_access} database"
                }
    except Exception as e:
        print(f"Error deleting template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
