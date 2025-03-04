import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Response, status, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Dict
from social_writer import generated_content_uploader, get_client_brand_voice, vector_search_for_published_content, metric_sorter, top_content_sentiment_setup, source_content_retriever, multitemplate_retriever, short_form_social_repurposing, top_content_to_repurposing, template_context_and_uploader, Templatizer, repurposer_using_posts_as_templates, source_content_repurposer_using_posts_as_templates
from social_dynamic_generation_flow import flow_config_retriever, social_post_generation_with_json
import schemas

# App setup
app = FastAPI(
    title="Ghostwriter API",
    description="API for generating and managing social media content",
    version="1.0.0",
    openapi_tags=[
        {"name": "Brand Management", "description": "Endpoints for managing brand voices and profiles"},
        {"name": "Content Management", "description": "Endpoints for managing and retrieving content"},
        {"name": "Generation Flows", "description": "Endpoints for configuring generation workflows"},
        {"name": "Template Management", "description": "Endpoints for creating and managing templates"},
        {"name": "Generation", "description": "Endpoints for generating content"},
        {"name": "Utility", "description": "Utility endpoints for search and analysis"},
        {"name": "Other", "description": "Miscellaneous endpoints"}
    ]
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Security configuration
SECRET_KEY = "your-secret-key-keep-it-secret"  # In production, use a secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Hardcoded credentials (in production, use a secure database)
CREDENTIALS = {
    "GentOfTech": {
        "password": "GOTBrain?"
    }
}

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Token creation
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Authentication routes
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username in CREDENTIALS and CREDENTIALS[username]["password"] == password:
        # Set the username as an environment variable
        os.environ["CURRENT_USERNAME"] = username

        access_token = create_access_token(
            data={"sub": username},
            expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "error": "Access denied. Wrong credentials."},
        status_code=status.HTTP_401_UNAUTHORIZED
    )

# Authentication dependency
async def get_current_user(request: Request):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = request.cookies.get("access_token")
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": current_user,
        "current_page": "dashboard"
    })

