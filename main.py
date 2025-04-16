import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from fastapi import FastAPI, HTTPException, Depends, Request, Response, status, Form, BackgroundTasks, UploadFile
from document_processor import DocumentProcessor
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jose import JWTError, jwt
from fastapi.middleware.cors import CORSMiddleware
import os
from typing import Dict
from api_middleware import check_api_key_or_jwt
from social_writer import generated_content_uploader, get_client_brand_voice, vector_search_for_published_content, metric_sorter, top_content_sentiment_setup, source_content_retriever, multitemplate_retriever, short_form_social_repurposing, top_content_to_repurposing, template_context_and_uploader, Templatizer, repurposer_using_posts_as_templates, source_content_repurposer_using_posts_as_templates, delete_user_account
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
        {"name": "Publishing History", "description": "Endpoints for tracking publication history and metrics"},
        {"name": "Industry Report Management", "description": "Endpoints for generating and managing industry reports"},
        {"name": "Utility", "description": "Utility endpoints for search and analysis"},
        {"name": "Onboarding", "description": "Endpoints for user onboarding process"},
        {"name": "Other", "description": "Miscellaneous endpoints"}
    ],
    # Hide API Keys endpoints from the docs
    openapi_url="/openapi.json",
    # Hide schemas section in the docs
    swagger_ui_parameters={"defaultModelsExpandDepth": -1}
)

# Custom exception handler for authentication failures
@app.exception_handler(HTTPException)
async def auth_exception_handler(request: Request, exc: HTTPException):
    # Only handle 401 Unauthorized errors
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        # Check if the request is coming from a browser (Accept header includes text/html)
        accept_header = request.headers.get("Accept", "")
        if "text/html" in accept_header:
            # Redirect browser requests to the login page
            return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    # For all other exceptions or API requests, return the original exception
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Security configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-dev-only-key")  # Fetch from environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

import bcrypt

# bcrypt for password hashing

# Import rate limiter
from rate_limiter import RateLimitMiddleware

# Rate limiting configuration - 300 requests per hour
app.add_middleware(RateLimitMiddleware, rate_limit_per_hour=300)

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
    # Check if user is already logged in by looking for access_token in cookies
    if request.cookies.get("access_token"):
        try:
            # Validate the token
            payload = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=[ALGORITHM])
            # If token is valid, redirect to dashboard
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        except JWTError:
            # If token is invalid, continue to login page
            pass
    
    # If no token or invalid token, show login page
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login", include_in_schema=False)
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
        # Check if input is email or username
        is_email = '@' in username

        # Query the user from the database
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }

        # Use different filter depending on login method
        if is_email:
            print(f"Login attempt using email: {username}")
            payload = {
                "findOne": {
                    "filter": {"email": username}
                }
            }
        else:
            print(f"Login attempt using username: {username}")
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
            actual_username = user.get("username", "")

            # Debug logging for password comparison
            print(f"Found user: {actual_username}")
            print(f"Stored hash exists: {bool(stored_hash)}")

            # Compare plain password with stored hash
            is_password_match = False
            if stored_hash:
                try:
                    input_encoded = password.encode('utf-8')
                    stored_encoded = stored_hash.encode('utf-8')
                    is_password_match = bcrypt.checkpw(input_encoded, stored_encoded)
                    print(f"Password comparison result: {is_password_match}")
                except Exception as e:
                    print(f"Error during password comparison: {str(e)}")

            if is_password_match:
                print(f"Login successful for user: {actual_username}")
                # Set the username and user_id as environment variables
                os.environ["CURRENT_USERNAME"] = actual_username
                os.environ["CURRENT_USER_ID"] = user_id

                # Create a short-lived access token (30 minutes for better UX)
                access_token = create_access_token(
                    data={"sub": actual_username, "user_id": user_id},
                    expires_delta=timedelta(minutes=30)
                )
                
                # Create a long-lived refresh token (30 days)
                from api_auth import create_refresh_token
                refresh_token, _ = create_refresh_token(user_id, actual_username)
                
                # Set both tokens as cookies
                response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
                response.set_cookie(
                    key="access_token", 
                    value=access_token, 
                    httponly=True,
                    max_age=1800,  # 30 minutes in seconds
                    path="/"
                )
                response.set_cookie(
                    key="refresh_token", 
                    value=refresh_token, 
                    httponly=True,
                    max_age=2592000,  # 30 days in seconds
                    path="/"
                )
                return response
            else:
                login_type = "email" if is_email else "username"
                print(f"Login failed for {login_type}: {username}")
                return templates.TemplateResponse(
                    "login.html",
                    {"request": request, "error": "Invalid credentials"},
                    status_code=status.HTTP_401_UNAUTHORIZED
                )

        # If authentication fails or user doesn't exist
        login_type = "email" if is_email else "username"
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": f"No user found with this {login_type}"},
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
        # Check if there's a refresh token we can use
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            # Try to use the refresh token endpoint
            return await refresh_access_token_from_cookie(request, refresh_token)
        raise credentials_exception
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id", "")
        if username is None:
            raise credentials_exception
        return {"username": username, "user_id": user_id}
    except JWTError:
        # Token is invalid, try to refresh
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            return await refresh_access_token_from_cookie(request, refresh_token)
        raise credentials_exception

