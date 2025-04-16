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


def repurpose_top_published_posts(user_id: str, brand: str, repurpose_count: int = 5, published_posts_count_to_repurpose: int = 5, workflow_name: str = "Legacy Generation Flow") -> Dict:
    """
    Repurpose top published posts for a user

    Args:
        user_id: String containing the user's ID
        brand: String containing the brand name for brand voice
        repurpose_count: Number of templates to use per post (default: 5)
        published_posts_count_to_repurpose: Number of top published posts to process (default: 5)
        workflow_name: Workflow name to use for content generation (default: "Legacy Generation Flow")

    Returns:
        Dictionary containing the repurposing results
    """
    print(f"\n=== Starting Top Published Posts Repurposing Process ===")
    print(f"User ID: {user_id}")
    print(f"Brand: {brand}")
    print(f"Repurpose count per post: {repurpose_count}")
    print(f"Published posts count to repurpose: {published_posts_count_to_repurpose}")
    print(f"Workflow name: {workflow_name}")

    # Step 1: Retrieve top published posts
    try:
        posts_data = top_published_posts_retriever(user_id)

        if not posts_data.get("data", {}).get("documents"):
            return {"status": "error", "message": "No published posts found for this user"}

        top_posts = posts_data["data"]["documents"]
        print(f"Retrieved {len(top_posts)} top published posts")

        # Step 2: Get brand voice for the specified brand
        from social_writer import get_client_brand_voice
        brand_voice_result = get_client_brand_voice(brand, user_id)
        brand_voice = brand_voice_result["brand_voice"]
        print(f"Retrieved brand voice for '{brand}'")

        # Step 3: Process each top post with multiple templates
        results = []

        for post_index, post in enumerate(top_posts[:published_posts_count_to_repurpose]):
            post_content = post.get("content", "")
            if not post_content:
                continue

            print(f"\n--- Processing Post {post_index + 1}/{min(published_posts_count_to_repurpose, len(top_posts))} ---")
            print(f"Post content: {post_content[:100]}{'...' if len(post_content) > 100 else ''}")

            # Get templates for this post
            from social_writer import multitemplate_retriever
            template_results = multitemplate_retriever(post_content, template_count_to_retrieve=repurpose_count)

            if not template_results.get("data", {}).get("documents"):
                print(f"No templates found for post {post_index + 1}")
                continue

            templates = template_results["data"]["documents"]
            print(f"Retrieved {len(templates)} templates for post")

            # Generate content using each template
            post_results = []

            for template_index, template in enumerate(templates):
                # Extract template content (handle both template and content keys)
                template_content = template.get("template") if "template" in template else template.get("content", "")

                if not template_content:
                    continue

                print(f"Using template {template_index + 1}: {template_content[:50]}...")

                # Generate content using the template and post content
                from social_dynamic_generation_flow import social_post_generation_with_json
                try:
                    generated_content = social_post_generation_with_json(
                        workflow_name=workflow_name,
                        client_brief=brand_voice,
                        template=template_content,
                        content_chunks=post_content
                    )

                    print(f"Generated content: {generated_content[:100]}...")

                    # Upload the generated content
                    from social_writer import generated_content_uploader

                    # Extract template base (without variations)
                    template_base = template_content.split("|")[0].strip()

                    # Prepare content data for upload
                    content_data = {
                        "first_draft": generated_content,
                        "content_chunks": post_content,
                        "template": template_base,
                        "workflow_name": "Top Post Repurposing",
                        "original_post_id": post.get("post_id", "")
                    }

                    upload_result = generated_content_uploader(content_data)

                    # Add to results
                    post_results.append({
                        "template": template_base,
                        "generated_content": generated_content,
                        "upload_result": upload_result
                    })

                except Exception as e:
                    print(f"Error generating content with template {template_index + 1}: {str(e)}")

            results.append({
                "original_post": post_content,
                "repurposed_content": post_results
            })

        print("\n=== Top Published Posts Repurposing Process Complete ===")

        return {
            "status": "success",
            "message": f"Successfully repurposed {len(results)} top posts",
            "results": results
        }

    except Exception as e:
        print(f"Error in repurpose_top_published_posts: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to repurpose top posts: {str(e)}"
        }