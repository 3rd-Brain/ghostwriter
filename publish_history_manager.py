
import os
import requests
import json
from typing import Dict, List, Any

def retrievePublications(user_id: str) -> Dict[str, Any]:
    """
    Retrieve publications for a specific user from AstraDB
    
    Args:
        user_id: String containing the user ID to retrieve publications for
        
    Returns:
        Dictionary containing the retrieved publication documents
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    # Set up the API request
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_twitter_publications"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "find": {
            "filter": {"user_id": user_id},
            "sort": {"created_at": -1}  # Sort by created_at in descending order (newest first)
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Process the documents to extract relevant fields for the table
        publications = []
        for doc in result.get("data", {}).get("documents", []):
            publication = {
                "id": doc.get("_id", ""),
                "content": doc.get("first_draft", ""),
                "publish_date": doc.get("created_at", ""),
                "impressions": doc.get("metrics", {}).get("impressions", 0),
                "likes": doc.get("metrics", {}).get("likes", 0),
                "shares": doc.get("metrics", {}).get("shares", 0),
                "quotes": doc.get("metrics", {}).get("quotes", 0),
                "bookmarks": doc.get("metrics", {}).get("bookmarks", 0),
                "replies": doc.get("metrics", {}).get("replies", 0),
                "status": doc.get("status", ""),
                "approval_date": doc.get("Approval_Date", "")
            }
            publications.append(publication)
        
        return {
            "status": "success",
            "publications": publications
        }
    
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving publications: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to retrieve publications: {str(e)}",
            "publications": []
        }

def getPublicationMetrics(publication_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed metrics for a specific publication
    
    Args:
        publication_id: String containing the publication ID to retrieve metrics for
        
    Returns:
        Dictionary containing the publication metrics
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_twitter_publications"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "findOne": {
            "filter": {"_id": publication_id}
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        doc = result.get("data", {}).get("document", {})
        
        # Extract metrics
        metrics = {
            "basic_metrics": {
                "impressions": doc.get("metrics", {}).get("impressions", 0),
                "likes": doc.get("metrics", {}).get("likes", 0),
                "shares": doc.get("metrics", {}).get("shares", 0),
                "quotes": doc.get("metrics", {}).get("quotes", 0),
                "bookmarks": doc.get("metrics", {}).get("bookmarks", 0),
                "replies": doc.get("metrics", {}).get("replies", 0)
            },
            "weighted_metrics": doc.get("weighted_metrics", {}),
            "score": doc.get("score", 0)
        }
        
        return {
            "status": "success",
            "metrics": metrics
        }
    
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving publication metrics: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to retrieve publication metrics: {str(e)}"
        }