async def refresh_access_token_from_cookie(request: Request, refresh_token: str):
    """
    Helper function to refresh an access token using a refresh token from cookie.
    Returns user info if successful, otherwise raises an exception.
    """
    from api_auth import validate_refresh_token
    import logging
    
    logging.info("Attempting to refresh access token from cookie")
    
    # Validate the refresh token
    user_info = validate_refresh_token(refresh_token)
    if not user_info:
        logging.error("Invalid refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create a new access token
    access_token = create_access_token(
        data={"sub": user_info["username"], "user_id": user_info["user_id"]},
        expires_delta=timedelta(minutes=15)
    )
    
    # Get current context to see if we can set cookies
    from starlette.background import BackgroundTask
    
    def set_cookies_on_response(response):
        response.set_cookie(
            key="access_token", 
            value=access_token, 
            httponly=True,
            max_age=900,  # 15 minutes in seconds
            path="/"
        )
        # Also refresh the refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            max_age=2592000,  # 30 days in seconds
            path="/"
        )
        logging.info("Cookies set on response")
        
    # Try to set cookies in different ways depending on context
    try:
        # Check if we have a response object in request state
        if hasattr(request, "state") and hasattr(request.state, "response"):
            set_cookies_on_response(request.state.response)
            logging.info("Set cookies on response in request state")
        else:
            # Try to add a background task to set cookies
            request.scope["_background"] = BackgroundTask(set_cookies_on_response)
            logging.info("Added background task to set cookies")
    except Exception as e:
        logging.error(f"Error setting cookies: {str(e)}")
        # We're not in a route context, the cookie will be refreshed on the next request
        pass
        
    # Return the user info
    logging.info(f"Refreshed access token for user: {user_info['username']}")
    return {"username": user_info["username"], "user_id": user_info["user_id"]}

@app.get("/api/refresh-token", tags=["Authentication"])
async def refresh_access_token(request: Request, response: Response):
    """
    **Refresh an expired access token using a valid refresh token**
    
    This endpoint validates the refresh token and issues a new access token.
    
    ## When to use
    Use this endpoint when:
    * Access token has expired but refresh token is still valid
    * You need to extend a user's session without requiring re-login
    * You want to maintain persistent authentication with better security
    
    *The refresh token should be provided in the HTTP-only cookie.*
    """
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    from api_auth import validate_refresh_token
    
    # Validate the refresh token
    user_info = validate_refresh_token(refresh_token)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create a new access token
    access_token = create_access_token(
        data={"sub": user_info["username"], "user_id": user_info["user_id"]},
        expires_delta=timedelta(minutes=15)
    )
    
    # Set the new access token cookie
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True,
        max_age=900,  # 15 minutes in seconds
        path="/"
    )
    
    # Also refresh the refresh token cookie to extend the session
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=2592000,  # 30 days in seconds
        path="/"
    )
    
    return {"status": "success", "message": "Access token refreshed successfully"}

