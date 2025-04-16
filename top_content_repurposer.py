import os
import json
import requests
import datetime
from typing import Dict, List
from openai import OpenAI
from prompts import Prompts
from social_writer import short_form_social_repurposing

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# AstraDB configuration
ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN")

def get_current_utc():
    """Get current UTC time as formatted string"""
    return datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def top_content_sentiment_setup(query: str) -> Dict:
    """
    Process user query to generate filter and metric sort parameters
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")

    # Append UTC time to query
    utc_time = get_current_utc()
    augmented_query = f"{query} | Date Today: {utc_time}"

    # Generate filter using first system prompt
    filter_response = openai_client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": Prompts.FILTER_GENERATION},
            {"role": "user", "content": augmented_query}
        ],
        response_format={"type": "json_object"}
    )

    try:
        filter_content = filter_response.choices[0].message.content.strip()
        metadata_filter = json.loads(filter_content)
    except json.JSONDecodeError as e:
        print(f"Failed to parse filter response: {filter_content}")
        raise Exception(f"Invalid JSON in filter response: {str(e)}")

    # Generate metric sort using second system prompt
    metric_response = openai_client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": Prompts.METRIC_SELECTION},
            {"role": "user", "content": query}
        ]
    )

    metric_sort = metric_response.choices[0].message.content.strip()

    return {
        "filter": metadata_filter,
        "metric_sort": metric_sort
    }

def metric_sorter(published_content: Dict, sort_metric: str) -> Dict:
    """
    Sort published content by specified metric in descending order
    """
    if not published_content.get("data", {}).get("documents"):
        return published_content

    # Sort documents by the specified metric
    sorted_documents = sorted(
        published_content["data"]["documents"],
        key=lambda x: x.get("metadata", {}).get(sort_metric, 0),
        reverse=True
    )

    return {
        "data": {
            "documents": sorted_documents,
            "nextPageState": published_content["data"].get("nextPageState")
        }
    }

import os
import json
import requests
from typing import Dict

def top_posts_retriever(user_id: str) -> Dict:
    """
    Retrieve top posts for a user from AstraDB

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

def top_content_to_repurposing(query: str, brand: str, numberOfPostsToRepurpose: int = 5, repurpose_count: int = 5, workflow_id: str = "Legacy Generation Flow") -> Dict:
    """
    Get top posts and repurpose each one multiple times using short_form_social_repurposing
    Args:
        query: String for searching top content (e.g. "Repurpose my most high-performing tweets")
        brand: String containing the brand for brand voice
        numberOfPostsToRepurpose: Number of top posts to repurpose (default: 5)
        repurpose_count: Number of times to repurpose each post (default: 5)
        workflow_id: String containing the workflow ID for generation
    Returns:
        Dictionary with status of repurposing process
    """
    # Get user ID from environment
    user_id = os.environ.get("CURRENT_USER_ID")
    if not user_id:
        raise Exception("CURRENT_USER_ID not configured")
    
    # Get top content using updated retriever
    results = top_posts_retriever(user_id)
    print("Results from top_posts_retriever:", results)

    # Process posts
    status_messages = []
    if results.get("data", {}).get("documents"):
        top_posts = [doc.get("content", "") for doc in results["data"]["documents"][:numberOfPostsToRepurpose]]

        # Iterate through posts and repurpose each one
        for post in top_posts:
            try:
                print("Starting: ", post)
                result = short_form_social_repurposing(post, brand, repurpose_count, workflow_id)
                status_messages.append(f"Processed post: {post[:50]}...")
            except Exception as e:
                status_messages.append(f"Failed to process post: {str(e)}")
    else:
        status_messages.append("No top content found or vector search functionality is unavailable.")
        print("No documents found in results. Vector search functionality has been removed.")

    return {
        "status": "Completed repurposing of top posts",
        "details": status_messages
    }