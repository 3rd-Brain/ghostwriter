from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from api_middleware import get_current_api_user, get_admin_api_user, check_api_key_or_jwt
from schemas import SuccessResponse
import os
import requests
from pydantic import BaseModel
from social_writer import extractProfileTopTweets, topTweetsToTemplate

class ProfileURLRequest(BaseModel):
    profile_url: str

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

@router.post("/top-tweets-to-template", tags=["Brand Management"])
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

@router.get("/user/profile")
async def get_user_profile(current_user: dict = Depends(get_current_api_user)):
    """Retrieves the user's profile information, including Twitter connection status."""
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