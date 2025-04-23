
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
import os
from api_middleware import check_api_key_or_jwt
from scrapers import scrape_linkedin_posts, scrape_youtube_videos, scrape_youtube_single_video

router = APIRouter(prefix="/api")

# Request Models
class LinkedInProfileRequest(BaseModel):
    profile_url: str = Field(..., description="URL or username of the LinkedIn profile")
    max_posts: int = Field(50, description="Maximum number of posts to retrieve")

class YouTubeChannelRequest(BaseModel):
    channel_url: str = Field(..., description="URL of the YouTube channel to scrape")
    max_videos: int = Field(20, description="Maximum number of videos to retrieve")
    sort_by: str = Field("POPULAR", description="How to sort videos - 'POPULAR' or 'NEWEST'")

class YouTubeVideoRequest(BaseModel):
    video_url: str = Field(..., description="URL of the YouTube video to extract transcript from")

# Endpoints
@router.post("/scrape/linkedin", tags=["Scrapers"])
async def linkedin_scraper(request: LinkedInProfileRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Scrape posts from a LinkedIn profile**
    
    This endpoint extracts recent posts from a LinkedIn profile using the Apify API.
    
    ## When to use
    Use this endpoint when you need to:
    * Analyze LinkedIn content from specific profiles
    * Extract engagement metrics from LinkedIn posts
    * Research content patterns from LinkedIn influencers
    
    ## Required Input
    * `profile_url`: LinkedIn profile URL or username
    * `max_posts`: Maximum number of posts to retrieve (default: 50)
    
    *This endpoint supports both JWT and API key authentication.*
    *Requires APIFY_API_TOKEN to be configured in environment variables.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured in environment")
        
        # Call the scraper function
        result = scrape_linkedin_posts(request.profile_url, request.max_posts)
        
        # Return the results
        return {
            "status": "success",
            "profile_url": request.profile_url,
            "post_count": len(result) if isinstance(result, list) else 0,
            "posts": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape/youtube/channel", tags=["Scrapers"])
async def youtube_channel_scraper(request: YouTubeChannelRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Scrape videos and transcripts from a YouTube channel**
    
    This endpoint extracts videos and their transcripts from a YouTube channel using the Apify API.
    
    ## When to use
    Use this endpoint when you need to:
    * Extract content from YouTube channels
    * Analyze video transcripts for content research
    * Gather engagement data from YouTube creators
    
    ## Required Input
    * `channel_url`: URL of the YouTube channel to scrape
    * `max_videos`: Maximum number of videos to retrieve (default: 20)
    * `sort_by`: How to sort videos - "POPULAR" or "NEWEST" (default: "POPULAR")
    
    *This endpoint supports both JWT and API key authentication.*
    *Requires APIFY_API_TOKEN to be configured in environment variables.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured in environment")
        
        # Call the scraper function
        result = scrape_youtube_videos(request.channel_url, request.max_videos, request.sort_by)
        
        # Return the results
        return {
            "status": "success",
            "channel_url": request.channel_url,
            "video_count": len(result) if isinstance(result, list) else 0,
            "videos": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/scrape/youtube/video", tags=["Scrapers"])
async def youtube_video_scraper(request: YouTubeVideoRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Extract transcript from a YouTube video**
    
    This endpoint extracts the transcript from a YouTube video using the Apify API.
    
    ## When to use
    Use this endpoint when you need to:
    * Get the full transcript of a YouTube video
    * Extract content from specific videos for analysis
    * Research video content without watching the video
    
    ## Required Input
    * `video_url`: URL of the YouTube video to extract transcript from
    
    *This endpoint supports both JWT and API key authentication.*
    *Requires APIFY_API_TOKEN to be configured in environment variables.*
    """
    try:
        # Check for APIFY API token
        if not os.environ.get("APIFY_API_TOKEN"):
            raise HTTPException(status_code=500, detail="APIFY_API_TOKEN not configured in environment")
        
        # Call the scraper function
        result = scrape_youtube_single_video(request.video_url)
        
        # Return the results
        return {
            "status": "success",
            "video_url": request.video_url,
            "video_data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
