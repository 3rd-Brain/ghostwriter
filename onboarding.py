import os
import json
import uuid
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, Request, Depends, Header
from pydantic import BaseModel, Field
import requests
from jose import jwt
from source_content_manager import gather_user_tweets, tweet_to_source_content

# Define Pydantic models for request/response validation
class OnboardingInitRequest(BaseModel):
    email: str = Field(..., description="User's email address")

class OnboardingSession(BaseModel):
    session_token: str = Field(..., description="Session token for tracking progress")
    expires_at: str = Field(..., description="Expiration timestamp")

class StepDataRequest(BaseModel):
    form_data: Dict = Field(..., description="Form data for the specific step")

class OnboardingProgressResponse(BaseModel):
    user_id: Optional[str] = Field(None, description="Temporary or permanent user ID")
    email: str = Field(..., description="User's email address")
    step: str = Field(..., description="Current step in the onboarding flow")
    completed_steps: List[str] = Field(..., description="Array of completed steps")
    last_updated: str = Field(..., description="Last updated timestamp")
    expires_at: str = Field(..., description="Expiration timestamp")
    form_data: Dict = Field(..., description="Collected form data for all completed steps")

class OnboardingCompleteRequest(BaseModel):
    pass

# Create API router
router = APIRouter(prefix="/sys/onboarding", tags=["Onboarding"])

# Configurations
SECRET_KEY = os.environ.get("SECRET_KEY", "your-secret-key-keep-it-secret")
ALGORITHM = "HS256"
SESSION_TOKEN_EXPIRE_DAYS = 7

# AstraDB configuration
ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

# Helper functions
def create_session_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=SESSION_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire

def decode_session_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        session_id = payload.get("sub")
        if session_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

