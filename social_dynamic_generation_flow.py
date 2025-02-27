
import os
import json
import requests
from urllib.parse import quote


from typing import Dict, List
import anthropic
import os
from string import Template

def legacy_generation_flow_with_claude() -> Dict:
    """
    Legacy generation flow using Claude for content generation
    Returns:
        Dictionary containing generation results
    """
    pass

def social_post_generation_with_json(
    workflow_id: str,
    client_brief: str,
    template: str,
    content_chunks: str,
    brand_voice: str = ""
) -> str:
    """
    Generate social post using a JSON-defined flow configuration
    Args:
        flow_config: Dictionary containing the generation steps configuration
        client_brief: String containing client brief
        template: String containing the template to use
        content_chunks: String containing content chunks
        brand_voice: Optional string containing brand voice guidelines
    Returns:
        String containing the generated social post
    """
    client = anthropic.Client(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    # Retrieve flow configuration using workflow_id
    flow_config = flow_config_retriever(workflow_id)
    
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
            content = template_str.format(
                client_brief=client_brief,
                template=template,
                content_chunks=content_chunks,
                brand_voice=brand_voice,
                prev_ai_output=prev_output
            )
            messages.append({"role": msg["role"], "content": content})
            


        # Make API call to Claude
        response = client.messages.create(
            model=step["Model"],
            system=step["System_prompt"],
            messages=messages,
            max_tokens=step["Max_tokens"],
            temperature=step["Temperature"]
        )
        
        # Store output for next step
        prev_output = response.content[0].text
        print(f"Output: {prev_output}\n")
        print(f"Character count: {len(prev_output)}")
    
    print("\n=== Generation Process Complete ===")
    return prev_output
    
def flow_config_retriever(workflow_id: str) -> dict:
    """
    Retrieve flow configuration from AstraDB based on workflow ID
    Args:
        workflow_id: String containing the workflow identifier
    Returns:
        Dictionary containing the flow configuration
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
    
    print(f"\n=== Debug: Flow Config Retrieval Started ===")
    print(f"Workflow ID: {workflow_id}")
    print(f"ASTRA_DB_API_ENDPOINT configured: {'Yes' if ASTRA_DB_API_ENDPOINT else 'No'}")
    print(f"ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER configured: {'Yes' if ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER else 'No'}")
    
    if not ASTRA_DB_API_ENDPOINT:
        raise Exception("ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise Exception("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's username from the environment
    CURRENT_USERNAME = os.environ.get("CURRENT_USERNAME", "GentOfTech")  # Default to GentOfTech if not set
    print(f"Current username: {CURRENT_USERNAME}")
    
    # Use the current user's username for the URL path
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{CURRENT_USERNAME}/workflows"
    print(f"Request URL: {url}")
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }
    
    payload = {
        "findOne": {
            "filter": {"Workflow_ID": workflow_id}
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
            raise Exception(f"No flow configuration found for workflow_id: {workflow_id}")
        
        # The response should have a 'data' field that contains the document
        if 'data' in data and 'document' in data['data']:
            document = data['data']['document']
            json_payload = document.get("JSON_Payload")
            print(f"JSON_Payload from response: {json_payload}")
            
            if not json_payload:
                print("JSON_Payload field not found in document data")
                raise Exception(f"No JSON Payload found for workflow_id: {workflow_id}")
                
            # Parse the JSON payload
            flow_config = json.loads(json_payload)
            print(f"=== Debug: Flow Config Retrieval Completed Successfully ===\n")
            return flow_config
        else:
            print("Expected data structure not found in response")
            print(f"Available keys in response: {list(data.keys())}")
            raise Exception(f"Data structure missing expected fields for workflow_id: {workflow_id}")
            
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {str(e)}")
        raise Exception(f"Invalid JSON in response payload: {str(e)}")
    except requests.exceptions.RequestException as e:
        print(f"Request exception: {str(e)}")
        raise Exception(f"Failed to retrieve flow configuration from AstraDB: {str(e)}")
import json
