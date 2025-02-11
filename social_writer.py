import anthropic
from typing import Dict
import os
from prompts import Prompts

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Client(api_key=ANTHROPIC_API_KEY)

def social_writer(
    initial_info: Dict, 
    completion_params: Dict = None,
) -> Dict:

    if completion_params is None:
        completion_params = {}

    system_message = Prompts.INITIAL_GENERATION
    prompt = f"""{system_message}

Initial information:
{initial_info}

Write a social media post based on the information provided.  Keep it concise and engaging.
"""

    response = client.messages.create(
        model="claude-3-opus-20240229",
        system=system_message,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=200
    )

    first_draft = response.content[0].text

    system_message = Prompts.CONTENT_REFINEMENT
    prompt = f"""Initial content:
{first_draft}

Refine and polish this content to maximize engagement. Consider optimizing for length, tone, and keywords."""

    response = client.messages.create(
        model="claude-3-opus-20240229",
        system=system_message,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=200
    )

    optimized_content = response.content[0].text


    return {
        "first_draft": first_draft,
        "optimized_content": optimized_content,
    }