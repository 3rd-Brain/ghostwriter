
# Admin functionality for Ghostwriter API

import os
import requests
import json
from typing import Dict, Optional, List, Any
from fastapi import HTTPException
from datetime import datetime

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
    
    # Helper function to delete all documents that match a filter in batches
    def delete_all_documents(url, collection_name, filter_criteria):
        total_deleted = 0
        batch_results = []
        
        while True:
            try:
                print(f"Deleting batch of documents from {collection_name}...")
                payload = {
                    "deleteMany": {
                        "filter": filter_criteria
                    }
                }
                
                response = requests.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                batch_results.append(result)
                
                # Check deletion status
                status = result.get("status", {})
                deleted_count = status.get("deletedCount", 0)
                more_data = status.get("moreData", False)
                
                total_deleted += deleted_count
                print(f"Deleted {deleted_count} documents from {collection_name} (total: {total_deleted})")
                
                if not more_data:
                    print(f"All documents deleted from {collection_name}")
                    break
                    
                print(f"More documents to delete from {collection_name}, continuing...")
                
            except Exception as e:
                print(f"Error deleting documents from {collection_name}: {str(e)}")
                return {"error": str(e), "deleted_count": total_deleted, "batch_results": batch_results}
        
        return {"deleted_count": total_deleted, "batch_results": batch_results}
    
    # 1. Delete from users_keyspace/users (single document deletion)
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
        results["api_keys"] = delete_all_documents(
            api_keys_url, 
            "user_api_keys", 
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in API keys deletion process: {str(e)}")
        results["api_keys"] = {"error": str(e)}
    
    # 3. Delete from user_content_keyspace/brands
    try:
        print(f"Deleting user brands...")
        brands_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"
        results["brands"] = delete_all_documents(
            brands_url, 
            "brands", 
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in brands deletion process: {str(e)}")
        results["brands"] = {"error": str(e)}
    
    # 4. Delete from user_content_keyspace/generated_content
    try:
        print(f"Deleting user generated content...")
        generated_content_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/generated_content"
        results["generated_content"] = delete_all_documents(
            generated_content_url,
            "generated_content",
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in generated content deletion process: {str(e)}")
        results["generated_content"] = {"error": str(e)}
    
    # 5. Delete from user_content_keyspace/user_industry_reports
    try:
        print(f"Deleting user industry reports...")
        industry_reports_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_industry_reports"
        results["industry_reports"] = delete_all_documents(
            industry_reports_url,
            "user_industry_reports",
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in industry reports deletion process: {str(e)}")
        results["industry_reports"] = {"error": str(e)}
    
    # 6. Delete from user_content_keyspace/user_source_content
    try:
        print(f"Deleting user source content...")
        source_content_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_source_content"
        results["source_content"] = delete_all_documents(
            source_content_url,
            "user_source_content",
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in source content deletion process: {str(e)}")
        results["source_content"] = {"error": str(e)}
    
    # 7. Delete from user_content_keyspace/user_templates
    try:
        print(f"Deleting user templates...")
        templates_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_templates"
        results["templates"] = delete_all_documents(
            templates_url,
            "user_templates",
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in templates deletion process: {str(e)}")
        results["templates"] = {"error": str(e)}
    
    # 8. Delete from user_content_keyspace/user_twitter_publications
    try:
        print(f"Deleting user Twitter publications...")
        twitter_publications_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_twitter_publications"
        results["twitter_publications"] = delete_all_documents(
            twitter_publications_url,
            "user_twitter_publications",
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in Twitter publications deletion process: {str(e)}")
        results["twitter_publications"] = {"error": str(e)}
    
    # 9. Delete from user_content_keyspace/user_workflows
    try:
        print(f"Deleting user workflows...")
        workflows_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_workflows"
        results["workflows"] = delete_all_documents(
            workflows_url,
            "user_workflows",
            {"user_id": user_id}
        )
    except Exception as e:
        print(f"Error in workflows deletion process: {str(e)}")
        results["workflows"] = {"error": str(e)}
    
    print(f"=== Debug: Complete User Purge Completed ===\n")
    
    # Prepare deletion summary stats
    deletion_stats = {}
    total_deleted = 0
    
    for collection, result in results.items():
        if collection != "users":  # Users is deleteOne, not deleteMany
            if isinstance(result, dict) and "deleted_count" in result:
                deleted_count = result["deleted_count"]
                deletion_stats[collection] = deleted_count
                total_deleted += deleted_count
    
    # Determine overall success status
    has_errors = any(isinstance(v, dict) and "error" in v for v in results.values())
    
    return {
        "status": "success" if not has_errors else "partial_success",
        "message": f"User purge completed. Deleted {total_deleted} documents across {len(deletion_stats)} collections.",
        "details": results,
        "deletion_stats": deletion_stats
    }

def create_system_workflow(
    workflow_name: str,
    workflow_type: str,
    description: str,
    steps: List[Dict[str, Any]]
) -> Dict:
    """
    Create a system workflow in sys_keyspace/workflows.
    
    Args:
        workflow_name: The name of the workflow to create
        workflow_type: The type of workflow (e.g., 'post_generation', 'repurpose')
        description: A description of what the workflow does
        steps: List of generation steps with model configurations
        
    Returns:
        Dictionary containing the creation result
        
    Raises:
        Exception: If creation fails or database credentials are missing
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: System Workflow Creation Started ===")
    print(f"Workflow name: {workflow_name}")
    print(f"Workflow type: {workflow_type}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/workflows"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create a unique workflow ID using UUID
    import uuid
    workflow_id = str(uuid.uuid4())
    
    # Create the document to insert
    document = {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "workflow_type": workflow_type.lower(),
        "description": description,
        "steps": {
            "steps": steps
        },
        "metadata": {
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "created_by": "admin"
        }
    }
    
    # Create the insert payload
    payload = {
        "insertOne": {
            "document": document
        }
    }
    
    try:
        print(f"Sending create request to AstraDB...")
        print(f"Request URL: {url}")
        print(f"Request payload summary: {document['workflow_name']}, {len(steps)} steps")
        
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        
        # Log truncated response for debugging
        response_text = response.text
        print(f"Response preview: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
        
        response.raise_for_status()
        result = response.json()
        print(f"=== Debug: System Workflow Creation Completed ===\n")
        
        return {
            "status": "success",
            "message": f"System workflow '{workflow_name}' created successfully",
            "workflow_id": workflow_id,
            "details": result
        }
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to create system workflow in AstraDB: {str(e)}")

def delete_system_workflow(workflow_id: str) -> Dict:
    """
    Delete a system workflow from sys_keyspace/workflows.
    
    Args:
        workflow_id: The ID of the workflow to delete
        
    Returns:
        Dictionary containing the deletion result
        
    Raises:
        Exception: If deletion fails or database credentials are missing
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: System Workflow Deletion Started ===")
    print(f"Workflow ID to delete: {workflow_id}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/workflows"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create the delete payload
    payload = {
        "deleteOne": {
            "filter": {
                "workflow_id": workflow_id
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
        
        # Check if anything was deleted
        deleted_count = result.get("status", {}).get("deletedCount", 0)
        
        if deleted_count > 0:
            print(f"Successfully deleted workflow: {workflow_id}")
            print(f"=== Debug: System Workflow Deletion Completed ===\n")
            return {
                "status": "success",
                "message": f"System workflow '{workflow_id}' deleted successfully",
                "details": result
            }
        else:
            print(f"No workflow found with ID: {workflow_id}")
            print(f"=== Debug: System Workflow Deletion Completed (Not Found) ===\n")
            return {
                "status": "warning",
                "message": f"No system workflow found with ID '{workflow_id}'",
                "details": result
            }
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to delete system workflow from AstraDB: {str(e)}")

def create_system_template(
    template: str,
    category: str = "Short Form",
    description: str = "System template for content generation",
    vector_embedding: List[float] = []
) -> Dict:
    """
    Create a system template in sys_keyspace/templates.
    
    Args:
        template: The actual template content
        category: The category of the template (Short Form, Atomic, or Mid Form)
        description: Description of the template (required)
        vector_embedding: Vector embedding for semantic search (required)
        
    Returns:
        Dictionary containing the creation result
        
    Raises:
        Exception: If creation fails or database credentials are missing
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: System Template Creation Started ===")
    print(f"Template category: {category}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    if not vector_embedding:
        raise Exception("Vector embedding is required for template creation")
    
    if not description:
        raise Exception("Description is required for template creation")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/templates"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Create a unique template ID
    import uuid
    template_id = str(uuid.uuid4())
    
    # Create the document to insert
    document = {
        "template_id": template_id,
        "template": template,
        "category": category,
        "description": description,
        "$vector": vector_embedding,
        "metadata": {
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "created_by": "admin"
        }
    }
    
    # Create the insert payload
    payload = {
        "insertOne": {
            "document": document
        }
    }
    
    try:
        print(f"Sending create request to AstraDB...")
        print(f"Request URL: {url}")
        print(f"Request document ID: {template_id}")
        
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        
        # Log truncated response for debugging
        response_text = response.text
        print(f"Response preview: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")
        
        response.raise_for_status()
        result = response.json()
        print(f"=== Debug: System Template Creation Completed ===\n")
        
        return {
            "status": "success",
            "message": f"System template '{template_name}' created successfully",
            "template_id": template_id,
            "details": result
        }
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to create system template in AstraDB: {str(e)}")

def delete_system_template(template_id: str) -> Dict:
    """
    Delete a system template from sys_keyspace/templates.
    
    Args:
        template_id: The ID of the template to delete
        
    Returns:
        Dictionary containing the deletion result
        
    Raises:
        Exception: If deletion fails or database credentials are missing
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: System Template Deletion Started ===")
    print(f"Template ID to delete: {template_id}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")
    
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/templates"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Templates can be searched by either _id or template_id, so we'll use both in an $or filter
    payload = {
        "deleteOne": {
            "filter": {
                "$or": [
                    {"_id": template_id},
                    {"template_id": template_id}
                ]
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
        
        # Check if anything was deleted
        deleted_count = result.get("status", {}).get("deletedCount", 0)
        
        if deleted_count > 0:
            print(f"Successfully deleted template: {template_id}")
            print(f"=== Debug: System Template Deletion Completed ===\n")
            return {
                "status": "success",
                "message": f"System template '{template_id}' deleted successfully",
                "details": result
            }
        else:
            print(f"No template found with ID: {template_id}")
            print(f"=== Debug: System Template Deletion Completed (Not Found) ===\n")
            return {
                "status": "warning", 
                "message": f"No system template found with ID '{template_id}'",
                "details": result
            }
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to delete system template from AstraDB: {str(e)}")