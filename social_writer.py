import anthropic
from typing import Dict, List
import os
import uuid
import requests
import json
import datetime
from urllib.parse import quote
from prompts import Prompts
from openai import OpenAI
from social_dynamic_generation_flow import social_post_generation_with_json

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN")
ASTRA_DB_APPLICATION_TOKEN_FOR_SOURCES = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_FOR_SOURCES")
ASTRA_DB_APPLICATION_TOKEN_FOR_SHORTFORM_TEMPLATES = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_FOR_SHORTFORM_TEMPLATES")

openai_client = OpenAI(api_key=OPENAI_API_KEY)
client = anthropic.Client(api_key=ANTHROPIC_API_KEY)

def generated_content_uploader(content_data: Dict) -> Dict:
    """
    Upload generated content to AstraDB

    Args:
        content_data: Dictionary containing content information with the following keys:
            - first_draft: The initial content generated
            - content_chunks: Source content used for generation
            - template: Template used (or template_id if available)
            - brand_id: (Optional) ID of the brand used
            - template_id: (Optional) ID reference to system templates
            - workflow_id: (Optional) ID of the workflow used for generation

    Returns:
        Dictionary with the database response
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    print(f"\n=== Debug: Generated Content Uploader Started ===")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN not configured")

    # Get the current user's ID from the environment
    user_id = os.environ.get("CURRENT_USER_ID")
    if not user_id:
        raise Exception("CURRENT_USER_ID not configured")

    # Extract content data
    first_draft = content_data.get("first_draft", "")
    source_chunks = content_data.get("content_chunks", "")
    template = content_data.get("template", "")
    template_id = content_data.get("template_id", "")  # New field
    brand_id = content_data.get("brand_id", "")  # New field
    workflow_id = content_data.get("workflow_id", "")
    workflow_name = content_data.get("workflow_name", "Legacy Generation Flow")
    content_format = content_data.get("content_format", "Short Form Social")

    # Set the URL for the new collection path
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/generated_content"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    # Generate UUID for post_id if not provided
    post_id = content_data.get("post_id", str(uuid.uuid4()))

    # Create a timestamp for created_at
    created_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Create document with new structure
    document = {
        "post_id": post_id,
        "user_id": user_id,
        "first_draft": first_draft,
        "current_draft": "",
        "template_id": template_id,
        "template": template,
        "source_chunks": source_chunks,
        "brand_id": brand_id,
        "status": "Draft",
        "created_at": created_at,
        "workflow_name": workflow_name,
        "workflow_id": workflow_id,
        "content_format": content_format,
        "metrics": {
            "likes": 0,
            "shares": 0,
            "quotes": 0,
            "bookmarks": 0,
            "replies": 0,
            "impressions": 0
        },
        "weighted_metrics": {
            "weighted_likes": 0,
            "weighted_shares": 0,
            "weighted_bookmarks": 0,
            "weighted_replies": 0,
            "weighted_impressions": 0
        },
        "score": 0
    }

    payload = {
        "insertOne": {
            "document": document
        }
    }

    print(f"\n=== Debug: Content Upload Started ===")
    print(f"URL: {url}")
    print(f"Payload (truncated): {str(payload)[:200]}...")

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        response.raise_for_status()
        result = response.json()
        print(f"=== Debug: Content Upload Completed ===\n")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Upload error: {str(e)}")
        raise Exception(f"Failed to upload to AstraDB: {str(e)}")


def get_client_brand_voice(brand: str, user_id: str = None) -> Dict:
    """
    Retrieve client brand voice information from AstraDB

    Args:
        brand: String containing the brand name to search for
        user_id: String containing the user ID (if None, will use current user from environment)

    Returns:
        Dictionary containing brand voice information
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    print(f"\n=== Debug: Brand Voice Request Started ===")
    print(f"Brand: {brand}")
    print(f"ASTRA_DB_API_ENDPOINT configured: {'Yes' if ASTRA_DB_API_ENDPOINT else 'No'}")
    print(f"ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER configured: {'Yes' if ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER else 'No'}")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's ID from the environment if not provided
    if not user_id:
        user_id = os.environ.get("CURRENT_USER_ID")
        print(f"Using current user ID from environment: {user_id}")

    if not user_id:
        raise Exception("User ID not provided and not found in environment")

    # Use the new collection path for brands
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"
    print(f"Request URL: {url}")

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # Update the payload to use $and operator for multiple filters
    payload = {
        "findOne": {
            "filter": {"$and": [
                {"user_id": user_id},
                {"brand_name": brand}
            ]}
        }
    }
    print(f"Request payload: {json.dumps(payload, indent=2)}")

    try:
        print(f"Sending request to AstraDB...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        print(f"Response headers: {response.headers}")
        print(f"Response body: {response.text}")

        response.raise_for_status()
        data = response.json()
        print(f"Parsed JSON data: {json.dumps(data, indent=2)}")

        if not data:
            print("No data returned from AstraDB")
            raise Exception(f"No brand voice found for brand: {brand}")

        # The response should have a 'data' field that contains the document
        if 'data' in data and 'document' in data['data']:
            document = data['data']['document']
            brand_voice = document.get("brand_voice")
            print(f"Brand voice from response: {brand_voice}")

            if not brand_voice:
                print("brand_voice field not found in document data")
                raise Exception(f"No brand voice found for brand: {brand}")
        else:
            print("Expected data structure not found in response")
            print(f"Available keys in response: {list(data.keys())}")
            raise Exception(f"Data structure missing expected fields for brand: {brand}")

        print(f"=== Debug: Brand Voice Request Completed Successfully ===\n")
        return {"brand_voice": brand_voice}

    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to retrieve brand voice from AstraDB: {str(e)}")

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

def multitemplate_retriever(content_chunk: str, template_count_to_retrieve: int = 5, db_to_access: str = "sys", category: str = "Short Form") -> Dict:
    """
    Retrieve template documents based on content chunk using vector search
    Args:
        content_chunk: String containing the content to find templates for
        template_count_to_retrieve: The number of templates to retrieve
        db_to_access: Which databases to access ("sys", "user", or "both")
        category: The category of templates to retrieve (Short Form, Atomic, Mid Form)
    Returns:
        Dictionary containing template search results
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_FOR_SHORTFORM_TEMPLATES:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_FOR_SHORTFORM_TEMPLATES not configured")

    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

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

    # Define base payload for template search
    base_payload = {
        "find": {
            "sort": {"$vector": vector},
            "options": {
                "limit": template_count_to_retrieve
            }
        }
    }

    # Configure search based on db_to_access parameter
    if db_to_access.lower() == "both":
        # If accessing both databases, split the count between them
        count_per_db = template_count_to_retrieve // 2
        remaining_count = template_count_to_retrieve - count_per_db

        # Get templates from system database
        sys_results = search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "sys_keyspace/templates", 
            count_per_db,
            category
        )

        # Get templates from user database
        user_results = search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "user_content_keyspace/user_templates", 
            remaining_count,
            category
        )

        # Combine results from both databases
        combined_documents = []
        if sys_results.get("data", {}).get("documents"):
            combined_documents.extend(sys_results["data"]["documents"])
        if user_results.get("data", {}).get("documents"):
            combined_documents.extend(user_results["data"]["documents"])

        return {
            "data": {
                "documents": combined_documents
            }
        }

    elif db_to_access.lower() == "user":
        # Access only user templates
        return search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "user_content_keyspace/user_templates", 
            template_count_to_retrieve,
            category
        )
    else:
        # Default - access only system templates
        return search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "sys_keyspace/templates", 
            template_count_to_retrieve,
            category
        )

def search_templates_in_db(api_endpoint: str, api_token: str, vector: List[float], db_path: str, count: int, category: str) -> Dict:
    """
    Helper function to search templates in a specific database

    Args:
        api_endpoint: The AstraDB API endpoint
        api_token: The AstraDB API token
        vector: The embedding vector for similarity search
        db_path: The database path to search in (e.g., "sys_keyspace/templates")
        count: The number of templates to retrieve
        category: The category of templates to retrieve

    Returns:
        Dictionary containing template search results
    """
    url = f"{api_endpoint}/api/json/v1/{db_path}"

    headers = {
        "Token": api_token,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "sort": {"$vector": vector},
            "filter": {"category": category},
            "options": {
                "limit": count
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Failed to retrieve templates from {db_path}: {str(e)}")
        # Return empty result structure instead of raising an exception
        return {"data": {"documents": []}}

def short_form_social_repurposing(topic_query: str, brand: str, repurpose_count: int = 5, workflow_name: str = "Legacy Generation Flow") -> Dict:
    """
    Repurpose content based on topic query and user's brand voice
    Args:
        topic_query: String containing the topic to search for
        brand: String containing the brand for brand voice
        repurpose_count: Number of times to repurpose each topic/post (default: 5)
        workflow_name: String containing the workflow name for generation
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

    # Step 2: Get templates based on repurpose count
    template_results = multitemplate_retriever(combined_chunks, template_count_to_retrieve=repurpose_count)

    # Debug logging for template retrieval
    print("\n=== Debug: Template Retrieval Results ===")
    template_count = len(template_results.get("data", {}).get("documents", []))
    print(f"Requested template count: {repurpose_count}")
    print(f"Actual templates retrieved: {template_count}")
    if template_count > 0:
        print(f"First template preview: {template_results['data']['documents'][0].get('template', '')[:50]}...")
    else:
        print("Warning: No templates retrieved!")
    print("=== End Template Debug ===\n")

    # Step 3: Get brand voice (use current user's ID from environment)
    user_id = os.environ.get("CURRENT_USER_ID")
    brand_voice = get_client_brand_voice(brand, user_id)

    # Return early with status message
    result = {"status": "Your content is being generated"}

    # Step 4: Generate content for each template
    if template_results.get("data", {}).get("documents"):
        templates = template_results["data"]["documents"][:repurpose_count]  # Get templates based on repurpose count
        print(f"\n=== Debug: Using {len(templates)} templates for content generation ===")

        # Log each template being used
        for i, template in enumerate(templates, 1):
            template_content = template.get("template") if "template" in template else template.get("content", "")
            print(f"Template {i}: {template_content[:100]}...")

        for template in templates:
            from social_dynamic_generation_flow import social_post_generation_with_json

            # Determine the correct template content key (template or content)
            template_content = template.get("template") if "template" in template else template.get("content", "")

            if not template_content:
                print(f"Warning: Could not find template content in: {template}")
                continue

            generated_content = social_post_generation_with_json(
                workflow_name=workflow_name,
                client_brief=brand_voice["brand_voice"],
                template=template_content,
                content_chunks=combined_chunks
            )

            print(f"\n--- Content Generated Using Template ---")
            # Use the correct key for template content (template or content)
            template_display = template.get("template") if "template" in template else template.get("content", "Unknown template")
            print(f"Template: {template_display}")
            print(f"Generated Content: {generated_content}")

            # Extract template without variations by splitting on "|" and taking first part
            template_base = template_content.split("|")[0].strip()

            # Create content result using consistent template access
            content_result = {
                "first_draft": generated_content,
                "content_chunks": combined_chunks,
                "template": template_base
            }

            # Prepare content data for upload (now using the same approach as content_result)
            content_data = {
                "first_draft": content_result["first_draft"],
                "content_chunks": combined_chunks,
                "template": template_base,
                "workflow_name": workflow_name
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
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's ID from environment
    user_id = os.environ.get("CURRENT_USER_ID")
    if not user_id:
        raise Exception("CURRENT_USER_ID not configured")

    # Generate embedding for the topic query
    response = openai_client.embeddings.create(
        input=topic_query,
        model="text-embedding-3-small"
    )
    vector = response.data[0].embedding

    # Prepare search request
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")

    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_source_content"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "sort": {"$vector": vector},
            "filter": {"user_id": user_id},
            "options": {
                "limit": 5
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"AstraDB Response Status: {response.status_code}")
        print(f"AstraDB Response Headers: {response.headers}")
        print(f"AstraDB Response Body: {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"AstraDB Error Details: {str(e)}")
        print(f"Request URL: {url}")
        print(f"Request Headers: {headers}")
        print(f"Request Payload: {payload}")
        raise Exception(f"Failed to retrieve user source content: {str(e)}")

def template_context_and_uploader(template: str, category: str = "Short Form") -> Dict:
    """
    Process a template by generating a description with Claude and creating a vector embedding
    Args:
        template: String containing the template for a short form social post
        category: Template category (Short Form, Atomic, or Mid Form)
    Returns:
        Dictionary with vector embedding and combined text
    """
    print("\n=== Starting Template Processing ===")
    print(f"Input template: {template}")
    print(f"Template category: {category}")

    # Get the current user's ID from environment
    user_id = os.environ.get("CURRENT_USER_ID")
    if not user_id:
        raise Exception("CURRENT_USER_ID not configured")

    # Generate template description using Claude
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        system=Prompts.TEMPLATE_DESCRIPTION_ANALYSIS,
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

    # Generate a unique ID for the template
    template_id = str(uuid.uuid4())

    # Get Astra DB endpoint from environment
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Upload vector and text to AstraDB using the new URL and structure
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_templates"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    # Prepare document with new structure
    payload = {
        "insertOne": {
            "document": {
                "template_id": template_id,
                "user_id": user_id,
                "template": template,
                "description": template_description,
                "category": category,
                "$vector": vector,
                "metadata": {
                    "timestamp": timestamp
                }
            }
        }
    }

    try:
        print(f"\n=== Uploading Template to AstraDB ===")
        print(f"URL: {url}")
        print(f"Payload structure (truncated): {str(payload)[:200]}...")

        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")

        response.raise_for_status()
        result = response.json()
        print(f"=== Template Upload Completed ===\n")

        return result
    except requests.exceptions.RequestException as e:
        print(f"AstraDB upload failed: {str(e)}")
        raise Exception(f"Failed to upload to AstraDB: {str(e)}")

def repurposer_using_posts_as_templates(
    content_chunks: str,
    template_post: str,
    brand: str,
    workflow_id: str = "Legacy Generation Flow with Claude",
    is_given_template_query: bool = False,
    number_of_posts_to_template: int = 5,
    post_topic_query: str = "Digital Operations"
) -> Dict:
    """
    Repurpose content using social posts as templates
    Args:        content_chunks: String containing content to supply generation
        template_post: String of a social post to inherit / String of a query to grab social posts
        brand: String containing brand name
        workflow_id: String containing workflow ID for generation (default: Legacy Generation Flow with Claude)
        is_given_template_query: Boolean indicating if a template query is provided (default: False)
        number_of_posts_to_template: Number of top posts to use as templates (default: 5)
        post_topic_query: String containing topic for top content search (default: "Digital Operations")
    Returns:
        Dictionary containing repurposing results
    """
    print("\n=== Starting Posts as Templates Repurposing Process ===")

    # Get brand voice with current user's ID
    user_id = os.environ.get("CURRENT_USER_ID")
    brand_voice_result = get_client_brand_voice(brand, user_id)
    brand_voice = brand_voice_result["brand_voice"]

    if not is_given_template_query:
        # Direct template usage path
        generated_content = social_post_generation_with_json(
            workflow_id=workflow_id,
            client_brief=brand_voice,
            template=template_post,
            content_chunks=content_chunks
        )

        # Upload to Airtable
        content_data = {
            "first_draft": generated_content,
            "content_chunks": content_chunks,
            "template": template_post
        }
        upload_result = generated_content_uploader(content_data)

        return {
            "status": "success",
            "generated_content": generated_content,
            "upload_result": upload_result
        }
    else:
        # Query-based template retrieval path
        results = top_content_retriever(query=template_post, topic=post_topic_query)

        if not results.get("data", {}).get("documents"):
            return {
                "status": "error",
                "message": "No templates found from the query"
            }

        # Get top X posts based on number_of_posts_to_template
        top_posts = [doc.get("content", "") for doc in results["data"]["documents"][:number_of_posts_to_template]]

        # Generate content using each post as a template
        generated_contents = []
        for post in top_posts:
            generated_content = social_post_generation_with_json(
                workflow_id=workflow_id,
                client_brief=brand_voice,
                template=post,
                content_chunks=content_chunks
            )
            # Upload to Airtable
            content_data = {
                "first_draft": generated_content,
                "content_chunks": content_chunks,
                "template": post
            }
            upload_result = generated_content_uploader(content_data)

            generated_contents.append({
                "template": post,
                "generated_content": generated_content,
                "upload_result": upload_result
            })

        return {
            "status": "success",
            "generated_contents": generated_contents
        }

def Templatizer(social_post: str) -> str:
    """
    Process a social post to create a reusable template
    Args:
        social_post: String containing the social post to templatize
    Returns:
        String containing the generated template
    """
    print("\n=== Starting Templatization Process ===")
    print(f"Input post: {social_post}")

    # Generate template using Claude
    response = client.messages.create(
        model="claude-3-5-haiku-20241022",
        system=Prompts.TEMPLATIZER_SHORT_FORM_PROMPT,
        messages=[{"role": "user", "content": social_post}],
        max_tokens=2048
    )
    template = response.content[0].text.strip()
    print(f"\n=== Generated Template ===\n{template}")

    return template

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


def source_content_repurposer_using_posts_as_templates(
    content_topic_query: str,
    template_post: str,
    brand: str,
    workflow_id: str = "Legacy Generation Flow with Claude",
    is_given_template_query: bool = False,
    number_of_posts_to_template: int = 5,
    post_topic_query: str = "Digital Operations"
) -> Dict:
    """
    Repurpose source content using social posts as templates
    Args:
        content_topic_query: String containing topic to search for source content
        template_post: String of a social post to inherit / String of a query to grab social posts
        brand: String containing brand name
        workflow_id: String containing workflow ID for generation (default: Legacy Generation Flow with Claude)
        is_given_template_query: Boolean indicating if a template query is provided (default: False)
        number_of_posts_to_template: Number of top posts to use as templates (default: 5)
        post_topic_query: String containing topic for top content search (default: "Digital Operations")
    Returns:
        Dictionary containing repurposing results
    """
    # Get source content
    source_results = source_content_retriever(content_topic_query)

    # Extract first three content chunks
    content_chunks = []
    if source_results.get("data", {}).get("documents"):
        content_chunks = [doc["content"] for doc in source_results["data"]["documents"][:3]]

    # Combine chunks
    combined_chunks = "\n\n".join(content_chunks)

    # Use existing repurposer with prepared content
    return repurposer_using_posts_as_templates(
        content_chunks=combined_chunks,
        template_post=template_post,
        brand=brand,
        workflow_id=workflow_id,
        is_given_template_query=is_given_template_query,
        number_of_posts_to_template=number_of_posts_to_template,
        post_topic_query=post_topic_query
    )

def get_latest_generated_content(username: str) -> Dict:
    """
    Retrieve the latest generated content for a user from AstraDB
    Args:
        username: String containing the username to retrieve content for
    Returns:
        Dictionary containing the retrieved content documents
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    print(f"\n=== Debug: Latest Content Retrieval Started ===")
    print(f"Username: {username}")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the user_id from environment or by looking it up from the username
    user_id = os.environ.get("CURRENT_USER_ID")

    # If we don't have a user_id in the environment, we need to look it up from the username
    if not user_id:
        # This would need to be implemented - for now assuming user_id is available
        print(f"Warning: CURRENT_USER_ID not found in environment")

    # Use the new URL path for the user_content_keyspace
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/generated_content"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # Create the query payload with filter for user_id and sort by Created_Time in descending order (-1)
    payload = {
        "find": {
            "filter": {
                "user_id": user_id
            },
            "sort": {
                "Created_Time": -1  # -1 for descending order (newest first)
            }
        }
    }

    try:
        print(f"Sending request to AstraDB...")
        print(f"Request URL: {url}")
        print(f"Request payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")

        # Log truncated response for debugging
        response_text = response.text
        print(f"Response preview: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")

        response.raise_for_status()
        result = response.json()

        print(f"Found {len(result.get('data', {}).get('documents', []))} documents")
        print(f"=== Debug: Latest Content Retrieval Completed ===\n")

        return result
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to retrieve latest content from AstraDB: {str(e)}")

def delete_generated_content(username: str, content_id: str) -> Dict:
    """
    Delete a specific generated content document from AstraDB
    Args:
        username: String containing the username for the URL path
        content_id: String containing the content ID to delete
    Returns:
        Dictionary containing the deletion result
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    print(f"\n=== Debug: Content Deletion Started ===")
    print(f"Username: {username}")
    print(f"Content ID to delete: {content_id}")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Use the provided username for the URL path
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{username}/generated_content"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # Create the delete payload
    payload = {
        "findOneAndDelete": {
            "filter": {
                "_id": content_id
            }
        }
    }

    try:
        print(f"Sending delete request to AstraDB...")
        print(f"Request URL: {url}")
        print(f"Request payload: {json.dumps(payload, indent=2)}")

        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")

        # Log truncated response for debugging
        response_text = response.text
        print(f"Response preview: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")

        response.raise_for_status()
        result = response.json()

        print(f"=== Debug: Content Deletion Completed ===\n")

        return result
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to delete content from AstraDB: {str(e)}")

def simple_repurpose(social_post: str, brand: str, repurpose_count: int = 5, workflow_id: str = "Simple Repurpose Flow") -> List[Dict]:
    """
    Simple repurposing of a social post using multiple templates
    Args:
        social_post: String containing the social post to repurpose
        brand: String containing the brand name for brand voice
        repurpose_count: Number of templates to use (default: 5)
        workflow_id: String containing the workflow ID for generation (default: "Simple Repurpose Flow")
    Returns:
        List of dictionaries containing the generated content results
    """
    print("\n=== Starting Simple Repurpose Process ===")
    print(f"Input social post: {social_post}")
    print(f"Brand: {brand}")
    print(f"Repurpose count: {repurpose_count}")
    print(f"Workflow ID: {workflow_id}")

    # Step 1: Get templates using multitemplate_retriever
    print("\n--- Retrieving Templates ---")
    template_results = multitemplate_retriever(social_post, template_count_to_retrieve=repurpose_count)

    # Step 2: Get brand voice
    print("\n--- Retrieving Brand Voice ---")
    user_id = os.environ.get("CURRENT_USER_ID")
    brand_voice_result = get_client_brand_voice(brand, user_id)
    brand_voice = brand_voice_result["brand_voice"]

    # Step 3: Generate content for each template
    generated_results = []

    if template_results.get("data", {}).get("documents"):
        templates = template_results["data"]["documents"][:repurpose_count]

        print(f"\n--- Found {len(templates)} templates ---")

        for i, template in enumerate(templates, 1):
            print(f"\n--- Generating Content for Template {i}/{len(templates)} ---")
            print(f"Template: {template['content']}")

            # Extract template without variations by splitting on "|" and taking first part
            template_base = template["content"].split("|")[0].strip()

            try:
                # Generate content using the template
                generated_content = social_post_generation_with_json(
                    workflow_id=workflow_id,
                    client_brief=brand_voice,
                    template=template_base,
                    content_chunks=social_post
                )

                print(f"Generated Content: {generated_content}")

                # Store result
                generated_results.append({
                    "template": template_base,
                    "generated_content": generated_content
                })

                # Prepare content data for upload
                content_data = {
                    "first_draft": generated_content,
                    "content_chunks": social_post,
                    "template": template_base
                }

                # Upload the generated content
                upload_result = generated_content_uploader(content_data)
                print(f"Content upload successful. ID: {upload_result.get('data', {}).get('documentId', 'Unknown')}")

            except Exception as e:
                print(f"Error generating content with template {i}: {str(e)}")
                generated_results.append({
                    "template": template_base,
                    "error": str(e)
                })
    else:
        print("No templates found for the given social post")

    print("\n=== Simple Repurpose Process Complete ===")
    return generated_results
def delete_user_account(identifier: str, delete_by: str = "username") -> dict:
    """Delete a user account from the database."""
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    # Set up filter based on identifier type
    filter_field = "_id" if delete_by.lower() == "id" else "username"

    payload = {
        "findOneAndDelete": {
            "filter": {
                filter_field: identifier
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    return response.json()


def template_search(text_query: str, template_count: int = 5, db_to_access: str = "sys", category: str = "Short Form") -> Dict:
    """
    Search for templates using vector embedding of the provided text

    Args:
        text_query: String containing the text to find templates for
        template_count: The number of templates to retrieve (default: 5)
        db_to_access: Which databases to access ("sys", "user", or "both")
        category: The category of templates to retrieve

    Returns:
        Dictionary containing template search results
    """
    if not OPENAI_API_KEY:
        raise Exception("OPENAI_API_KEY not configured")

    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Generate embedding directly for the input text
    response = openai_client.embeddings.create(
        input=text_query,
        model="text-embedding-3-small"
    )
    vector = response.data[0].embedding

    print("Received the following inputs:")
    print(f"Text query: {text_query}")
    print(f"Template count: {template_count}")
    print(f"DB to access: {db_to_access}")
    print(f"Category: {category}")
    
    # Configure search based on db_to_access parameter
    if db_to_access.lower() == "both":
        # If accessing both databases, split the count between them
        print("Accessing both template databases")
        count_per_db = template_count // 2
        remaining_count = template_count - count_per_db

        # Get templates from system database
        sys_results = search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "sys_keyspace/templates", 
            count_per_db,
            category
        )

        # Get templates from user database
        user_results = search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "user_content_keyspace/user_templates", 
            remaining_count,
            category
        )

        # Combine results from both databases
        combined_documents = []
        if sys_results.get("data", {}).get("documents"):
            combined_documents.extend(sys_results["data"]["documents"])
        if user_results.get("data", {}).get("documents"):
            combined_documents.extend(user_results["data"]["documents"])

        return {
            "data": {
                "documents": combined_documents
            }
        }

    elif db_to_access.lower() == "user":
        # Access only user templates
        print("Accessing user templates only")
        return search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "user_content_keyspace/user_templates", 
            template_count,
            category
        )
    else:
        # Default - access only system templates
        print("Accessing system templates only")
        return search_templates_in_db(
            ASTRA_DB_API_ENDPOINT, 
            ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
            vector, 
            "sys_keyspace/templates", 
            template_count,
            category
        )