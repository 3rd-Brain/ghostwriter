
import requests
from typing import Literal, Dict, Union
import os

def gather_user_tweets(
    max_items: int,
    sort: Literal["Latest", "Top"],
    user_url: str
) -> Dict:
    """
    Gather tweets from a user's X/Twitter profile using Apify
    
    Args:
        max_items: Maximum number of tweets to retrieve
        sort: Sort order - "Latest" or "Top"
        user_url: Full URL of user's X/Twitter profile
        
    Returns:
        Dict containing the Twitter data response
    """
    APIFY_API_TOKEN = os.environ.get("APIFY_API_TOKEN")
    
    if not APIFY_API_TOKEN:
        raise Exception("APIFY_API_TOKEN not configured in environment")
        
    # Apify endpoint
    url = "https://api.apify.com/v2/actor-tasks/james-3rdbrain~twitter-x-com-scraper-unlimited-ghostwriter/run-sync-get-dataset-items"
    
    # Request headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # Request parameters
    params = {
        "token": APIFY_API_TOKEN
    }
    
    # Request payload
    payload = {
        "maxItems": max_items,
        "sort": sort,
        "startUrls": [user_url]
    }
    
    try:
        response = requests.post(url, headers=headers, params=params, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to gather tweets: {str(e)}")
