
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

def top_content_retriever(filter_query: str, user_id: str) -> Dict:
    """
    Process user query to get filtered and sorted content from user's Twitter publications
    Args:
        filter_query: String containing the search query (e.g. "Find top posts of the week")
        user_id: String containing the user's ID
    Returns:
        Dictionary containing filtered and sorted content
    """
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")
    
    # Get filter and metric sort from sentiment setup
    setup_result = top_content_sentiment_setup(filter_query)
    metadata_filter = setup_result.get("filter", {})
    metric_sort = setup_result.get("metric_sort")
    
    print(f"Generated filter parameters for query: '{filter_query}'")
    print(f"Filter: {metadata_filter}")
    print(f"Metric sort: {metric_sort}")
    
    # Handle filter structure and add metadata prefix to appropriate fields
    metadata_fields = [
        "weighted_impression_ratio", "weighted_like_ratio", 
        "weighted_bookmark_ratio", "weighted_retweet_ratio", 
        "weighted_reply_ratio", "total_weight_metric",
        "post_id", "published_date"
    ]

    def process_filter(filter_obj):
        if isinstance(filter_obj, dict):
            new_obj = {}
            for key, value in filter_obj.items():
                if key in ['$and', '$or']:
                    new_obj[key] = [process_filter(item) for item in value]
                elif key in metadata_fields:
                    new_obj[f"metadata.{key}"] = value
                else:
                    new_obj[key] = process_filter(value) if isinstance(value, dict) else value
            return new_obj
        return filter_obj

    processed_filter = process_filter(metadata_filter)
    
    # Add user_id to filter
    if "$and" in processed_filter:
        processed_filter["$and"].append({"user_id": user_id})
    else:
        processed_filter = {
            "$and": [
                processed_filter,
                {"user_id": user_id}
            ]
        }
    
    # Get API endpoint from environment
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    
    # Get application token for Ghostwriter
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    # Prepare database request
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_twitter_publications"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }
    
    payload = {
        "find": {
            "filter": processed_filter,
            "options": {
                "limit": 1000
            }
        }
    }
    
    try:
        print(f"Sending request to AstraDB: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        response = requests.post(url, headers=headers, json=payload)
        print(f"AstraDB Response Status: {response.status_code}")
        
        response.raise_for_status()
        result = response.json()
        
        # Sort results by the chosen metric if present
        if metric_sort and result.get("data", {}).get("documents"):
            result = metric_sorter(result, metric_sort)
            
        return result
    except requests.exceptions.RequestException as e:
        print(f"AstraDB Error: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"Response Status: {e.response.status_code}")
            print(f"Response Body: {e.response.text}")
        raise Exception(f"Failed to retrieve user content: {str(e)}")

def top_content_to_repurposing(query: str, brand: str, numberOfPostsToRepurpose: int = 5, repurpose_count: int = 1, workflow_id: str = "Legacy Generation Flow") -> Dict:
    """
    Get top posts and repurpose each one multiple times using short_form_social_repurposing
    Args:
        query: String for searching top content (e.g. "Repurpose my most high-performing tweets")
        brand: String containing the brand for brand voice
        numberOfPostsToRepurpose: Number of top posts to repurpose (default: 5)
        repurpose_count: Number of times to repurpose each post (default: 1)
        workflow_id: String containing the workflow ID for generation
    Returns:
        Dictionary with status of repurposing process
    """
    # Get user ID from environment
    user_id = os.environ.get("CURRENT_USER_ID")
    if not user_id:
        raise Exception("CURRENT_USER_ID not configured")
    
    # Get top content using updated retriever
    results = top_content_retriever(query, user_id)
    print("Results from top_content_retriever:", results)

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
