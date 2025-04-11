
"""
Industry Report API Module
Handles Twitter/X profile analysis and industry report generation.
"""
import os
import json
import requests
from typing import List, Dict, Any, Optional


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

def uploadIndustryReport(report_data: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Upload an industry report to AstraDB.

    Args:
        report_data (Dict): The industry report data to upload
        user_id (str, optional): The user ID to associate with the report

    Returns:
        Dict: Response from the database with upload status
    """
    print(f"\n=== Industry Report Upload Started ===")

    # Get database credentials from environment
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")

    # Add user_id to report data if provided
    if user_id:
        report_data["user_id"] = user_id

    # Ensure report has a unique ID if not already present
    if "_id" not in report_data:
        import uuid
        report_data["_id"] = str(uuid.uuid4())

    # Add timestamp if not present
    if "created_at" not in report_data:
        from datetime import datetime
        report_data["created_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Prepare the database request
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_industry_reports"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "insertOne": {
            "document": report_data
        }
    }

    try:
        print(f"Uploading industry report to AstraDB...")
        print(f"Report ID: {report_data.get('_id')}")

        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        
        # Check for response length before printing preview
        response_text = response.text
        preview_length = min(200, len(response_text))
        print(f"Response preview: {response_text[:preview_length]}{'...' if len(response_text) > preview_length else ''}")

        response.raise_for_status()
        result = response.json()

        print(f"=== Industry Report Upload Completed ===\n")

        return {
            "status": "success",
            "message": "Industry report uploaded successfully",
            "report_id": report_data.get("_id"),
            "response": result
        }
    except requests.exceptions.RequestException as e:
        print(f"Error uploading industry report: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to upload industry report: {str(e)}"
        }


def getIndustryReports(user_id: str) -> Dict[str, Any]:
    """
    Retrieve industry reports for a specific user.

    Args:
        user_id (str): The user ID to retrieve reports for

    Returns:
        Dict: Response containing the user's industry reports
    """
    print(f"\n=== Getting Industry Reports for User {user_id} ===")

    # Get database credentials from environment
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")

    # Prepare the database request
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_industry_reports"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "filter": {"user_id": user_id},
            "options": {
                "sort": {"created_at": -1}  # Sort by created_at in descending order (newest first)
            }
        }
    }

    try:
        print(f"Fetching industry reports from AstraDB...")

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        reports = result.get("data", {}).get("documents", [])
        print(f"Retrieved {len(reports)} industry reports for user {user_id}")

        return {
            "status": "success",
            "reports": reports
        }
    except Exception as e:
        print(f"Error retrieving industry reports: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to retrieve industry reports: {str(e)}"
        }