@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(request: Request, current_user: dict = Depends(get_current_user)):
    # Check for source content
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_source_content"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "filter": {"user_id": current_user["user_id"]},
            "options": {"limit": 1}  # We only need to check if any content exists
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    has_source_content = bool(response.json().get("data", {}).get("documents", []))

    # Get source content count
    from source_content_manager import count_user_documents, count_user_files
    doc_count = count_user_documents(current_user["user_id"])
    file_count = count_user_files(current_user["user_id"])
    
    # Get content counts by status
    draft_count = 0
    awaiting_publishing_count = 0
    published_count = 0
    try:
        generated_content_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/generated_content"
        
        # Count draft content
        draft_payload = {
            "countDocuments": {
                "filter": {
                    "user_id": current_user["user_id"],
                    "status": "Draft"
                }
            }
        }
        
        draft_response = requests.post(generated_content_url, headers=headers, json=draft_payload)
        if draft_response.status_code == 200:
            draft_count = draft_response.json().get("status", {}).get("count", 0)
            
        # Count awaiting publishing content
        awaiting_payload = {
            "countDocuments": {
                "filter": {
                    "user_id": current_user["user_id"],
                    "status": "Approved"
                }
            }
        }
        
        awaiting_response = requests.post(generated_content_url, headers=headers, json=awaiting_payload)
        if awaiting_response.status_code == 200:
            awaiting_publishing_count = awaiting_response.json().get("status", {}).get("count", 0)
            
        # Count published content
        published_payload = {
            "countDocuments": {
                "filter": {
                    "user_id": current_user["user_id"],
                    "status": "Published"
                }
            }
        }
        
        published_response = requests.post(generated_content_url, headers=headers, json=published_payload)
        if published_response.status_code == 200:
            published_count = published_response.json().get("status", {}).get("count", 0)
            
    except Exception as e:
        print(f"Error counting content: {str(e)}")

    print(f"User data loaded for {current_user['username']}, has_source_content: {has_source_content}, doc_count: {doc_count}, draft_count: {draft_count}, awaiting_publishing_count: {awaiting_publishing_count}, published_count: {published_count}")

    # Get follower count from user's profile
    follower_count = 0
    social_count = 0
    try:
        user_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        user_payload = {
            "findOne": {
                "filter": {"user_id": current_user["user_id"]}
            }
        }
        
        user_response = requests.post(user_url, headers=headers, json=user_payload)
        if user_response.status_code == 200:
            user_data = user_response.json()
            user_profile = user_data.get("data", {}).get("document", {}).get("profile", {})
            follower_count = user_profile.get("follower_count", 0)
            
            # Count social media accounts
            socials = user_profile.get("socials", {})
            social_count = sum(1 for value in socials.values() if value)
            
            print(f"Retrieved follower count for user: {follower_count}")
            print(f"Connected social accounts: {social_count}")
    except Exception as e:
        print(f"Error retrieving user data: {str(e)}")
        
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "dashboard",
        "show_onboarding": not has_source_content,
        "doc_count": doc_count,
        "file_count": file_count,
        "draft_count": draft_count,
        "awaiting_publishing_count": awaiting_publishing_count,
        "published_count": published_count,
        "follower_count": follower_count,
        "social_count": social_count
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
async def get_workflows(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve all generation workflow configurations**

    This endpoint fetches all system workflows available for all users.

    ## When to use
    Use this endpoint when you need to:
    * **List all available workflows** for user selection
    * Get an overview of configured generation processes
    * Select a workflow for content generation

    *This endpoint supports both JWT and API key authentication.*
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Use the system keyspace for workflows instead of user-specific
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/sys_keyspace/workflows"

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

@app.get("/api/user-workflows", tags=["Generation Flows"])
async def get_user_workflows(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve generation workflow configurations for the current user**

    This endpoint fetches all workflows created by or available to the current user.

    ## When to use
    Use this endpoint when you need to:
    * **List all available workflows** specific to the user
    * Get an overview of your custom generation processes
    * Select a personal workflow for content generation

    *This endpoint supports both JWT and API key authentication.*
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get user ID from authenticated user
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in authentication context")

    # Query the user-specific workflows collection
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_workflows"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    payload = {"find": {"filter": {"user_id": user_id}}}

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user-brands", tags=["Brand Management"])
async def get_user_brands(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve brands for the current user**

    This endpoint fetches all brands created by or available to the current user.

    ## When to use
    Use this endpoint when you need to:
    * **List all available brands** specific to the user
    * Get a list of brands for selection in content generation
    * Access brand information for content creation

    *This endpoint supports both JWT and API key authentication.*
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get user ID from authenticated user
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in authentication context")

    print(f"\n=== Debug: User Brands Request Started ===")
    print(f"User ID: {user_id}")

    # Query the brands collection
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/brands"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # Query for brands matching the user_id
    payload = {
        "find": {
            "filter": {"user_id": user_id}
        }
    }

    print(f"Request URL: {url}")
    print(f"Request payload: {json.dumps(payload, indent=2)}")

    try:
        print(f"Sending request to AstraDB...")
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status code: {response.status_code}")

        # Log truncated response for debugging
        response_text = response.text
        print(f"Response preview: {response_text[:200]}{'...' if len(response_text) > 200 else ''}")

        response.raise_for_status()
        result = response.json()

        brands = result.get("data", {}).get("documents", [])
        print(f"Found {len(brands)} brands for user {user_id}")
        print(f"=== Debug: User Brands Request Completed ===\n")

        return {
            "status": "success",
            "brands": brands
        }
    except Exception as e:
        print(f"Error fetching brands: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/create/brand-voice", response_class=HTMLResponse, include_in_schema=False)
async def create_brand_voice(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("brand_voice.html", {
        "request": request,
        "username": current_user,
        "current_page": "create_brand_voice"
    })

@app.get("/source-content-management", response_class=HTMLResponse, include_in_schema=False)
async def source_content_management(request: Request, current_user: dict = Depends(get_current_user)):
    # Get user data from AstraDB
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    payload = {
        "findOne": {
            "filter": {"user_id": current_user["user_id"]}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        user_data = response.json()

        # Count social media accounts
        socials = user_data.get("data", {}).get("document", {}).get("profile", {}).get("socials", {})
        social_count = sum(1 for value in socials.values() if value)
    except Exception as e:
        print(f"Error fetching user data: {str(e)}")
        social_count = 0

    from source_content_manager import count_user_documents

    # Get document count
    doc_count = count_user_documents(current_user["user_id"])

    return templates.TemplateResponse("source_content_management.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "source_content_management",
        "social_count": social_count,
        "doc_count": doc_count
    })

@app.get("/create/templatizer", response_class=HTMLResponse, include_in_schema=False)
async def create_templatizer(request: Request, current_user: str = Depends(get_current_user)):
    return templates.TemplateResponse("templatizer.html", {
        "request": request,
        "username": current_user,
        "current_page": "create_templatizer"
    })

@app.get("/settings", response_class=HTMLResponse, include_in_schema=False)
async def settings_page(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "settings"
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

@app.get("/industry-report", response_class=HTMLResponse, include_in_schema=False)
async def industry_report(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("industry_report.html", {
        "request": request,
        "username": current_user,
        "current_page": "industry_report"
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

@app.get("/publish-history", response_class=HTMLResponse, include_in_schema=False)
async def publish_history(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("publish_history.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "publish_history"
    })

@app.get("/api/user-publications", tags=["Publishing History"])
async def get_user_publications(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve published content for the current user**
    
    This endpoint fetches all publications created by the current user,
    including metrics and status information.
    
    ## When to use
    Use this endpoint when you need to:
    * View your publication history
    * Track performance metrics across publications
    * Analyze content effectiveness
    
    *This endpoint supports both JWT and API key authentication.*
    """
    print("\n=== DEBUG: /api/user-publications endpoint called ===")
    print(f"User context: {user}")
    
    try:
        from publish_history_manager import retrievePublications
        
        # Get user ID from authenticated user
        user_id = user.get("user_id")
        print(f"Extracted user_id: {user_id}")
        
        if not user_id:
            print("ERROR: User ID not found in authentication context")
            raise HTTPException(status_code=401, detail="User ID not found in authentication context")
            
        print(f"Calling retrievePublications with user_id: {user_id}")
        result = retrievePublications(user_id)
        
        print(f"Retrieved result status: {result.get('status')}")
        print(f"Publication count: {len(result.get('publications', []))}")
        
        if result.get("status") == "error":
            print(f"Error in result: {result.get('message')}")
            raise HTTPException(status_code=500, detail=result.get("message"))
         
        print("=== DEBUG: /api/user-publications completed successfully ===\n")   
        return result
    except Exception as e:
        print(f"ERROR in get_user_publications: {str(e)}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        print("=== DEBUG: /api/user-publications failed ===\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/publication-metrics/{publication_id}", tags=["Publishing History"])
async def get_publication_metrics(publication_id: str, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve detailed metrics for a specific publication**
    
    This endpoint fetches comprehensive performance metrics for a single publication.
    
    ## When to use
    Use this endpoint when you need to:
    * Analyze detailed metrics for a specific post
    * Compare weighted and raw metrics
    * Access performance score information
    
    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from publish_history_manager import getPublicationMetrics
        
        result = getPublicationMetrics(publication_id)
        
        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))
            
        return result
    except Exception as e:
        print(f"Error fetching publication metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api-keys", response_class=HTMLResponse, include_in_schema=False)
async def api_keys_page(request: Request, current_user: dict = Depends(get_current_user)):
    return templates.TemplateResponse("api_keys.html", {
        "request": request,
        "username": current_user["username"],
        "user_id": current_user["user_id"],
        "current_page": "api_keys"
    })

@app.get("/logout", include_in_schema=False)
async def logout(request: Request, response: Response):
    # Clear the username environment variable on logout
    if "CURRENT_USERNAME" in os.environ:
        del os.environ["CURRENT_USERNAME"]
    
    # Revoke the refresh token if it exists
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        try:
            from api_auth import validate_refresh_token, revoke_refresh_token
            token_info = validate_refresh_token(refresh_token)
            if token_info and token_info.get("token_id"):
                revoke_refresh_token(token_info["token_id"])
        except Exception as e:
            print(f"Error revoking refresh token: {str(e)}")

    response = RedirectResponse(url="/login")
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
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

# Include routers
app.include_router(onboarding_router)

# Create custom OpenAPI function to exclude specified tags
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Tags to exclude from documentation
    tags_to_exclude = ["API Keys", "default", "Onboarding", "Utility", "Storage", "User Management"]
    
    # Filter out paths with excluded tags
    paths_to_keep = {}
    for path, path_item in openapi_schema["paths"].items():
        exclude_path = False
        for operation in path_item.values():
            if "tags" in operation:
                for tag in tags_to_exclude:
                    if tag in operation["tags"]:
                        exclude_path = True
                        break
            if exclude_path:
                break
        if not exclude_path:
            paths_to_keep[path] = path_item
    
    openapi_schema["paths"] = paths_to_keep
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Import and include API routes
from api_routes import router as api_router
from api_key_routes import router as api_key_router
from brand_management import router as brand_management_router
from fastapi.openapi.utils import get_openapi

app.include_router(api_router)
app.include_router(api_key_router)  # Still include the router so endpoints work
app.include_router(brand_management_router)

# Override the openapi function
app.openapi = custom_openapi

@app.get("/", include_in_schema=False)
def read_root():
    return {"Hello": "World"}

@app.post("/api/upload-file", tags=["Content Management"])
async def upload_file(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    user: dict = Depends(check_api_key_or_jwt)
):
    """
    **Upload a file (PDF or Markdown) for processing into source content**

    This endpoint allows users to upload document files that will be processed into source content chunks.

    ## When to use
    Use this endpoint when you need to:
    * Add new content sources to your knowledge base
    * Process documents into AI-ready content chunks
    * Import external content into your content generation system

    *This endpoint supports both JWT and API key authentication.*
    """
    print("\n=== File Upload Debug ===")
    print(f"Received file: {file.filename}")
    print(f"Content type: {file.content_type}")
    print(f"User ID: {user['user_id']}")
    print(f"Auth method: {user.get('auth_source', 'unknown')}")

    # Validate file type
    if not (file.filename.lower().endswith('.pdf') or 
            file.filename.lower().endswith('.md') or 
            file.filename.lower().endswith('.txt') or 
            file.filename.lower().endswith('.docx')):
        print("File type validation failed")
        raise HTTPException(status_code=400, detail="Only PDF, Markdown, TXT, and DOCX files are supported")

    try:
        print("Creating DocumentProcessor instance...")
        processor = DocumentProcessor()

        # Store file in Object Storage first
        file_id = await processor.store_file(file.file, file.filename, user["user_id"])
        print(f"File stored with ID: {file_id}")
        
        # Schedule background processing
        print("Scheduling background processing...")
        background_tasks.add_task(
            processor.process_file_background,
            file.filename, 
            file_id, 
            user["user_id"]
        )

        # Return success immediately
        print(f"Returning success response before background processing completes")
        return {"status": "success", "file_id": file_id, "message": "File upload successful, processing in background"}
    except Exception as e:
        print(f"Error handling file: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error traceback:", e.__traceback__)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/generation-flow", response_model=schemas.SuccessResponse, tags=["Generation Flows"])
async def create_generation_flow(request_data: schemas.GenerationFlowRequest, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    # Get the current user's user_id from the authenticated user or environment
    user_id = user.get("user_id") or os.environ.get("CURRENT_USER_ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in authentication context")

    # Use the user_content_keyspace/user_workflows collection
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/user_workflows"

    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER,
        "Content-Type": "application/json"
    }

    # Convert the Pydantic model objects to dictionaries first
    steps_dict = [step.dict() for step in request_data.steps]

    # Create the document object with the new schema
    document = {
        "workflow_id": request_data.workflowId,
        "user_id": user_id,
        "workflow_name": request_data.workflow_name if hasattr(request_data, 'workflow_name') else request_data.workflowId,
        "workflow_type": request_data.workflowType.lower(),
        "description": request_data.description,
        "steps": {
            "steps": steps_dict
        },
        "metadata": {
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
            "updated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
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

@app.post("/api/upload-post", response_model=Dict, tags=["Content Management"])
async def upload_post(content_data: schemas.ContentUploadRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Upload generated post to the posts database**

    This endpoint stores posts that have been generated along with their metadata for future reference and retrieval.

    ## When to use
    Use this endpoint when you need to:
    * **Store newly generated posts** after creation
    * **Preserve the relationship** between posts and their source material
    * **Track templates** used for specific post pieces
    * Build a **searchable knowledge base** of posts for later reference

    *This endpoint should be called after post generation to ensure all posts are properly archived.*
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/brand-voice", response_model=Dict, tags=["Brand Management"])
async def get_brand_voice(request_data: schemas.BrandVoiceRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve brand voice and tone guidelines**

    This endpoint fetches the complete brand voice profile, including tone, style, and communication guidelines for a specific brand.

    ## When to use
    Use this endpoint when you need to:
    * **Apply consistent branding** to generated content
    * Access **tone and style guidelines** for content creation
    * Ensure content reflects the **brand personality**
    * Incorporate brand-specific **terminology and phrasing**

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        # Get the user ID from the authenticated user or from request data
        user_id = request_data.user_id or user.get("user_id")
        brand = request_data.brand

        # Print debugging information before calling get_client_brand_voice
        auth_method = user.get("auth_source", "unknown")
        print(f"\n=== Debug: Calling get_client_brand_voice for brand: {brand}, user ID: {user_id} ===")
        print(f"=== Debug: Authenticated using: {auth_method} ===")

        result = get_client_brand_voice(brand, user_id)
        print(f"=== Debug: API Response: {result} ===\n")
        return result
    except Exception as e:
        print(f"\n=== Debug: Error in get_brand_voice: {str(e)} ===\n")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/vector-search", response_model=Dict, tags=["Utility"])
async def vector_search(request_data: schemas.VectorSearchRequest, current_user: dict = Depends(get_current_user)):
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

@app.post("/api/sentiment-setup", response_model=Dict, tags=["Utility"])
async def setup_sentiment(request_data: schemas.SentimentSetupRequest, current_user: dict = Depends(get_current_user)):
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

@app.post("/api/top-content", response_model=Dict, tags=["Content Management"])
async def get_top_content(request_data: schemas.TopContentRequest, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/source-content", response_model=Dict, tags=["Content Management"])
async def get_source_content(request_data: schemas.SourceContentRequest, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/generate-new-content", response_model=schemas.SuccessResponse, tags=["Generation"])
async def generate_new_content(request_data: schemas.RepurposeRequest, background_tasks: BackgroundTasks, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Generate new content based on a topic query for a specific brand.**

    This endpoint generates new content based on source content and brand voice.

    ## When to use
    Use this endpoint when you need to:
    * Generate content from scratch based on a topic
    * Create multiple content pieces at once without templates
    * Need simple content generation directly from source material

    *This endpoint runs in the background and doesn't provide immediate results.*
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/top-content-repurposing", response_model=schemas.SuccessResponse, tags=["Generation"])
async def get_top_content_repurposing(request_data: schemas.TopContentRepurposingRequest, background_tasks: BackgroundTasks, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Repurpose top performing content**

    This endpoint identifies top content based on metrics and creates new variations.

    ## When to use
    Use this endpoint when you need to:
    * Create content based on your **best performing** existing posts
    * Leverage performance metrics to guide content generation
    * Create variations of successful content patterns

    *This performs an automatic selection of high-performing content before repurposing.*
    *This endpoint supports both JWT and API key authentication.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN notconfigured")

    try:
        # Add task to background using the new module
        from top_content_repurposer import top_content_to_repurposing

        background_tasks.add_task(
            top_content_to_repurposing, 
            request_data.query, 
            request_data.brand, 
            request_data.number_of_posts, 
            request_data.repurpose_count, 
            request_data.workflow_id
        )

        # Return immediately
        return {"status": "success", "message": "Content is now being generated"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/social-post-generation", response_model=schemas.SocialPostGenerationResponse, tags=["Generation"])
async def generate_social_post(request_data: schemas.SocialPostGenerationRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Generate a social media post using a specified workflow.**

    This endpoint creates social media content based on template, brand voice, and content chunks.

    ## When to use
    Use this endpoint when you need to:
    * Generate a **single post** with immediate response
    * Have complete control over the workflow, template, and content
    * Need to see results immediately rather than in the background

    *Unlike other generation endpoints, this returns the content immediately.*
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/template-context-and-uploader", response_model=Dict, tags=["Template Management"])
async def create_template_embedding(request_data: schemas.TemplateContextRequest, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = template_context_and_uploader(
            template=request_data.template,
            category=request_data.category
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/flow-config/{workflow_id}", tags=["Generation Flows"])
async def get_flow_config(workflow_id: str, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/templatizer", response_model=schemas.TemplatizerResponse, tags=["Template Management"])
async def create_template(request_data: schemas.TemplatizerRequest, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/multitemplate", response_model=Dict, tags=["Template Management"])
async def get_multitemplate(request_data: schemas.MultitemplateRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Find templates that match specific content**

    This endpoint uses semantic search to identify templates best suited for a particular content chunk.

    ## When to use
    Use this endpoint when you need to:
    * **Find appropriate templates** for specific content
    * Get **multiple formatting options** for a content piece
    * **Automatically match** content with compatible templates
    * Enhance content presentation with optimized formatting
    * Access templates from system database, user database, or both

    *This endpoint requires templates to be previously processed with `/template-context-and-uploader`.*
    *This endpoint supports both JWT and API key authentication.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN not configured")
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    try:
        result = multitemplate_retriever(
            content_chunk=request_data.content_chunk, 
            template_count_to_retrieve=request_data.template_count,
            db_to_access=request_data.db_to_access
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/repurpose-with-templates", response_model=Dict, tags=["Generation"])
async def repurpose_with_templates(request_data: schemas.RepurposeWithTemplatesRequest, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
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

@app.post("/api/template-search", response_model=Dict, tags=["Template Management"])
async def search_templates(request_data: schemas.MultitemplateRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Search for templates matching specific content**

    This endpoint uses semantic search to identify templates best suited for a particular content chunk,
    without additional AI analysis of the content.

    ## When to use
    Use this endpoint when you need to:
    * **Find appropriate templates** for specific content
    * Get **multiple formatting options** for a content piece
    * **Directly search templates** without additional processing
    * Perform faster template searches for performance-sensitive applications
    * Access templates from system database, user database, or both

    *This endpoint supports both JWT and API key authentication.*
    """
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    print("Performing template search...")
    print("Received request data:", request_data)   
    
    try:
        from social_writer import template_search
        result = template_search(
            text_query=request_data.content_chunk, 
            template_count=request_data.template_count,
            db_to_access=request_data.db_to_access,
            category=request_data.category
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/source-content-repurpose-with-templates", response_model=schemas.SuccessResponse, tags=["Generation"])
async def repurpose_source_content_with_templates(
    request_data: schemas.SourceContentRepurposeWithTemplatesRequest, 
    background_tasks: BackgroundTasks,
    user: dict = Depends(check_api_key_or_jwt)
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
    *This endpoint supports both JWT and API key authentication.*
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
async def delete_generation_flow(workflow_id: str, user: dict = Depends(check_api_key_or_jwt)):
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
    *This endpoint supports both JWT and API key authentication.*
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

@app.get("/api/latest-posts", tags=["Generation"])
async def get_latest_generated_posts(user: dict = Depends(check_api_key_or_jwt)):
    """
    **Retrieve the latest generated posts for the current user**

    This endpoint fetches the most recent posts generated by the current user,
    sorted by creation timestamp.

    ## When to use
    Use this endpoint when you need to:
    * View your most recently generated posts
    * Track your latest post generation activities
    * Retrieve posts for editing or review

    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from social_writer import get_latest_generated_content

        # Use the current user's username from the authentication
        username = user["username"]
        user_id = user["user_id"]

        result = get_latest_generated_content(username)

        return {
            "status": "success", 
            "posts": result.get("data", {}).get("documents", []),
            "user_id": user_id
        }
    except Exception as e:
        print(f"Error fetching latest posts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/latest-posts/{username}", tags=["Generation"])
async def get_latest_posts_by_username(username: str):
    """
    **Retrieve the latest generated posts for a specified username**

    This endpoint fetches the most recent posts generated by the specified username,
    sorted by creation timestamp.

    ## When to use
    Use this endpoint when you need to:
    * View posts generated by a specific user
    * Access posts across multiple user accounts
    * Compare post generation across different users

    *No authentication required to access this endpoint.*
    """
    try:
        from social_writer import get_latest_generated_content

        # Use the username provided in the path parameter
        result = get_latest_generated_content(username)

        return {
            "status": "success", 
            "posts": result.get("data", {}).get("documents", [])
        }
    except Exception as e:
        print(f"Error fetching latest posts for {username}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/post/{post_id}", tags=["Generation"])
async def delete_post(post_id: str, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Delete a specific generated post entry**

    This endpoint permanently removes a generated post document from the database.

    ## When to use
    Use this endpoint when you need to:
    * Remove outdated or incorrect posts
    * Clean up your posts repository
    * Delete test posts after development

    *This action cannot beundone, and posts will be permanently removed.*
    *This endpoint supports both JWT and API key authentication.*
    """
    try:
        from social_writer import delete_generated_content

        # Use the current user's username from the authentication
        username = user["username"]
        user_id = user["user_id"]

        result = delete_generated_content(username, post_id)

        # Check if deletion was successful
        if result.get("data", {}).get("document"):
            return {"status": "success", "message": f"Post '{post_id}' deleted successfully"}
        else:
            return {"status": "warning", "message": f"Post '{post_id}' not found or already deleted"}
    except Exception as e:
        print(f"Error deleting post: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/update-post-status", tags=["Generation"])
async def update_post_status(request_data: schemas.PostStatusUpdateRequest, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Update the status of a generated post**

    This endpoint updates the status of a post to either 'Approved' or 'Rejected'.

    ## When to use
    Use this endpoint when you need to:
    * Approve posts for publishing
    * Reject posts that don't meet quality standards
    * Change the workflow status of content

    *This endpoint supports both JWT and API key authentication.*
    """
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not ASTRA_DB_APPLICATION_TOKEN:
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    post_id = request_data.post_id
    new_status = request_data.status

    # Validate status
    if new_status not in ["Approved", "Rejected", "Published"]:
        raise HTTPException(status_code=400, detail="Status must be 'Approved', 'Rejected', or 'Published'")

    # Get the current user's ID from the authenticated user
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found in authentication context")

    # Prepare the API request to AstraDB
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/user_content_keyspace/generated_content"
    
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "findOneAndUpdate": {
            "filter": {"$and": [
                {"_id": post_id},
                {"user_id": user_id}  # Ensure user can only update their own posts
            ]},
            "update": { 
                "$set": { 
                    "status": new_status,
                    "Approval_Date": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                } 
            }
        }
    }

    try:
        print(f"\n=== Debug: Updating Post Status ===")
        print(f"Post ID: {post_id}")
        print(f"New Status: {new_status}")
        print(f"User ID: {user_id}")
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        
        # Check if update was successful
        if result.get("data", {}).get("document"):
            print(f"Post status updated successfully")
            return {"status": "success", "message": f"Post status updated to '{new_status}'"}
        else:
            print(f"Post not found or no update made: {result}")
            return {"status": "warning", "message": "Post not found or no changes were made"}
            
    except Exception as e:
        print(f"Error updating post status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/simple-repurpose", response_model=schemas.SuccessResponse, tags=["Generation"])
async def simple_repurpose_endpoint(request_data: schemas.SimpleRepurposeRequest, background_tasks: BackgroundTasks, user: dict = Depends(check_api_key_or_jwt)):
    """
    **Generate content variations using a simple repurposing workflow**

    This endpoint takes a social post and generates variations using multiple templates.

    ## When to use
    Use this endpoint when you need to:
    * Create multiple variations of an existing social post
    * Apply different templates to the same content
    * Get quick repurposing without manual template selection

    *This endpoint runs in the background and returns immediately with a status.*
    *This endpoint supports both JWT and API key authentication.*
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
    # Check if user is already logged in
    if request.cookies.get("access_token"):
        try:
            # Validate the token
            payload = jwt.decode(request.cookies.get("access_token"), SECRET_KEY, algorithms=[ALGORITHM])
            # If token is valid, redirect to dashboard
            return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
        except JWTError:
            # If token is invalid, continue to signup page
            pass
    
    # If no token or invalid token, show signup page
    return templates.TemplateResponse("signup.html", {"request": request})

@app.delete("/api/user/{identifier}", tags=["User Management"])
async def delete_user(identifier: str, delete_by: str = "username"):
    """
    **Delete a user account**

    This endpoint permanently deletes a user account from the database.
    The user can be identified by either username or _id.

    ## When to use
    Use this endpoint when you need to:
    * Remove a user account from the system
    * Clean up user data
    * Handle account deletion requests

    *This action cannot be undone, and all user data will be permanently removed.*
    """
    if not os.getenv("ASTRA_DB_API_ENDPOINT"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_API_ENDPOINT not configured")
    if not os.getenv("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER"):
        raise HTTPException(status_code=500, detail="ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured")

    try:
        from social_writer import delete_user_account
        result = delete_user_account(identifier, delete_by)

        if result.get("data", {}).get("document"):
            return {
                "status": "success", 
                "message": f"User {identifier} deleted successfully"
            }
        else:
            raise HTTPException(
                status_code=404, 
                detail=f"User with {delete_by} '{identifier}' not found"
            )
    except Exception as e:
        print(f"Error deleting user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))