from typing import Dict
from fastapi import FastAPI, HTTPException
from social_writer import social_writer, generated_content_uploader, get_client_brand_voice # Added import for get_client_brand_voice
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}



@app.post("/generate-social")
async def generate_social_content(request_data: Dict):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = social_writer(request_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-content")
async def upload_content(content_data: Dict):
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        result = generated_content_uploader(content_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/brand-voice/{username}")
async def get_brand_voice(username: str):
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        result = get_client_brand_voice(username)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))