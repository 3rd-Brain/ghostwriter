
# Admin functionality for Ghostwriter API

import os
import requests
from typing import Dict, Optional
from fastapi import HTTPException

def delete_user(user_id: str) -> Dict:
    """
    Delete a user account from the database by user_id.
    
    Args:
        user_id: The unique identifier of the user to delete
        
    Returns:
        Dictionary containing the deletion result
        
    Raises:
        Exception: If the deletion fails or database credentials are missing
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: User Deletion Started ===")
    print(f"User ID to delete: {user_id}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create the delete payload
    payload = {
        "deleteOne": {
            "filter": {
                "user_id": user_id
            }
        }
    }
    
    try:
        print(f"Sending delete request to AstraDB...")
        print(f"Request URL: {url}")
        print(f"Request payload: {payload}")
        
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        
        # Log truncated response for debugging
        response_text = response.text
        print(f"Response preview: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
        
        response.raise_for_status()
        result = response.json()
        print(f"=== Debug: User Deletion Completed ===\n")
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to delete user from AstraDB: {str(e)}")

def get_all_users(limit: int = 100, skip: int = 0) -> Dict:
    """
    Retrieve all users from the database with pagination.
    
    Args:
        limit: Maximum number of users to retrieve
        skip: Number of users to skip (for pagination)
        
    Returns:
        Dictionary containing the users
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create the find payload with pagination
    payload = {
        "find": {
            "options": {
                "limit": limit,
                "skip": skip
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        return result
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve users from AstraDB: {str(e)}")

def get_user_by_id(user_id: str) -> Optional[Dict]:
    """
    Retrieve a user by their user_id.
    
    Args:
        user_id: The unique identifier of the user
        
    Returns:
        User document or None if not found
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create the findOne payload
    payload = {
        "findOne": {
            "filter": {
                "user_id": user_id
            }
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        return result.get("data", {}).get("document")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve user from AstraDB: {str(e)}")
