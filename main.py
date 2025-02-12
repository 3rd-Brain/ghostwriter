from typing import Dict
from fastapi import FastAPI, HTTPException
from social_writer import social_writer, generated_content_uploader, get_client_brand_voice, vector_search_for_published_content, metric_sorter
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

@app.post("/vector-search")
async def vector_search(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        metadata_filter = request_data.get("metadata_filter", {})
        text_to_vectorize = request_data.get("text_to_vectorize")

        if not text_to_vectorize:
            raise HTTPException(status_code=400, detail="text_to_vectorize is required")

        result = vector_search_for_published_content(metadata_filter, text_to_vectorize)
        
        # If sort_metric is provided, sort the results
        sort_metric = request_data.get("sort_metric")
        if sort_metric:
            result = metric_sorter(result, sort_metric)
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))