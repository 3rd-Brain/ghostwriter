import anthropic
from typing import Dict
import os
import uuid
import requests
import json
from urllib.parse import quote
from prompts import Prompts
from openai import OpenAI

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
client = anthropic.Client(api_key=ANTHROPIC_API_KEY)


def social_writer(
    initial_info: Dict,
    completion_params: Dict = None,
) -> Dict:

    if completion_params is None:
        completion_params = {}

    client_brief = initial_info.get('client_brief', '')
    template = initial_info.get('template', '')
    content_chunks = initial_info.get('content_chunks', '')

    prompt = f"""<client_brief>
{client_brief}

<template>
{template}

<content_chunks>
{content_chunks}

Write a social media post based on the information provided. Keep it concise and engaging."""

    response = client.messages.create(model="claude-3-5-sonnet-20241022",
                                      system=Prompts.INITIAL_GENERATION,
                                      messages=[{
                                          "role": "user",
                                          "content": prompt
                                      }],
                                      max_tokens=2048)

    first_draft = response.content[0].text

    prompt = f"""Initial content:
{first_draft}

Refine and polish this content to maximize engagement. Consider optimizing for length, tone, and keywords. Client brief is provided below. Follow the user's brand voice:

{client_brief}"""

    response = client.messages.create(model="claude-3-5-sonnet-20241022",
                                      system=Prompts.CONTENT_REFINEMENT,
                                      messages=[{
                                          "role": "user",
                                          "content": prompt
                                      }],
                                      max_tokens=2048)

    optimized_content = response.content[0].text

    return {
        "first_draft": first_draft,
        "optimized_content": optimized_content,
        "content_chunks": content_chunks,
        "template": template,
        "client_brief": client_brief
    }


def generated_content_uploader(content_data: Dict) -> Dict:
    """
    Upload generated content to Airtable
    """
    AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
    AIRTABLE_BASE_ID = "appLz2zuN6ZFu4mYS"
    AIRTABLE_TABLE_NAME = "Generated Content"

    content = content_data.get("first_draft", "")
    content_chunks = content_data.get("content_chunks", "")
    template = content_data.get("template", "")

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "records": [{
            "fields": {
                "Content_ID": str(uuid.uuid4()),
                "First Draft": content,
                "Tag": "Legacy Generation Flow with Claude",
                "Content Format": "Short Form Social",
                "Status": "Draft",
                "Source Chunk": content_chunks,
                "Template": template,
                "Counter": 1,
                "Content Author": "AI Generated"
            }
        }]
    }

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to upload to Airtable: {str(e)}")


def get_client_brand_voice(username: str) -> Dict:
    """
    Retrieve client brand voice information from Airtable
    """
    AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
    if not AIRTABLE_API_KEY:
        raise Exception("AIRTABLE_API_KEY not configured")

    encoded_username = quote(username)
    url = f"https://api.airtable.com/v0/appLz2zuN6ZFu4mYS/tblpQGTYUROOEYPrY?filterByFormula=%7BAccount+(User)%7D%3D'{encoded_username}'"

    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        if not data.get("records"):
            raise Exception(f"No brand voice found for username: {username}")

        # Extract specifically the Brand Voice field
        brand_voice = data["records"][0]["fields"].get("Brand Voice")
        if not brand_voice:
            raise Exception(f"No brand voice found for username: {username}")
        return {"brand_voice": brand_voice}

    except requests.exceptions.RequestException as e:
        raise Exception(
            f"Failed to retrieve brand voice from Airtable: {str(e)}")

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
        print(f"AstraDB API response:")
        print(f"Request payload: {json.dumps(payload, indent=2)}")
        print(f"Response: {json.dumps(response_data, indent=2)}")
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
import datetime

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
        model="gpt-4-0125-preview",
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
        model="gpt-4-0125-preview",
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

