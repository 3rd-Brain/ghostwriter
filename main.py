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
from onboarding import router as onboarding_router

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
        {"name": "Onboarding", "description": "Endpoints for user onboarding process"},
        {"name": "Other", "description": "Miscellaneous endpoints"}
    ]
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Security configuration
SECRET_KEY = "your-secret-key-keep-it-secret"  # In production, use a secure secret key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

import bcrypt

# bcrypt for password hashing

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
    # Get Astra DB credentials from environment
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Database configuration error. Please contact administrator."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    try:
        # Query the user from the database
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        payload = {
            "findOne": {
                "filter": {"username": username}
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        user_data = response.json()

        # Check if user exists and password matches
        if user_data.get("data") and user_data["data"].get("document"):
            user = user_data["data"]["document"]
            stored_hash = user.get("password_hash", "")
            user_id = user.get("user_id", "")

            # Debug logging for password comparison
            print(f"Login attempt for user: {username}")
            print(f"Stored hash exists: {bool(stored_hash)}")
            
            # Compare plain password with stored hash
            is_password_match = False
            if stored_hash:
                try:
                    is_password_match = bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
                    print(f"Password comparison result: {is_password_match}")
                except Exception as e:
                    print(f"Error during password comparison: {str(e)}")
                    
            if is_password_match:
                print(f"Login successful for user: {username}")
                # Set the username and user_id as environment variables
                os.environ["CURRENT_USERNAME"] = username
                os.environ["CURRENT_USER_ID"] = user_id
                
                # Create an access token that includes both username and user_id
                access_token = create_access_token(
                    data={"sub": username, "user_id": user_id},
                    expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                )
                response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
                response.set_cookie(key="access_token", value=access_token, httponly=True)
                return response
            else:
                print(f"Login failed for user: {username}")
                return templates.TemplateResponse(
                    "login.html",
                    {"request": request, "error": "Invalid username or password"},
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

        # If authentication fails or user doesn't exist
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Access denied. Wrong credentials."},
            status_code=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        print(f"Login error: {str(e)}")
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "An error occurred during login. Please try again."},
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        user_id: str = payload.get("user_id", "")
        if username is None:
            raise credentials_exception
        return {"username": username, "user_id": user_id}
    except JWTError:
        raise credentials_exception

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "dashboard"
    })

@app.get("/generation/repurpose", response_class=HTMLResponse, include_in_schema=False)
async def generation_repurpose(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("generation.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "generation_repurpose",
        "page": "repurpose"
    })

@app.get("/generation/top-content", response_class=HTMLResponse, include_in_schema=False)
async def generation_top_content(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("top_content.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "generation_top_content",
        "page": "top-content"
    })

@app.get("/generation/posts-templates", response_class=HTMLResponse, include_in_schema=False)
async def generation_posts_templates(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("posts_templates.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "generation_posts_templates",
        "page": "posts-templates"
    })

@app.get("/generate-content", response_class=HTMLResponse, include_in_schema=False)
async def generate_content(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("generate_content.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "generate_content"
    })

