import anthropic
from typing import Dict
import os
import uuid
import requests
from urllib.parse import quote
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

    response = client.messages.create(model="claude-3-opus-20240229",
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

    response = client.messages.create(model="claude-3-opus-20240229",
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

        # Extract the first record's fields
        record = data["records"][0]["fields"]
        return record

    except requests.exceptions.RequestException as e:
        raise Exception(
            f"Failed to retrieve brand voice from Airtable: {str(e)}")
