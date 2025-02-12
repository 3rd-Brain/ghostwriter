from typing import Dict
from fastapi import FastAPI, HTTPException
from social_writer import social_writer, generated_content_uploader, get_client_brand_voice, vector_search_for_published_content, metric_sorter, top_content_sentiment_setup, source_content_retriever
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

@app.post("/sentiment-setup")
async def setup_sentiment(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        query = request_data.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="query is required")

        result = top_content_sentiment_setup(query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def top_content_retriever(query: str):
    setup_result = top_content_sentiment_setup(query)
    results = vector_search_for_published_content(setup_result["filter"], query)
    if setup_result.get("metric_sort"):
        results = metric_sorter(results, setup_result["metric_sort"])
    return results

@app.post("/top-content")
async def get_top_content(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        query = request_data.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="query is required")

        result = top_content_retriever(query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/source-content")
async def get_source_content(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        topic_query = request_data.get("topic_query")
        if not topic_query:
            raise HTTPException(status_code=400, detail="topic_query is required")

        result = source_content_retriever(topic_query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))