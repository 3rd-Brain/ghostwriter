
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
    flow_config: Dict,
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
            
            # Log the content being sent
            print(f"\nMessage {msg['role']}:")
            print(f"Content: {content}\n")

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