async def get_onboarding_session(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization.split(" ")[1]
    payload = decode_session_token(token)

    # Verify the session still exists in the database
    session_id = payload.get("sub")
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/onboarding_progress"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    # Query to find the session
    query_payload = {
        "findOne": {
            "filter": {"_id": session_id}
        }
    }

    response = requests.post(url, headers=headers, json=query_payload)
    if response.status_code != 200 or not response.json().get("data", {}).get("document"):
        raise HTTPException(status_code=401, detail="Session not found or expired")

    return payload, response.json().get("data", {}).get("document")

# API Endpoints
@router.post("/init", response_model=OnboardingSession)
async def init_onboarding(request: OnboardingInitRequest):
    """Create a new onboarding session and return a tracking token"""

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        raise HTTPException(status_code=500, detail="Database configuration error")

    # Generate a unique ID for the session
    session_id = str(uuid.uuid4())

    # Create expiration date (7 days from now)
    expires_delta = timedelta(days=SESSION_TOKEN_EXPIRE_DAYS)
    expires_at = datetime.utcnow() + expires_delta

    # Create a JWT session token
    token, expire_datetime = create_session_token(
        data={"sub": session_id, "email": request.email},
        expires_delta=expires_delta
    )

    # Store the session in AstraDB
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/onboarding_progress"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    # Prepare session document
    document = {
        "_id": session_id,
        "user_id": session_id,  # Initially, user_id is the same as session_id
        "email": request.email,
        "step": "account_basics",  # Initial step
        "completed_steps": [],
        "last_updated": datetime.utcnow().isoformat(),
        "expires_at": expires_at.isoformat(),
        "form_data": {},
        "session_id": session_id
    }

    payload = {
        "insertOne": {
            "document": document
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        return {
            "session_token": token,
            "expires_at": expires_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize onboarding: {str(e)}")

@router.post("/step/{step_name}")
async def save_step_data(step_name: str, request: StepDataRequest, session_data=Depends(get_onboarding_session)):
    """Save data for a specific onboarding step"""
    payload, document = session_data
    session_id = payload.get("sub")

    # Check if this is a valid step
    valid_steps = ["account_basics", "profile_basics", "social_media"]
    if step_name not in valid_steps:
        raise HTTPException(status_code=400, detail=f"Invalid step: {step_name}")

    # Get current step index and validate step order
    current_step = document.get("step", "account_basics")
    current_index = valid_steps.index(current_step)
    requested_index = valid_steps.index(step_name)

    # Only allow moving to the next step or updating current step
    if requested_index > current_index + 1:
        raise HTTPException(status_code=400, detail="Steps must be completed in order")

    # Update the document with the new step data
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/onboarding_progress"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    # Update form data for this step
    form_data = document.get("form_data", {})
    form_data[step_name] = request.form_data

    # Update completed steps
    completed_steps = document.get("completed_steps", [])
    if step_name not in completed_steps:
        completed_steps.append(step_name)

    # Determine next step
    next_step = step_name
    if step_name == current_step and current_index < len(valid_steps) - 1:
        next_step = valid_steps[current_index + 1]

    # Hash password if this is the account_basics step
    if step_name == "account_basics" and "password" in request.form_data:
        print("\n=== Debug Password Hashing During Registration ===")
        password = request.form_data["password"]
        print(f"Raw password: {password}")
        print(f"Raw password type: {type(password)}")

        password_encoded = password.encode('utf-8')
        print(f"Password encoded: {password_encoded}")
        print(f"Password encoded type: {type(password_encoded)}")

        salt = bcrypt.gensalt()
        print(f"Generated salt: {salt}")
        print(f"Generated salt type: {type(salt)}")

        hashed = bcrypt.hashpw(password_encoded, salt)
        print(f"Generated hash: {hashed}")
        print(f"Generated hash type: {type(hashed)}")

        decoded_hash = hashed.decode('utf-8')
        print(f"Decoded hash for storage: {decoded_hash}")
        print(f"Decoded hash type: {type(decoded_hash)}")

        request.form_data["password"] = decoded_hash
        print("=== End Debug Section ===\n")

    update_payload = {
        "updateOne": {
            "filter": {"_id": session_id},
            "update": {
                "$set": {
                    "step": next_step,
                    "completed_steps": completed_steps,
                    "last_updated": datetime.utcnow().isoformat(),
                    "form_data": form_data
                }
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=update_payload)
        response.raise_for_status()
        return {"status": "success", "message": f"Step {step_name} saved successfully", "next_step": next_step}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save step data: {str(e)}")

@router.get("/step/{step_name}")
async def get_step_data(step_name: str, session_data=Depends(get_onboarding_session)):
    """Retrieve data for a specific onboarding step"""
    payload, document = session_data

    # Check if this step has data
    form_data = document.get("form_data", {})
    step_data = form_data.get(step_name, {})

    return {"status": "success", "data": step_data}

@router.put("/step/{step_name}")
async def update_step_data(step_name: str, request: StepDataRequest, session_data=Depends(get_onboarding_session)):
    """Update data for a specific onboarding step"""
    payload, document = session_data
    session_id = payload.get("sub")

    # Check if this is a valid step
    valid_steps = ["account_basics", "profile_basics", "social_media"]
    if step_name not in valid_steps:
        raise HTTPException(status_code=400, detail=f"Invalid step: {step_name}")

    # Update the document with the updated step data
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/onboarding_progress"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    # Update form data for this step
    form_data = document.get("form_data", {})
    form_data[step_name] = request.form_data

    update_payload = {
        "updateOne": {
            "filter": {"_id": session_id},
            "update": {
                "last_updated": datetime.utcnow().isoformat(),
                "form_data": form_data
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=update_payload)
        response.raise_for_status()
        return {"status": "success", "message": f"Step {step_name} updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update step data: {str(e)}")

@router.post("/complete")
async def complete_onboarding(request: OnboardingCompleteRequest, session_data=Depends(get_onboarding_session)):
    """Finalize onboarding and create user account"""
    payload, document = session_data
    session_id = payload.get("sub")

    # Check if all required steps are completed
    required_steps = ["account_basics", "profile_basics", "social_media"]
    completed_steps = document.get("completed_steps", [])

    missing_steps = [step for step in required_steps if step not in completed_steps]
    if missing_steps:
        raise HTTPException(
            status_code=400, 
            detail=f"Onboarding incomplete. Missing steps: {', '.join(missing_steps)}"
        )

    # Get form data
    form_data = document.get("form_data", {})

    # Create user object
    account_basics = form_data.get("account_basics", {})
    profile_basics = form_data.get("profile_basics", {})
    social_media = form_data.get("social_media", {})

    # Get the previously hashed password from account_basics
    password_hash = account_basics.get("password", "")
    if not password_hash:
        raise HTTPException(status_code=400, detail="Password is required")

    # Generate a unique user ID
    user_id = str(uuid.uuid4())
    username = account_basics.get("username", "")

    # Create user document
    user = {
        "_id": user_id,
        "user_id": user_id,
        "username": username,
        "email": account_basics.get("email", ""),
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat(),
        "last_login": "",
        "role": "user",
        "is_active": True,
        "profile": {
            "full_name": profile_basics.get("full_name", ""),
            "bio": "",
            "company": profile_basics.get("company", ""),
            "job_title": "",
            "profile_picture": "",
            "preferences": {
                "default_brand_id": username,
                "default_workflow_id": "Legacy Generation Flow",
                "notification_settings": {
                    "email_notifications": False,
                    "content_approval_alerts": False
                }
            },
            "socials": social_media
        },
        "settings": {
            "theme": "",
            "language": "",
            "timezone": "",
            "content_generation": {
                "default_repurpose_count": 5,
                "default_template_count": 5,
                "auto_approval": False
            }
        },
        "verification": {
            "is_verified": False,
            "verification_token": "",
            "token_expiry": "",
            "last_password_reset": ""
        }
    }

    try:
        # Process Twitter data if provided
        social_media_data = form_data.get("social_media", {})
        twitter_url = social_media_data.get("twitter_url")

        if twitter_url:
            try:
                print("\n=== Debug: Twitter URL Processing ===")
                print(f"Twitter URL detected: {twitter_url}")
                print(f"APIFY_API_TOKEN present: {'Yes' if os.environ.get('APIFY_API_TOKEN') else 'No'}")
                print(f"OPENAI_API_KEY present: {'Yes' if os.environ.get('OPENAI_API_KEY') else 'No'}")
                
                if not os.environ.get("APIFY_API_TOKEN"):
                    raise Exception("APIFY_API_TOKEN missing")
                    
                print("Importing tweet processing functions...")
                from source_content_manager import gather_user_tweets, tweet_to_source_content

                # Store user ID in environment for the tweet processing
                os.environ["CURRENT_USER_ID"] = user_id
                print(f"Set CURRENT_USER_ID env var to: {user_id}")
                print(f"Processing Twitter URL: {twitter_url}")

                # Gather and process tweets
                print("Calling gather_user_tweets...")
                tweets = gather_user_tweets(
                    max_items=100,
                    sort="Latest",
                    user_url=twitter_url
                )
                print(f"Retrieved {len(tweets) if tweets else 0} tweets")

                print("Processing tweets with tweet_to_source_content...")
                processed_tweets = tweet_to_source_content(tweets)
                print(f"Successfully processed {len(processed_tweets)} tweets")

                # Clear the environment variable
                del os.environ["CURRENT_USER_ID"]
                print("Cleared CURRENT_USER_ID env var")

                # Add tweet processing result to user document
                user["profile"]["twitter_processed"] = True
                user["profile"]["processed_tweets_count"] = len(processed_tweets)
                print("=== End Tweet Processing ===\n")
            except Exception as e:
                print("\n=== Debug: Tweet Processing Error ===")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {str(e)}")
                print(f"Twitter URL attempted: {twitter_url}")
                print("=== End Error Debug ===\n")
                user["profile"]["twitter_processed"] = False
                user["profile"]["twitter_process_error"] = str(e)

        # Insert user document
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }

        payload = {
            "insertOne": {
                "document": user
            }
        }

        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Delete the onboarding session
        delete_url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/onboarding_progress"
        delete_payload = {
            "deleteOne": {
                "filter": {"_id": session_id}
            }
        }

        delete_response = requests.post(delete_url, headers=headers, json=delete_payload)
        delete_response.raise_for_status()

        # Create access token for auto-login
        from datetime import timedelta
        from main import create_access_token

        access_token = create_access_token(
            data={"sub": username, "user_id": user_id},
            expires_delta=timedelta(minutes=30)
        )

        return {
            "status": "success", 
            "message": "Onboarding completed successfully", 
            "user_id": user_id,
            "access_token": access_token
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete onboarding: {str(e)}")

@router.get("/progress", response_model=OnboardingProgressResponse)
async def get_onboarding_progress(session_data=Depends(get_onboarding_session)):
    """Get current onboarding progress"""
    payload, document = session_data

    # Return the progress information
    return {
        "user_id": document.get("user_id"),
        "email": document.get("email"),
        "step": document.get("step"),
        "completed_steps": document.get("completed_steps", []),
        "last_updated": document.get("last_updated"),
        "expires_at": document.get("expires_at"),
        "form_data": document.get("form_data", {})
    }

@router.post("/reset")
async def reset_onboarding(session_data=Depends(get_onboarding_session)):
    """Reset the onboarding process"""
    payload, document = session_data
    session_id = payload.get("sub")
    email = document.get("email", "")

    # Delete the existing session
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/onboarding_progress"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    delete_payload = {
        "deleteOne": {
            "filter": {"_id": session_id}
        }
    }

    try:
        # Delete the existing session
        delete_response = requests.post(url, headers=headers, json=delete_payload)
        delete_response.raise_for_status()

        # Create a new session
        # Generate a unique ID for the session
        new_session_id = str(uuid.uuid4())

        # Create expiration date (7 days from now)
        expires_delta = timedelta(days=SESSION_TOKEN_EXPIRE_DAYS)
        expires_at = datetime.utcnow() + expires_delta

        # Create a JWT session token
        token, expire_datetime = create_session_token(
            data={"sub": new_session_id, "email": email},
            expires_delta=expires_delta
        )

        # Prepare session document
        document = {
            "_id": new_session_id,
            "user_id": new_session_id,  # Initially, user_id is the same as session_id
            "email": email,
            "step": "account_basics",  # Initial step
            "completed_steps": [],
            "last_updated": datetime.utcnow().isoformat(),
            "expires_at": expires_at.isoformat(),
            "form_data": {},
            "session_id": new_session_id
        }

        insert_payload = {
            "insertOne": {
                "document": document
            }
        }

        response = requests.post(url, headers=headers, json=insert_payload)
        response.raise_for_status()

        return {
            "status": "success",
            "message": "Onboarding reset successfully",
            "session_token": token,
            "expires_at": expires_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset onboarding: {str(e)}")