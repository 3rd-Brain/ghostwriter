
"""
Industry Report API Module
Handles Twitter/X profile analysis and industry report generation.
"""
import os
import json
import requests
from typing import List, Dict, Any


def extract_handle_from_url(url: str) -> str:
    """
    Extract the handle/username from a Twitter/X URL.
    
    Args:
        url (str): Twitter/X profile URL
        
    Returns:
        str: The extracted handle or empty string if not found
    """
    import re
    handle_match = re.search(r'(?:twitter|x)\.com\/([^\/\?]+)', url)
    return handle_match.group(1) if handle_match else ""


def generateReport(twitter_urls: List[str], user_id: str = None) -> Dict[str, Any]:
    """
    Generate an industry report based on provided Twitter/X profile URLs.
    
    Args:
        twitter_urls (List[str]): List of Twitter/X profile URLs to analyze
        user_id (str, optional): ID of the currently logged in user
        
    Returns:
        Dict: Response from the webhook API
    """
    print(f"Generating report for {len(twitter_urls)} Twitter/X profiles")
    
    # Prepare the payload
    payload = {
        "user_id": user_id,
        "profiles": []
    }
    
    for url in twitter_urls:
        handle = extract_handle_from_url(url)
        if handle:
            payload["profiles"].append({
                "url": url,
                "handle": handle
            })
    
    # Only proceed if we have valid profiles
    if not payload["profiles"]:
        return {"status": "error", "message": "No valid Twitter/X profiles provided"}
    
    print(f"Prepared payload with {len(payload['profiles'])} profiles for user {payload['user_id']}")
    
    # Make the API call to the webhook
    try:
        response = requests.post(
            'https://n8n.3rdbrainhosting.com/webhook/IndustryGenStart',
            headers={'Content-Type': 'application/json'},
            json=payload,
            timeout=30
        )
        
        # Check response status
        response.raise_for_status()
        result = response.json()
        
        print(f"Report generation initiated successfully")
        return {
            "status": "success", 
            "message": "Industry report generation started", 
            "response": result
        }
    except requests.exceptions.RequestException as e:
        print(f"Error starting report generation: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to start report generation: {str(e)}"
        }