def multitemplate_retriever(content_chunk: str) -> Dict:
    """
    Retrieve template documents based on content chunk using vector search
    Args:
        content_chunk: String containing the content to find templates for
    Returns:
        Dictionary containing template search results
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")

    # Get template description from Claude
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        system=Prompts.TEMPLATE_DESCRIPTION,
        messages=[{"role": "user", "content": content_chunk}],
        max_tokens=2048
    )
    template_description = response.content[0].text

    # Generate embedding for the template description
    response = openai_client.embeddings.create(
        input=template_description,
        model="text-embedding-3-small"
    )
    vector = response.data[0].embedding

    # Prepare search request
    url = "https://42ac68c8-bfd9-4149-ab5c-a5212153b560-us-east-2.apps.astra.datastax.com/api/json/v1/default_keyspace/templates_shortform"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "sort": {"$vector": vector},
            "options": {
                "limit": 5
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve templates: {str(e)}")

def short_form_social_repurposing(topic_query: str, username: str) -> Dict:
    """
    Repurpose content based on topic query and user's brand voice
    Args:
        topic_query: String containing the topic to search for
        username: String containing the username for brand voice
    Returns:
        Dictionary with status message
    """
    print("\n=== Starting Content Repurposing Process ===")

    # Step 1: Get source content
    source_results = source_content_retriever(topic_query)

    # Extract first three content chunks
    content_chunks = []
    if source_results.get("data", {}).get("documents"):
        content_chunks = [doc["content"] for doc in source_results["data"]["documents"][:3]]

    combined_chunks = "\n\n".join(content_chunks)
    print("\n=== Extracted Content Chunks ===")
    print(combined_chunks)

    # Step 2: Get templates
    template_results = multitemplate_retriever(combined_chunks)
    print("\n=== Template Search Results ===")
    print(json.dumps(template_results, indent=2))

    # Step 3: Get brand voice
    brand_voice = get_client_brand_voice(username)
    print("\n=== Retrieved Brand Voice ===")
    print(json.dumps(brand_voice, indent=2))

    # Return early with status message
    result = {"status": "Your content is being generated"}

    # Step 4: Generate content for each template
    if template_results.get("data", {}).get("documents"):
        templates = template_results["data"]["documents"][:5]  # Get first 5 templates

        for template in templates:
            initial_info = {
                "client_brief": brand_voice["brand_voice"],
                "template": template["content"],
                "content_chunks": combined_chunks
            }

            content_result = social_writer(initial_info)
            print(f"\n--- Content Generated Using Template ---")
            print(f"Template: {template['content']}")
            print(f"First Draft: {content_result['first_draft']}")
            print(f"Optimized Content: {content_result['optimized_content']}")

            # Extract template without variations by splitting on "|" and taking first part
            template_base = template["content"].split("|")[0].strip()

            # Prepare content data for upload
            content_data = {
                "first_draft": content_result["first_draft"],
                "content_chunks": combined_chunks,
                "template": template_base
            }

            # Upload the generated content
            upload_result = generated_content_uploader(content_data)
            print(f"\n--- Content Upload Result ---")
            print(json.dumps(upload_result, indent=2))

    return result

def source_content_retriever(topic_query: str) -> str:
    """
    Retrieve source content based on topic query using vector search
    Args:
        topic_query: String containing the topic to search for
    Returns:
        String containing concatenated text chunks from search results
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")

    # Generate embedding for the topic query
    response = openai_client.embeddings.create(
        input=topic_query,
        model="text-embedding-3-small"
    )
    vector = response.data[0].embedding

    # Prepare search request
    url = "https://168d1caf-ef22-4f69-a1a0-2e771cbd41bf-us-east-2.apps.astra.datastax.com/api/json/v1/default_keyspace/source_content"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "sort": {"$vector": vector},
            "options": {
                "limit": 5
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to retrieve source content: {str(e)}")

def templatizer_short_form(template: str) -> Dict:
    """
    Process a template by generating a description with Claude and creating a vector embedding
    Args:
        template: String containing the template for a short form social post
    Returns:
        Dictionary with vector embedding and combined text
    """
    print("\n=== Starting Template Processing ===")
    print(f"Input template: {template}")

    # Generate template description using Claude
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        system="You are a professional content writer analyzing social media post templates. Describe the given template's structure, ideal use cases, and best practices for using it effectively. Be specific about what type of content works best with this template.",
        messages=[{"role": "user", "content": template}],
        max_tokens=2048
    )
    template_description = response.content[0].text
    print(f"\n=== Generated Template Description ===\n{template_description}")

    # Combine template and description
    combined_text = f"{template}|{template_description}"
    print(f"\n=== Combined Text ===\n{combined_text}")

    # Generate vector embedding
    embedding_response = openai_client.embeddings.create(
        input=combined_text,
        model="text-embedding-3-small"
    )
    vector = embedding_response.data[0].embedding

    return {
        "vector": vector,
        "combined_text": combined_text
    }

def top_content_to_repurposing(query: str, topic: str, username: str) -> Dict:
    """
    Get top 5 posts and repurpose each one using short_form_social_repurposing
    Args:
        query: String for searching top content (e.g. "Repurpose my most high-performing tweets")
        topic: String containing topic to search for (e.g. "Digital Operations")
        username: String containing the username for brand voice
    Returns:
        Dictionary with status of repurposing process
    """
    # Get top content using existing retriever
    results = top_content_retriever(query, topic)

    # Process top 5 posts
    status_messages = []
    if results.get("data", {}).get("documents"):
        top_posts = [doc.get("content", "") for doc in results["data"]["documents"][:5]]

        # Iterate through posts and repurpose each one
        for post in top_posts:
            try:
                result = short_form_social_repurposing(post, username)
                status_messages.append(f"Processed post: {post[:50]}...")
            except Exception as e:
                status_messages.append(f"Failed to process post: {str(e)}")

    return {
        "status": "Completed repurposing of top posts",
        "details": status_messages
    }