@app.get("/generation/repurpose", response_class=HTMLResponse, include_in_schema=False)
async def generation_repurpose(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("generation.html", {
        "request": request,
        "username": current_user,
        "current_page": "generation_repurpose",
        "page": "repurpose"
    })

@app.get("/generation/top-content", response_class=HTMLResponse, include_in_schema=False)
async def generation_top_content(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("top_content.html", {
        "request": request,
        "username": current_user,
        "current_page": "generation_top_content",
        "page": "top-content"
    })

@app.get("/generation/posts-templates", response_class=HTMLResponse, include_in_schema=False)
async def generation_posts_templates(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("posts_templates.html", {
        "request": request,
        "username": current_user,
        "current_page": "generation_posts_templates",
        "page": "posts-templates"
    })

@app.get("/create/brand-voice", response_class=HTMLResponse, include_in_schema=False)
async def create_brand_voice(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("brand_voice.html", {
        "request": request,
        "username": current_user,
        "current_page": "create_brand_voice"
    })

@app.get("/create/source-content", response_class=HTMLResponse, include_in_schema=False)
async def create_source_content(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("source_content.html", {
        "request": request,
        "username": current_user,
        "current_page": "create_source_content"
    })

@app.get("/create/templatizer", response_class=HTMLResponse, include_in_schema=False)
async def create_templatizer(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("templatizer.html", {
        "request": request,
        "username": current_user,
        "current_page": "create_templatizer"
    })

@app.get("/create/generation-flow", response_class=HTMLResponse, include_in_schema=False)
async def create_generation_flow(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("generation_flow.html", {
        "request": request,
        "username": current_user,
        "current_page": "create_generation_flow"
    })

@app.get("/generated-content", response_class=HTMLResponse, include_in_schema=False)
async def generated_content(request: Request, current_user: str = Depends(get_current_user)):
    AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
    if not AIRTABLE_API_KEY:
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    url = "https://api.airtable.com/v0/appLz2zuN6ZFu4mYS/tbliCJf9aeYkryU2W"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
    }
    params = {
        "view": "viwlEIVj2rgBVKVWj"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        contents = []
        for record in data.get("records", []):
            fields = record.get("fields", {})
            date_str = fields.get("Created Time", "")
            try:
                # Convert ISO format string to datetime object
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                date_obj = None

            contents.append({
                "content_id": fields.get("Content_ID", ""),
                "first_draft": fields.get("First Draft", ""),
                "source_chunk": fields.get("Source Chunk", ""),
                "template": fields.get("Template", ""),
                "tag": fields.get("Tag", ""),
                "date_created": date_obj
            })
        return templates.TemplateResponse("generated_content.html", {
            "request": request,
            "username": current_user,
            "current_page": "generated_content",
            "contents": contents
        })
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch generated content: {str(e)}")

@app.get("/search/published", response_class=HTMLResponse, include_in_schema=False)
async def search_published(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("search_published.html", {
        "request": request,
        "username": current_user,
        "current_page": "search_published"
    })

@app.get("/search/brand-voices", response_class=HTMLResponse, include_in_schema=False)
async def search_brand_voices(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("search_brand_voices.html", {
        "request": request,
        "username": current_user,
        "current_page": "search_brand_voices"
    })

@app.get("/search/source-content", response_class=HTMLResponse, include_in_schema=False)
async def search_source_content(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("search_source_content.html", {
        "request": request,
        "username": current_user,
        "current_page": "search_source_content"
    })

@app.get("/search/templates", response_class=HTMLResponse, include_in_schema=False)
async def search_templates(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("search_templates.html", {
        "request": request,
        "username": current_user,
        "current_page": "search_templates"
    })

@app.get("/logout", include_in_schema=False)
async def logout(response: Response):
    # Clear the username environment variable on logout
    if "CURRENT_USERNAME" in os.environ:
        del os.environ["CURRENT_USERNAME"]

    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    return response

# Configure CORS with enhanced settings for referrer issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # Changed to True to allow credentials
    allow_methods=["*"],
    allow_headers=["*", "Referer", "Origin", "X-Requested-With"],
    allow_origin_regex=None,
    expose_headers=["*"]
)

@app.middleware("http")
async def add_cors_headers(request, call_next):
    if request.method == "OPTIONS":
        response = Response()
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, DELETE, PUT, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Referer, Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response

    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Referer, Origin"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, DELETE, PUT, OPTIONS"
    response.headers["Access-Control-Allow-Credentials"] = "true"

    # Disable referrer policy restrictions
    response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
    return response

from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

class ReferrerPolicyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "no-referrer-when-downgrade"
        return response

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
app.add_middleware(ReferrerPolicyMiddleware)

@app.get("/", include_in_schema=False)
def read_root():
    return {"Hello": "World"}

@app.post("/api/generation-flow", response_model=schemas.SuccessResponse, tags=["Generation Flows"])
async def create_generation_flow(request_data: schemas.GenerationFlowRequest):
    """
    Save generation flow configuration to Airtable

    This endpoint stores workflow configuration for content generation.
    """
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    url = "https://api.airtable.com/v0/appLz2zuN6ZFu4mYS/tblXFcCbZsmGYebZt"
    headers = {
        "Authorization": f"Bearer {os.getenv('AIRTABLE_API_KEY')}",
        "Content-Type": "application/json"
    }

    # First prepare the steps JSON with proper escaping
    steps_json = json.dumps({
        "steps": request_data.steps
    }, ensure_ascii=False)

    # Format JSON payload with proper indentation
    formatted_steps_json = json.dumps(json.loads(steps_json), indent=2)

    payload = {
        "fields": {
            "workflow_id": request_data.workflowId,
            "Workflow Type": request_data.workflowType.title(),
            "Short Description": request_data.description,
            "JSON Payload": formatted_steps_json
        }
    }

    print("Payload being sent to Airtable:", json.dumps(payload, indent=2))

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return {"status": "success", "message": "Generation flow saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-content", response_model=Dict, tags=["Content Management"])
async def upload_content(content_data: schemas.ContentUploadRequest):
    """
    Upload generated content to AstraDB

    This endpoint stores generated content and associated metadata.
    """
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        # Convert Pydantic model to dict for the uploader function
        content_dict = content_data.dict()
        result = generated_content_uploader(content_dict)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/brand-voice/{brand}", response_model=Dict, tags=["Brand Management"])
async def get_brand_voice(brand: str):
    """
    Get the brand voice details for a specific brand.

    This endpoint retrieves the brand voice configuration from Airtable.
    """
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        # Print debugging information before calling get_client_brand_voice
        print(f"\n=== Debug: Calling get_client_brand_voice for brand: {brand} ===")
        result = get_client_brand_voice(brand)
        print(f"=== Debug: API Response: {result} ===\n")
        return result
    except Exception as e:
        print(f"\n=== Debug: Error in get_brand_voice: {str(e)} ===\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/vector-search", response_model=Dict, tags=["Utility"])
async def vector_search(request_data: schemas.VectorSearchRequest):
    """
    Search for similar content using vector search.

    This endpoint uses OpenAI embeddings to search for similar content based on the provided text.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        metadata_filter = request_data.metadata_filter
        text_to_vectorize = request_data.text_to_vectorize

        result = vector_search_for_published_content(metadata_filter, text_to_vectorize)

        # If sort_metric is provided, sort the results
        if request_data.sort_metric:
            result = metric_sorter(result, request_data.sort_metric)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sentiment-setup", response_model=Dict, tags=["Utility"])
async def setup_sentiment(request_data: schemas.SentimentSetupRequest):
    """
    Set up sentiment analysis configuration based on a query.

    This endpoint generates filter and sorting configurations for content sentiment analysis.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

    try:
        result = top_content_sentiment_setup(request_data.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def top_content_retriever(query: str, topic: str) -> Dict:
    setup_result = top_content_sentiment_setup(query)
    results = vector_search_for_published_content(setup_result["filter"], topic)
    if setup_result.get("metric_sort"):
        results = metric_sorter(results, setup_result["metric_sort"])
    return results

@app.post("/top-content", response_model=Dict, tags=["Content Management"])
async def get_top_content(request_data: schemas.TopContentRequest):
    """
    Retrieve top performing content based on a query and topic.

    This endpoint combines sentiment setup and vector search to find optimal content.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        result = top_content_retriever(request_data.query, request_data.topic)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/source-content", response_model=Dict, tags=["Content Management"])
async def get_source_content(request_data: schemas.SourceContentRequest):
    """
    Retrieve source content based on a topic query

    This endpoint searches for relevant source content from a knowledge base.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        result = source_content_retriever(request_data.topic_query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/repurpose", response_model=schemas.SuccessResponse, tags=["Generation"])
async def repurpose_content(request_data: schemas.RepurposeRequest, background_tasks: BackgroundTasks):
    """
    **Repurpose content based on a topic query for a specific brand.**

    This endpoint generates new content based on source content and brand voice.

    ## When to use
    Use this endpoint when you need to:
    * Generate content from scratch based on a topic
    * Create multiple content pieces at once without templates
    * Need simple content generation directly from source material

    *This endpoint runs in the background and doesn't provide immediate results.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")
    if not os.getenv("AIRTABLE_API_KEY"):
        raise HTTPException(status_code=500, detail="AIRTABLE_API_KEY not configured")

    try:
        background_tasks.add_task(
            short_form_social_repurposing, 
            request_data.topic_query, 
            request_data.brand, 
            request_data.repurpose_count, 
            request_data.workflow_id
        )
        return {"status": "success", "message": "Your content is being generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/top-content-repurposing", response_model=schemas.SuccessResponse, tags=["Generation"])
async def get_top_content_repurposing(request_data: schemas.TopContentRepurposingRequest, background_tasks: BackgroundTasks):
    """
    **Repurpose top performing content**

    This endpoint identifies top content based on metrics and creates new variations.

    ## When to use
    Use this endpoint when you need to:
    * Create content based on your **best performing** existing posts
    * Leverage performance metrics to guide content generation
    * Create variations of successful content patterns

    *This performs an automatic selection of high-performing content before repurposing.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")

    try:
        # Add task to background
        background_tasks.add_task(
            top_content_to_repurposing, 
            request_data.query, 
            request_data.topic, 
            request_data.brand, 
            request_data.number_of_posts, 
            request_data.repurpose_count, 
            request_data.workflow_id
        )

        # Return immediately
        return {"status": "success", "message": "Content is now being generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/social-post-generation", response_model=schemas.SocialPostGenerationResponse, tags=["Generation"])
async def generate_social_post(request_data: schemas.SocialPostGenerationRequest):
    """
    **Generate a social media post using a specified workflow.**

    This endpoint creates social media content based on template, brand voice, and content chunks.

    ## When to use
    Use this endpoint when you need to:
    * Generate a **single post** with immediate response
    * Have complete control over the workflow, template, and content
    * Need to see results immediately rather than in the background

    *Unlike other generation endpoints, this returns the content immediately.*
    """
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = social_post_generation_with_json(
            workflow_id=request_data.workflow_id,
            client_brief=request_data.client_brief,
            template=request_data.template,
            content_chunks=request_data.content_chunks,
            brand_voice=request_data.brand_voice
        )
        return {"generated_content": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/template-context-and-uploader", response_model=Dict, tags=["Template Management"])
async def create_template_embedding(request_data: schemas.TemplateContextRequest):
    """
    Process a template by generating a description and creating a vector embedding

    This endpoint analyzes templates and stores them with embeddings for retrieval.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = template_context_and_uploader(request_data.template)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/flow-config/{workflow_id}", tags=["Generation Flows"])
async def get_flow_config(workflow_id: str):
    """
    **Retrieve a generation workflow configuration**

    This endpoint fetches the complete configuration for a specific workflow by ID.

    ## When to use
    Use this endpoint when you need to:
    * **Get details of an existing workflow** before execution
    * View the steps, models, and prompts in a workflow
    * Verify workflow configuration before content generation

    *This is useful for inspecting workflows before using them in content generation endpoints.*
    """
    if not os.getenv("ASTRA_DB_API_ENDPOINT"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    try:
        result = flow_config_retriever(workflow_id)
        # Ensure response is JSON serializable
        return {"workflow_id": workflow_id, "flow_config": result}
    except Exception as e:
        print(f"Error retrieving flow config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/templatizer", response_model=schemas.TemplatizerResponse, tags=["Template Management"])
async def create_template(request_data: schemas.TemplatizerRequest):
    """
    Convert a social post into a reusable template

    This endpoint extracts the structure from a social post to create a template.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        template = Templatizer(request_data.social_post)
        return {"template": template}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/multitemplate", response_model=Dict, tags=["Template Management"])
async def get_multitemplate(request_data: schemas.MultitemplateRequest):
    """
    Retrieve multiple templates based on content chunk

    This endpoint finds suitable templates for a given content piece.
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = multitemplate_retriever(request_data.content_chunk, request_data.template_count)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/repurpose-with-templates", response_model=Dict, tags=["Generation"])
async def repurpose_with_templates(request_data: schemas.RepurposeWithTemplatesRequest):
    """
    **Repurpose content using social posts as templates**

    This endpoint generates new content using existing post structures.

    ## When to use
    Use this endpoint when you need to:
    * Create content based on **specific templates** you provide
    * Maintain consistent formatting across content pieces
    * Apply a successful post structure to new content
    * Get immediate results rather than background processing

    *Unlike `/source-content-repurpose-with-templates`, this requires you to provide content chunks.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = repurposer_using_posts_as_templates(
            content_chunks=request_data.content_chunks,
            template_post=request_data.template_post,
            brand=request_data.brand,
            workflow_id=request_data.workflow_id,
            is_given_template_query=request_data.is_given_template_query,
            number_of_posts_to_template=request_data.number_of_posts_to_template,
            post_topic_query=request_data.post_topic_query
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/source-content-repurpose-with-templates", response_model=schemas.SuccessResponse, tags=["Generation"])
async def repurpose_source_content_with_templates(
    request_data: schemas.SourceContentRepurposeWithTemplatesRequest, 
    background_tasks: BackgroundTasks
):
    """
    **Repurpose source content using social posts as templates**

    This endpoint retrieves source content and generates new content using existing post structures.

    ## When to use
    Use this endpoint when you need to:
    * Create content from **source knowledge** using specific templates
    * Combine template structure with fresh source content
    * Process multiple pieces of content in the background
    * Don't have specific content chunks prepared

    *This endpoint automatically retrieves relevant source content based on your topic query,
    then applies templates to create multiple posts in the background.*
    """
    try:
        # Add task to background
                background_tasks.add_task(
            source_content_repurposer_using_posts_as_templates,
            content_topic_query=request_data.content_topic_query,
            template_post=request_data.template_post,
            brand=request_data.brand,
            workflow_id=request_data.workflow_id,
            is_given_template_query=request_data.is_given_template_query,
            number_of_posts_to_template=request_data.number_of_posts_to_template,
            post_topic_query=request_data.post_topic_query
        )

        return {"status": "success", "message": "Content is now being generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

@app.delete("/api/generation-flow/{workflow_id}", tags=["Generation Flows"])
async def delete_generation_flow(workflow_id: str):
    """Delete a generation flow configuration from AstraDB"""
    if not os.getenv("ASTRA_DB_API_ENDPOINT"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    try:
        from social_dynamic_generation_flow import workflow_delete
        result = workflow_delete(workflow_id)

        # Check if deletion was successful
        if result.get("data", {}).get("deletedCount", 0) > 0:
            return {"status": "success", "message": f"Workflow '{workflow_id}' deleted successfully"}
        else:
            return {"status": "warning", "message": f"Workflow '{workflow_id}' not found or already deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))