@app.get("/api/workflows", tags=["Generation Flows"])
async def get_workflows(current_user: dict = Depends(get_current_user)):
    """
    **Retrieve all generation workflow configurations**

    This endpoint fetches all workflows available for the current user.

    ## When to use
    Use this endpoint when you need to:
    * **List all available workflows** for user selection
    * Get an overview of configured generation processes
    * Select a workflow for content generation
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's username and user_id
    username = current_user["username"]
    user_id = current_user["user_id"]

    # Use the current user's username for the URL path
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{username}/workflows"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    payload = {"find": {"filter": {}}}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        # Extract the documents from the response
        workflows = result.get("data", {}).get("documents", [])

        return {
            "status": "success",
            "workflows": workflows
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
async def generated_content(request: Request, current_user: dict = Depends(get_current_user)):
    from social_writer import get_latest_generated_content

    try:
        # Use the current user's username and user_id from the authentication
        username = current_user["username"]
        user_id = current_user["user_id"]

        # Fetch the latest content from AstraDB
        result = get_latest_generated_content(username)
        documents = result.get("data", {}).get("documents", [])

        contents = []
        for doc in documents:
            # Parse the date from string format to datetime object
            date_str = doc.get("Created_Time", "")
            try:
                # Convert string to datetime object
                date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S UTC") if date_str else None
            except (ValueError, AttributeError):
                date_obj = None

            contents.append({
                "content_id": doc.get("_id", ""),
                "first_draft": doc.get("First_Draft", ""),
                "source_chunk": doc.get("Source_Chunk", ""),
                "template": doc.get("Template", ""),
                "tag": doc.get("Tag", ""),
                "date_created": date_obj
            })

        return templates.TemplateResponse("generated_content.html", {
            "request": request,
            "username": current_user["username"],
            "user_id": current_user["user_id"],
            "current_page": "generated_content",
            "contents": contents
        })
    except Exception as e:
        print(f"Error fetching latest content: {str(e)}")
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

@app.get("/template-management", response_class=HTMLResponse, include_in_schema=False)
async def template_management(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("template_management.html", {
        "request": request,
        "username": current_user,
        "current_page": "template_management"
    })

@app.get("/content-approval", response_class=HTMLResponse, include_in_schema=False)
async def content_approval(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("content_approval.html", {
        "request": request,
        "username": current_user,
        "current_page": "content_approval"
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

# Include onboarding router
app.include_router(onboarding_router)

@app.get("/", include_in_schema=False)
def read_root():
    return {"Hello": "World"}

@app.post("/api/generation-flow", response_model=schemas.SuccessResponse, tags=["Generation Flows"])
async def create_generation_flow(request_data: schemas.GenerationFlowRequest):
    """
    **Create or update a content generation workflow**

    This endpoint stores a custom workflow configuration that defines how content is generated.

    ## When to use
    Use this endpoint when you need to:
    * **Define a new workflow** with custom generation steps
    * Create a **reusable process** for content creation
    * Set up **specific AI models** and prompts for each step
    * Define **multi-stage generation** with different parameters

    *Once created, workflows can be referenced by ID in content generation endpoints.*
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's username from the environment
    CURRENT_USERNAME = os.environ.get("CURRENT_USERNAME")

    # Use the current user's username for the URL path
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/{CURRENT_USERNAME}/workflows"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # Convert the Pydantic model objects to dictionaries first
    steps_dict = [step.dict() for step in request_data.steps]

    # Prepare the payload according to AstraDB format
    json_payload = {
        "steps": steps_dict
    }

    # Create the document object
    document = {
        "Workflow_ID": request_data.workflowId,
        "Workflow_Type": request_data.workflowType.title(),
        "Short_Description": f"{request_data.workflowType.title()}_Content",
        "Description": request_data.description,
        "JSON_Payload": json_payload,
        "Sample_Output": "",
        "Workflow_Tag": request_data.workflowId
    }

    # Create the final AstraDB payload
    payload = {
        "insertOne": {
            "document": document
        }
    }

    print("Payload being sent to AstraDB:", json.dumps(payload, indent=2))

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")
        print(f"Response text: {response.text}")
        response.raise_for_status()
        return {"status": "success", "message": "Generation flow saved successfully in AstraDB"}
    except Exception as e:
        print(f"Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-content", response_model=Dict, tags=["Content Management"])
