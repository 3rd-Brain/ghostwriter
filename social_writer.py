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

    response = client.messages.create(
        model="claude-3-opus-20240229",
        system=Prompts.INITIAL_GENERATION,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=2048
    )

    first_draft = response.content[0].text

    prompt = f"""Initial content:
{first_draft}

Refine and polish this content to maximize engagement. Consider optimizing for length, tone, and keywords. Client brief is provided below. Follow the user's brand voice:

{client_brief}"""

    response = client.messages.create(
        model="claude-3-opus-20240229",
        system=Prompts.CONTENT_REFINEMENT,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        max_tokens=2048
    )

    optimized_content = response.content[0].text


    return {
        "first_draft": first_draft,
        "optimized_content": optimized_content,
    }