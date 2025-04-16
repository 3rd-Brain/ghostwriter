
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

def vector_search_for_published_content(metadata_filter: Dict, text_to_vectorize: str) -> Dict:
    """
    Perform vector search for published content using OpenAI embeddings
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")

    # Generate embedding for the input text
    response = openai_client.embeddings.create(
        input=text_to_vectorize,
        model="text-embedding-3-small"
    )
    vector = response.data[0].embedding
    print(f"Generated embedding for text: '{text_to_vectorize}'")
    print(f"Embedding vector (first 5 dimensions): {vector[:5]}...")
    print(f"Embedding dimension: {len(vector)}")

    # Prepare search request
    url = "https://d468cd02-85c9-4ee8-9bd3-3dc123ddf2ac-us-east-2.apps.astra.datastax.com/api/json/v1/default_keyspace/published_content"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

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

    payload = {
        "find": {
            "filter": processed_filter,
            "sort": {"$vector": vector},
            "options": {
                "limit": 1000
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        response_data = response.json()
        return response_data
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to perform vector search: {str(e)}")

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

def top_content_retriever(query: str, topic: str) -> Dict:
    """
    Process user query to get filtered and sorted content
    Args:
        query: String containing the search query (e.g. "Find top posts of the week")
        topic: String containing the topic to vectorize (e.g. "Digital Operations")
    Returns:
        Dictionary containing filtered and sorted content
    """
    # Get filter and metric sort from sentiment setup
    setup_result = top_content_sentiment_setup(query)

    # Use vector search with the filter, but vectorize the topic
    search_result = vector_search_for_published_content(
        metadata_filter=setup_result["filter"],
        text_to_vectorize=topic
    )

    # Sort results by the chosen metric if present
    if "metric_sort" in setup_result and search_result:
        return metric_sorter(search_result, setup_result["metric_sort"])
    return search_result

def top_content_to_repurposing(query: str, topic: str, brand: str, numberOfPostsToRepurpose: int = 5, repurpose_count: int = 1, workflow_id: str = "Legacy Generation Flow") -> Dict:
    """
    Get top posts and repurpose each one multiple times using short_form_social_repurposing
    Args:
        query: String for searching top content (e.g. "Repurpose my most high-performing tweets")
        topic: String containing topic to search for (e.g. "Digital Operations")
        brand: String containing the brand for brand voice
        numberOfPostsToRepurpose: Number of top posts to repurpose (default: 5)
        repurposeCount: Number of times to repurpose each post (default: 5)
        workflow_id: String containing the workflow ID for generation
    Returns:
        Dictionary with status of repurposing process
    """
    # Get top content using existing retriever
    results = top_content_retriever(query, topic)
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

    return {
        "status": "Completed repurposing of top posts",
        "details": status_messages
    }
