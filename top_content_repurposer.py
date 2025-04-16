import os
import json
import requests
from typing import Dict

def top_published_posts_retriever(user_id: str) -> Dict:
    """
    Retrieve top published posts for a user from AstraDB

    Args:
        user_id: String containing the user's ID

    Returns:
        Dictionary containing the response from AstraDB
    """
    # Get AstraDB credentials from environment
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Prepare request
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_twitter_publications"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "filter": {"user_id": user_id},
            "sort": {
                "score": -1
            }
        }
    }

    try:
        print(f"Sending request to AstraDB for user_id: {user_id}")
        print(f"Request URL: {url}")
        print(f"Request payload: {json.dumps(payload, indent=2)}")

        # Execute request
        response = requests.post(url, headers=headers, json=payload)

        # Log response status
        print(f"Response status code: {response.status_code}")

        # Print truncated response
        response_text = response.text
        print(f"Response preview: {response_text[:1000]}{'...' if len(response_text) > 1000 else ''}")

        # Raise exception for non-2xx responses
        response.raise_for_status()

        # Parse and return result
        result = response.json()
        return result

    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"Error response status: {e.response.status_code}")
            print(f"Error response text: {e.response.text[:200]}...")

        raise Exception(f"Failed to retrieve top posts: {str(e)}")