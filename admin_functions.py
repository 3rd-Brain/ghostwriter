
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


def complete_user_purge(user_id: str) -> Dict:
    """
    Completely purges all user data from all databases.
    This is an irreversible operation that removes:
    - User account from users database
    - All API keys
    - All brands
    - All generated content
    - All industry reports
    - All source content
    - All templates
    - All Twitter publications
    - All workflows
    
    Args:
        user_id: String containing the user's unique identifier
        
    Returns:
        Dictionary containing deletion results for each database
        
    Raises:
        Exception: If deletion fails or database credentials are missing
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: Complete User Purge Started ===")
    print(f"User ID to purge: {user_id}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    # Set up common headers
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Track results for each database
    results = {
        "users": None,
        "api_keys": None,
        "brands": None,
        "generated_content": None,
        "industry_reports": None,
        "source_content": None,
        "templates": None,
        "twitter_publications": None,
        "workflows": None
    }
    
    # 1. Delete from users_keyspace/users
    try:
        print(f"Deleting user account from users database...")
        users_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        users_payload = {
            "deleteOne": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(users_url, headers=headers, json=users_payload)
        response.raise_for_status()
        results["users"] = response.json()
        print(f"User account deleted successfully.")
    except Exception as e:
        print(f"Error deleting user account: {str(e)}")
        results["users"] = {"error": str(e)}
    
    # 2. Delete from users_keyspace/user_api_keys
    try:
        print(f"Deleting user API keys...")
        api_keys_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
        api_keys_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(api_keys_url, headers=headers, json=api_keys_payload)
        response.raise_for_status()
        results["api_keys"] = response.json()
        print(f"User API keys deleted successfully.")
    except Exception as e:
        print(f"Error deleting user API keys: {str(e)}")
        results["api_keys"] = {"error": str(e)}
    
    # 3. Delete from user_content_keyspace/brands
    try:
        print(f"Deleting user brands...")
        brands_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"
        brands_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(brands_url, headers=headers, json=brands_payload)
        response.raise_for_status()
        results["brands"] = response.json()
        print(f"User brands deleted successfully.")
    except Exception as e:
        print(f"Error deleting user brands: {str(e)}")
        results["brands"] = {"error": str(e)}
    
    # 4. Delete from user_content_keyspace/generated_content
    try:
        print(f"Deleting user generated content...")
        generated_content_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/generated_content"
        generated_content_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(generated_content_url, headers=headers, json=generated_content_payload)
        response.raise_for_status()
        results["generated_content"] = response.json()
        print(f"User generated content deleted successfully.")
    except Exception as e:
        print(f"Error deleting user generated content: {str(e)}")
        results["generated_content"] = {"error": str(e)}
    
    # 5. Delete from user_content_keyspace/user_industry_reports
    try:
        print(f"Deleting user industry reports...")
        industry_reports_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_industry_reports"
        industry_reports_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(industry_reports_url, headers=headers, json=industry_reports_payload)
        response.raise_for_status()
        results["industry_reports"] = response.json()
        print(f"User industry reports deleted successfully.")
    except Exception as e:
        print(f"Error deleting user industry reports: {str(e)}")
        results["industry_reports"] = {"error": str(e)}
    
    # 6. Delete from user_content_keyspace/user_source_content
    try:
        print(f"Deleting user source content...")
        source_content_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_source_content"
        source_content_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(source_content_url, headers=headers, json=source_content_payload)
        response.raise_for_status()
        results["source_content"] = response.json()
        print(f"User source content deleted successfully.")
    except Exception as e:
        print(f"Error deleting user source content: {str(e)}")
        results["source_content"] = {"error": str(e)}
    
    # 7. Delete from user_content_keyspace/user_templates
    try:
        print(f"Deleting user templates...")
        templates_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_templates"
        templates_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(templates_url, headers=headers, json=templates_payload)
        response.raise_for_status()
        results["templates"] = response.json()
        print(f"User templates deleted successfully.")
    except Exception as e:
        print(f"Error deleting user templates: {str(e)}")
        results["templates"] = {"error": str(e)}
    
    # 8. Delete from user_content_keyspace/user_twitter_publications
    try:
        print(f"Deleting user Twitter publications...")
        twitter_publications_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_twitter_publications"
        twitter_publications_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(twitter_publications_url, headers=headers, json=twitter_publications_payload)
        response.raise_for_status()
        results["twitter_publications"] = response.json()
        print(f"User Twitter publications deleted successfully.")
    except Exception as e:
        print(f"Error deleting user Twitter publications: {str(e)}")
        results["twitter_publications"] = {"error": str(e)}
    
    # 9. Delete from user_content_keyspace/user_workflows
    try:
        print(f"Deleting user workflows...")
        workflows_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_workflows"
        workflows_payload = {
            "deleteMany": {
                "filter": {"user_id": user_id}
            }
        }
        response = requests.post(workflows_url, headers=headers, json=workflows_payload)
        response.raise_for_status()
        results["workflows"] = response.json()
        print(f"User workflows deleted successfully.")
    except Exception as e:
        print(f"Error deleting user workflows: {str(e)}")
        results["workflows"] = {"error": str(e)}
    
    print(f"=== Debug: Complete User Purge Completed ===\n")
    
    # Prepare summary
    success_count = sum(1 for v in results.values() if v and not isinstance(v, dict) or "error" not in v)
    
    return {
        "status": "success" if success_count == len(results) else "partial_success",
        "message": f"User purge completed. Successfully purged {success_count}/{len(results)} databases.",
        "details": results
    }

        raise Exception(f"Failed to retrieve user from AstraDB: {str(e)}")
