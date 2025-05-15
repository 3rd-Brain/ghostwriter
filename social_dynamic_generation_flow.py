import os
import json
import requests
from urllib.parse import quote

from typing import Dict, List
import anthropic
import os
from string import Template
from third_party_keys import get_third_party_key

def social_post_generation_with_json(workflow_name: str,
                                     client_brief: str,
                                     template: str,
                                     content_chunks: str,
                                     brand_voice: str = "") -> str:
    """
    Generate social post using a JSON-defined flow configuration
    Args:
        workflow_name: String containing the workflow name to use
        client_brief: String containing client brief
        template: String containing the template to use
        content_chunks: String containing content chunks
        brand_voice: Optional string containing brand voice guidelines
    Returns:
        String containing the generated social post
    """
    client = anthropic.Client(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    # Retrieve flow configuration using workflow_name
    flow_config = flow_config_retriever(workflow_name)

    # Sort steps by order
    steps = sorted(flow_config["steps"], key=lambda x: x["Order"])
    prev_output = ""

    print("\n=== Starting Generation Process ===")
    for step in steps:
        print(f"\n--- Step: {step['Step_name']} ---")
        # Prepare messages by replacing variables in content
        messages = []
        for msg in step["Message"]:
            # Create template with variables to replace
            template_str = msg["content"]

            # First replace the raw newlines with actual newlines
            template_str = template_str.replace('\\n', '\n')

            # Replace variables directly in the string first
            content = template_str.format(client_brief=client_brief,
                                          template=template,
                                          content_chunks=content_chunks,
                                          brand_voice=brand_voice,
                                          prev_ai_output=prev_output)
            messages.append({"role": msg["role"], "content": content})

        # Make API call to Claude
        response = client.messages.create(model=step["Model"],
                                          system=step["System_prompt"],
                                          messages=messages,
                                          max_tokens=step["Max_tokens"],
                                          temperature=step["Temperature"])

        # Store output for next step
        prev_output = response.content[0].text
        print(f"Output: {prev_output}\n")
        print(f"Character count: {len(prev_output)}")

    print("\n=== Generation Process Complete ===")
    return prev_output


def flow_config_retriever(workflow_name: str) -> dict:
    """
    Retrieve flow configuration from AstraDB based on workflow name.
    First checks system workflows, then falls back to user workflows if not found.

    Args:
        workflow_name: String containing the workflow name
    Returns:
        Dictionary containing the flow configuration
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get(
        "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    # Get the current user's ID from the environment
    CURRENT_USER_ID = os.environ.get("CURRENT_USER_ID", "")

    print(f"\n=== Debug: Flow Config Retrieval Started ===")
    print(f"Workflow Name: {workflow_name}")
    print(f"User ID: {CURRENT_USER_ID}")
    print(
        f"ASTRA_DB_API_ENDPOINT configured: {'Yes' if ASTRA_DB_API_ENDPOINT else 'No'}"
    )
    print(
        f"ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER configured: {'Yes' if ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER else 'No'}"
    )

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception(
            "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # First, try to find the workflow in the system workflows
    system_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/workflows"
    print(f"Checking system workflows at URL: {system_url}")

    system_payload = {"findOne": {"filter": {"workflow_name": workflow_name}}}
    print(f"System payload: {json.dumps(system_payload, indent=2)}")

    try:
        print(f"Sending request to system workflows collection...")
        system_response = requests.post(system_url, headers=headers, json=system_payload)
        print(f"System response status code: {system_response.status_code}")

        if system_response.status_code == 200:
            system_data = system_response.json()
            print(f"System data available: {'Yes' if system_data else 'No'}")

            # Check if we found a document in the system workflows
            if system_data.get('data', {}).get('document'):
                print(f"Found workflow in system workflows collection")
                document = system_data['data']['document']
                # Check for nested fields based on sample document structure
                generation_steps = document.get("steps")
                print(f"Generation Steps from system response: {generation_steps}")

                if generation_steps:
                    # Parse the Generation Steps
                    if isinstance(generation_steps, dict):
                        flow_config = generation_steps
                    else:
                        try:
                            flow_config = json.loads(generation_steps)
                        except json.JSONDecodeError as e:
                            print(f"Generation steps parsing failed: {str(e)}")
                            if isinstance(generation_steps, str) and generation_steps.startswith('"') and generation_steps.endswith('"'):
                                unescaped_steps = generation_steps[1:-1].replace('\\"', '"')
                                flow_config = json.loads(unescaped_steps)
                            else:
                                raise

                    # If the payload has a 'steps' field and it's a dict with a nested 'steps' array
                    if 'steps' in flow_config and isinstance(flow_config['steps'], dict) and 'steps' in flow_config['steps']:
                        print("Found nested steps structure in system workflow")
                        flow_config['steps'] = flow_config['steps']['steps']

                    print(f"=== Debug: System Flow Config Retrieval Completed Successfully ===\n")
                    return flow_config
            else:
                print("No document found in system workflows, checking user workflows...")
        else:
            print(f"System workflow request failed with status {system_response.status_code}")
            print(f"Response: {system_response.text}")

        # If we reach here, we didn't find the workflow in system workflows
        # Try to find it in user workflows
        user_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_workflows"
        print(f"Checking user workflows at URL: {user_url}")

        # Need to filter by both user_id and workflow_name for user workflows using $and operator
        user_payload = {
            "findOne": {
                "filter": {
                    "$and": [
                        {"user_id": CURRENT_USER_ID},
                        {"workflow_name": workflow_name}
                    ]
                }
            }
        }
        print(f"User payload: {json.dumps(user_payload, indent=2)}")

        print(f"Sending request to user workflows collection...")
        user_response = requests.post(user_url, headers=headers, json=user_payload)
        print(f"User response status code: {user_response.status_code}")

        if user_response.status_code != 200:
            print(f"User workflow request failed with status {user_response.status_code}")
            print(f"Response: {user_response.text}")
            raise Exception(f"No workflow found with name: {workflow_name}")

        user_data = user_response.json()
        print(f"User data available: {'Yes' if user_data else 'No'}")

        if not user_data.get('data', {}).get('document'):
            print("No document found in user workflows")
            raise Exception(f"No workflow found with name: {workflow_name}")

        document = user_data['data']['document']
        # Handle nested steps structure - the steps field might be an object with a 'steps' array
        steps = document.get("steps")

        if not steps:
            print("No steps field found in user workflow document")
            raise Exception(f"Invalid workflow format for workflow_name: {workflow_name}")

        # Check if steps is a dict with a nested 'steps' array (new format)
        if isinstance(steps, dict) and 'steps' in steps:
            print("Found nested steps structure in user workflow")
            steps = steps['steps']

        # For user workflows, we return the steps array
        print(f"=== Debug: User Flow Config Retrieval Completed Successfully ===\n")
        return {"steps": steps}

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {str(e)}")
        raise Exception(f"Invalid JSON in response payload: {str(e)}")
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(
            f"Failed to retrieve flow configuration from AstraDB: {str(e)}")


def workflow_delete(workflow_id: str) -> dict:
    """
    Delete a workflow configuration from AstraDB based on workflow ID
    Args:
        workflow_id: String containing the workflow identifier to delete
    Returns:
        Dictionary containing the deletion result
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get(
        "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    print(f"\n=== Debug: Workflow Deletion Started ===")
    print(f"Workflow ID to delete: {workflow_id}")

    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception(
            "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's username from the environment
    CURRENT_USERNAME = os.environ.get(
        "CURRENT_USERNAME", "GentOfTech")  # Default to GentOfTech if not set

    # Use the current user's username for the URL path
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{CURRENT_USERNAME}/workflows"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    payload = {"deleteOne": {"filter": {"Workflow_ID": workflow_id}}}

    try:
        print(f"Sending delete request to AstraDB...")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        print(f"Delete response: {json.dumps(result, indent=2)}")
        print(f"=== Debug: Workflow Deletion Completed ===\n")

        return result
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to delete workflow from AstraDB: {str(e)}")