async def upload_content(content_data: schemas.ContentUploadRequest):
    """
    **Upload generated content to the content database**

    This endpoint stores content that has been generated along with its metadata for future reference and retrieval.

    ## When to use
    Use this endpoint when you need to:
    * **Store newly generated content** after creation
    * **Preserve the relationship** between content and its source material
    * **Track templates** used for specific content pieces
    * Build a **searchable knowledge base** of content for later reference

    *This endpoint should be called after content generation to ensure all content is properly archived.*
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
    **Retrieve brand voice and tone guidelines**

    This endpoint fetches the complete brand voice profile, including tone, style, and communication guidelines for a specific brand.

    ## When to use
    Use this endpoint when you need to:
    * **Apply consistent branding** to generated content
    * Access **tone and style guidelines** for content creation
    * Ensure content reflects the **brand personality**
    * Incorporate brand-specific **terminology and phrasing**

    *This endpoint should be called before content generation to ensure all content adheres to brand guidelines.*
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

def top_content_retriever(query: str, topic: str = "general") -> Dict:
    setup_result = top_content_sentiment_setup(query)
    results = vector_search_for_published_content(setup_result["filter"], topic)
    if setup_result.get("metric_sort"):
        results = metric_sorter(results, setup_result["metric_sort"])
    return results

@app.post("/top-content", response_model=Dict, tags=["Content Management"])
async def get_top_content(request_data: schemas.TopContentRequest):
    """
    **Retrieve top-performing content based on performance metrics**

    This endpoint identifies your best content by combining semantic search with performance metric analysis.

    ## When to use
    Use this endpoint when you need to:
    * **Identify successful content patterns** for future creation
    * **Find high-engagement posts** on specific topics
    * **Analyze what works** for your specific audience
    * **Select content for repurposing** based on proven performance

    *Unlike `/source-content` which finds reference material, this endpoint specifically targets content with strong performance metrics.*
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
    **Retrieve relevant source content from the knowledge base**

    This endpoint performs semantic search to find the most relevant source material based on a topic query.

    ## When to use
    Use this endpoint when you need to:
    * **Find reference material** for content creation
    * **Research specific topics** in your knowledge base
    * **Gather source material** before content generation
    * Access **foundational content** without knowing exact document names

    *This endpoint is typically called before content generation to provide source material for the AI models.*
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

