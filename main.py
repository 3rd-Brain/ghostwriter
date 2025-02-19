from typing import Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks
from social_writer import generated_content_uploader, get_client_brand_voice, vector_search_for_published_content, metric_sorter, top_content_sentiment_setup, source_content_retriever, multitemplate_retriever, short_form_social_repurposing, top_content_to_repurposing, template_context_and_uploader
from social_dynamic_generation_flow import flow_config_retriever
import os

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.post("/upload-content")
async def upload_content(content_data: Dict):
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        result = generated_content_uploader(content_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/brand-voice/{brand}")
async def get_brand_voice(brand: str):
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        result = get_client_brand_voice(brand)
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

def top_content_retriever(query: str, topic: str) -> Dict:
    setup_result = top_content_sentiment_setup(query)
    results = vector_search_for_published_content(setup_result["filter"], topic)
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
        topic = request_data.get("topic")
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")

        result = top_content_retriever(query, topic)
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

@app.post("/repurpose")
async def repurpose_content(request_data: Dict, background_tasks: BackgroundTasks):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        topic_query = request_data.get("topic_query")
        brand = request_data.get("brand")
        repurpose_count = request_data.get("repurpose_count", 1)
        workflow_id = request_data.get("workflow_id", "Legacy Generation Flow with Claude")

        if not topic_query:
            raise HTTPException(status_code=400, detail="topic_query is required")
        if not brand:
            raise HTTPException(status_code=400, detail="brand is required")

        background_tasks.add_task(short_form_social_repurposing, topic_query, brand, repurpose_count, workflow_id)
        return {"status": "Your content is being generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/top-content-repurposing")
async def get_top_content_repurposing(request_data: Dict, background_tasks: BackgroundTasks):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        query = request_data.get("query")
        topic = request_data.get("topic")
        brand = request_data.get("brand")
        number_of_posts = request_data.get("number_of_posts", 5)
        repurpose_count = request_data.get("repurpose_count", 5)
        workflow_id = request_data.get("workflow_id", "Legacy Generation Flow with Claude")

        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        if not topic:
            raise HTTPException(status_code=400, detail="topic is required")
        if not brand:
            raise HTTPException(status_code=400, detail="brand is required")

        # Add task to background
        background_tasks.add_task(top_content_to_repurposing, query, topic, brand, number_of_posts, repurpose_count, workflow_id)

        # Return immediately
        return {"status": "Content is now being generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/social-post-generation")
async def generate_social_post(request_data: Dict):
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        workflow_id = request_data.get("workflow_id")
        client_brief = request_data.get("client_brief")
        template = request_data.get("template")
        content_chunks = request_data.get("content_chunks")
        brand_voice = request_data.get("brand_voice", "")

        if not all([workflow_id, client_brief, template, content_chunks]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        from social_dynamic_generation_flow import social_post_generation_with_json
        result = social_post_generation_with_json(
            workflow_id=workflow_id,
            client_brief=client_brief,
            template=template,
            content_chunks=content_chunks,
            brand_voice=brand_voice
        )
        return {"generated_content": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/templatizer-short-form")
async def create_template_embedding(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        template = request_data.get("template")
        if not template:
            raise HTTPException(status_code=400, detail="template is required")

        result = template_context_and_uploader(template)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/flow-config/{workflow_id}")
async def get_flow_config(workflow_id: str):
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        result = flow_config_retriever(workflow_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/templatizer")
async def create_template(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    
    try:
        social_post = request_data.get("social_post")
        if not social_post:
            raise HTTPException(status_code=400, detail="social_post is required")
            
        result = Templatizer(social_post)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/multitemplate")
async def get_multitemplate(request_data: Dict):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        content_chunk = request_data.get("content_chunk")
        template_count = request_data.get("template_count", 5)
        if not content_chunk:
            raise HTTPException(status_code=400, detail="content_chunk is required")

        result = multitemplate_retriever(content_chunk, template_count)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))