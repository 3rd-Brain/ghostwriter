import os
import uuid
import secrets
import string
import bcrypt
import requests
from datetime import datetime
from typing import Dict, Optional, Tuple

def generate_api_key(length: int = 32) -> Tuple[str, str]:
    """
    Generate a secure API key and its prefix.

    Args:
        length: Length of the API key

    Returns:
        Tuple containing the API key and its prefix
    """
    # Generate a random string for the API key
    alphabet = string.ascii_letters + string.digits
    api_key = ''.join(secrets.choice(alphabet) for _ in range(length))

    # Create a prefix (first 8 characters)
    prefix = "GW_" + api_key[:8]

    # Full key format
    full_key = f"{prefix}_{api_key}"

    return full_key, prefix

def hash_api_key(api_key: str) -> str:
    """
    Hash an API key using bcrypt.

    Args:
        api_key: The API key to hash

    Returns:
        Hashed API key
    """
    # Convert string to bytes
    api_key_bytes = api_key.encode('utf-8')

    # Generate a salt and hash the API key
    salt = bcrypt.gensalt()
    hashed_key = bcrypt.hashpw(api_key_bytes, salt)

    # Return the hash as string
    return hashed_key.decode('utf-8')

def create_api_key(user_id: str, name: str, scope: str = "user") -> dict:
    """
    Create a new API key for a user.

    Args:
        user_id: ID of the user who owns the key
        name: Descriptive name for the key
        scope: Permission scope (user or admin)

    Returns:
        Dictionary with API key information
    """
    try:
        # Generate a random API key with prefix
        prefix = f"GW_{secrets.token_hex(4)}"
        api_key = f"{prefix}_{secrets.token_hex(16)}"

        # Hash the API key for storage
        hashed_key = bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            raise ValueError("Astra DB credentials not configured")

        # Store the hash in database
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }

        # Create a new document ID
        document_id = str(uuid.uuid4())

        # Current timestamp for created_at
        created_at = datetime.utcnow().isoformat()

        # Prepare the document
        document = {
            "_id": document_id,
            "user_id": user_id,
            "key_hash": hashed_key,
            "prefix": prefix,
            "name": name,
            "created_at": created_at,
            "last_used": None,
            "is_active": True,
            "scope": scope
        }

        # Create the insert payload
        payload = {
            "insertOne": {
                "document": document
            }
        }

        # Make the request
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        # Return the key (will only be shown once)
        return {
            "api_key": api_key,
            "hashed_key": hashed_key,     # Debug only, remove in production
            "prefix": prefix,
            "scope": scope,                # Permission level
            "is_active": True,             # Active by default
            "name": name,                  # Descriptive name
            "id": document_id,             # Database document ID
            "created_at": created_at       # Creation timestamp
        }
    except Exception as e:
        print(f"Error creating API key: {str(e)}")
        raise

def verify_api_key(api_key: str) -> Optional[Dict]:
    """
    Verify an API key against the database.

    Args:
        api_key: The API key to verify

    Returns:
        User details dictionary if valid, None otherwise
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        raise ValueError("Database credentials not configured")

    # Extract prefix from the API key
    try:
        prefix = api_key.split("_")[0] + "_" + api_key.split("_")[1]
    except IndexError:
        return None  # Invalid format

    # Find API key record by prefix
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "findOne": {
            "filter": {"prefix": prefix}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        document = response.json().get("data", {}).get("document")

        if not document or not document.get("is_active", False):
            return None  # Not found or inactive

        # Verify the key hash
        stored_hash = document.get("key_hash", "") # corrected key name
        if not bcrypt.checkpw(api_key.encode('utf-8'), stored_hash.encode('utf-8')):
            return None  # Hash doesn't match

        # Update last used timestamp
        update_last_used(document.get("_id", ""))

        # Return user details (excluding sensitive data)
        return {
            "user_id": document.get("user_id"),
            "scope": document.get("scope"),
            "name": document.get("name"),
            "id": document.get("_id")  # Keep _id in database but return as id
        }
    except Exception as e:
        print(f"Error verifying API key: {str(e)}")
        return None

def update_last_used(key_id: str) -> None:
    """
    Update the last_used timestamp for an API key.

    Args:
        key_id: Database ID of the API key
    """
    if not key_id:
        return

    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return

    # Current timestamp
    current_time = datetime.utcnow().isoformat()

    # Update document in database
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "updateOne": {
            "filter": {"_id": key_id},
            "update": {"$set": {"last_used": current_time}}
        }
    }

    try:
        requests.post(url, headers=headers, json=payload)
    except Exception as e:
        print(f"Error updating last_used timestamp: {str(e)}")

def get_user_api_keys(user_id: str) -> list:
    """
    Get all API keys for a user.

    Args:
        user_id: The user's ID

    Returns:
        List of API keys (without the actual key values)
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        raise ValueError("Database credentials not configured")

    # Find all API keys for the user
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "find": {
            "filter": {"user_id": user_id}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()

        documents = response.json().get("data", {}).get("documents", [])

        # Return key details (excluding the actual key)
        return [
            {
                "id": doc.get("_id"),  # Renamed from _id to id for consistency with schema
                "name": doc.get("name"),
                "prefix": doc.get("prefix"),
                "scope": doc.get("scope"),
                "created_at": doc.get("created_at"),
                "last_used": doc.get("last_used"),
                "is_active": doc.get("is_active")
            }
            for doc in documents
        ]
    except Exception as e:
        print(f"Error getting user API keys: {str(e)}")
        return []

def deactivate_api_key(key_id: str) -> bool:
    """
    Deactivate an API key.

    Args:
        key_id: Database ID of the API key

    Returns:
        True if successful, False otherwise
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return False

    # Update document in database
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "updateOne": {
            "filter": {"_id": key_id},
            "update": {"$set": {"is_active": False}}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error deactivating API key: {str(e)}")
        return False

def delete_api_key(key_id: str) -> bool:
    """
    Delete an API key.

    Args:
        key_id: Database ID of the API key

    Returns:
        True if successful, False otherwise
    """
    # Get Astra DB credentials
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return False

    # Delete document from database
    url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/user_api_keys"
    headers = {
        "Token": ASTRA_DB_APPLICATION_TOKEN,
        "Content-Type": "application/json"
    }

    payload = {
        "deleteOne": {
            "filter": {"_id": key_id}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"Error deleting API key: {str(e)}")
        return False