@app.post("/generate-new-content", response_model=schemas.SuccessResponse, tags=["Generation"])
async def generate_new_content(request_data: schemas.RepurposeRequest, background_tasks: BackgroundTasks):
    """
    **Generate new content based on a topic query for a specific brand.**

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
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN notconfigured")

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
    **Process and index a template for future retrieval**

    This endpoint analyzes a template, generates a semantic description, and creates a vector embedding for efficient searching.

    ## When to use
    Use this endpoint when you need to:
    * **Add a new template** to your template library
    * Make a template **searchable** by its semantic content
    * **Index** a template before using it in content generation
    * Enable **automatic template matching** for future content

    *This is a prerequisite step before templates can be used with the `/multitemplate` endpoint.*
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
    * Clone an existing workflow as a starting point for a new one

    *This endpoint is typically used before running content generation to ensure the workflow is configured correctly.*
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
    **Convert an existing social post into a reusable template**

    This endpoint analyzes a successful social post and extracts its structure to create a template for future content.

    ## When to use
    Use this endpoint when you need to:
    * **Extract the structure** from a high-performing post
    * Create a **reusable template** from existing content
    * **Standardize content formats** across your social media
    * Leverage the structure of successful posts for new content

    *After creating a template, use `/template-context-and-uploader` to index it for future retrieval.*
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
    **Find templates that match specific content**

    This endpoint uses semantic search to identify templates best suited for a particular content chunk.

    ## When to use
    Use this endpoint when you need to:
    * **Find appropriate templates** for specific content
    * Get **multiple formatting options** for a content piece
    * **Automatically match** content with compatible templates
    * Enhance content presentation with optimized formatting

    *This endpoint requires templates to be previously processed with `/template-context-and-uploader`.*
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
    """
    **Delete a generation workflow configuration**

    This endpoint permanently removes a workflow configuration from the database.

    ## When to use
    Use this endpoint when you need to:
    * **Remove obsolete workflows** that are no longer needed
    * **Clean up** your workflow library
    * **Delete test workflows** after development
    * Remove workflows that have been replaced with newer versions

    *This action cannot be undone, and workflows in use by other processes will cause errors if deleted.*
    """
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

@app.get("/api/latest-content", tags=["Content Management"])
async def get_latest_generated_content(current_user: dict = Depends(get_current_user)):
    """
    **Retrieve the latest generated content for the current user**

    This endpoint fetches the most recent content generated by the current user,
    sorted by creation timestamp.

    ## When to use
    Use this endpoint when you need to:
    * View your most recently generated content
    * Track your latest content generation activities
    * Retrieve content for editing or review
    """
    try:
        from social_writer import get_latest_generated_content

        # Use the current user's username from the authentication
        username = current_user["username"]
        user_id = current_user["user_id"]

        result = get_latest_generated_content(username)

        return {
            "status": "success", 
            "content": result.get("data", {}).get("documents", []),
            "user_id": user_id
        }
    except Exception as e:
        print(f"Error fetching latest content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/latest-content-specified/{username}", tags=["Content Management"])
async def get_latest_content_specified(username: str):
    """
    **Retrieve the latest generated content for a specified username**

    This endpoint fetches the most recent content generated by the specified username,
    sorted by creation timestamp.

    ## When to use
    Use this endpoint when you need to:
    * View content generated by a specific user
    * Access content across multiple user accounts
    * Compare content generation across different users

    *No authentication required to access this endpoint.*
    """
    try:
        from social_writer import get_latest_generated_content

        # Use the username provided in the path parameter
        result = get_latest_generated_content(username)

        return {
            "status": "success", 
            "content": result.get("data", {}).get("documents", [])
        }
    except Exception as e:
        print(f"Error fetching latest content for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/content/{content_id}", tags=["Content Management"])
async def delete_content(content_id: str, current_user: dict = Depends(get_current_user)):
    """
    **Delete a specific generated content entry**

    This endpoint permanently removes a generated content document from the database.

    ## When to use
    Use this endpoint when you need to:
    * Remove outdated or incorrect content
    * Clean up your content repository
    * Delete test content after development

    *This action cannot be undone, and content will be permanently removed.*
    """
    try:
        from social_writer import delete_generated_content

        # Use the current user's username from the authentication
        username = current_user["username"]
        user_id = current_user["user_id"]

        result = delete_generated_content(username, content_id)

        # Check if deletion was successful
        if result.get("data", {}).get("document"):
            return {"status": "success", "message": f"Content '{content_id}' deleted successfully"}
        else:
            return {"status": "warning", "message": f"Content '{content_id}' not found or already deleted"}
    except Exception as e:
        print(f"Error deleting content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simple-repurpose", response_model=schemas.SuccessResponse, tags=["Generation"])
async def simple_repurpose_endpoint(request_data: schemas.SimpleRepurposeRequest, background_tasks: BackgroundTasks):
    """
    **Generate content variations using a simple repurposing workflow**

    This endpoint takes a social post and generates variations using multiple templates.

    ## When to use
    Use this endpoint when you need to:
    * Create multiple variations of an existing social post
    * Apply different templates to the same content
    * Get quick repurposing without manual template selection

    *This endpoint runs in the background and returns immediately with a status.*
    """
    try:
        from social_writer import simple_repurpose

        # Add the simple_repurpose function to background tasks
        background_tasks.add_task(
            simple_repurpose,
            social_post=request_data.social_post,
            brand=request_data.brand,
            repurpose_count=request_data.repurpose_count,
            workflow_id=request_data.workflow_id
        )

        # Return immediately with success message
        return {"status": "success", "message": "Your content is being generated"}
    except Exception as e:
        print(f"Error in simple repurpose: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat/reset", tags=["Utility"])
async def reset_chat_session(current_user: dict = Depends(get_current_user)):
    """
    **Reset the current chat session**

    This endpoint signals the client to start a new chat session with a fresh ID.

    ## When to use
    Use this endpoint when you need to:
    * Start a fresh conversation
    * Clear conversation history with the chatbot
    * Resolve issues with the current chat session
    """
    try:
        return {
            "status": "success", 
            "message": "Chat session reset requested",
            "username": current_user["username"],
            "user_id": current_user["user_id"]
        }
    except Exception as e:
        print(f"Error resetting chat session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/signup", response_class=HTMLResponse, include_in_schema=False)
async def signup(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})