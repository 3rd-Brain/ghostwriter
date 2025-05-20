
import os
import uuid
import secrets
import string
from cryptography.fernet import Fernet
from datetime import datetime
import requests
from typing import Dict, Optional, Tuple

# Initialize encryption (ideally, the key would be stored in a secure vault)
def get_encryption_key():
    """Get the encryption key from environment or create a new one"""
    key = os.environ.get("ENCRYPTION_KEY")
    if not key:
        # In production, this key should be stored securely and reused
        # First-time generation only
        key = Fernet.generate_key().decode()
        print(f"Warning: Generated new encryption key. Store this securely: {key}")
    return key.encode()

def initialize_cipher():
    """Initialize the cipher for encryption/decryption"""
    key = get_encryption_key()
    return Fernet(key)

# The cipher will be initialized when the module is loaded
cipher = initialize_cipher()

def encrypt_api_key(api_key: str) -> str:
    """
    Encrypt an API key using Fernet symmetric encryption.
    
    Args:
        api_key: The API key to encrypt
        
    Returns:
        Encrypted API key as a string
    """
    return cipher.encrypt(api_key.encode()).decode()

def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt an API key.
    
    Args:
        encrypted_key: The encrypted API key
        
    Returns:
        Original API key
    """
    try:
        return cipher.decrypt(encrypted_key.encode()).decode()
    except Exception as e:
        print(f"Error decrypting API key: {str(e)}")
        return ""

def store_third_party_key(user_id: str, service: str, api_key: str, description: str = "") -> Dict:
    """
    Store a third-party API key for a user.
    
    Args:
        user_id: ID of the user who owns the key
        service: Service name (e.g., "openai", "anthropic")
        api_key: The API key to store
        description: Optional description of what this key is used for
        
    Returns:
        Dictionary with API key information
    """
    try:
        # Get prefix (first few characters) for display
        key_prefix = api_key[:8] + "..." if len(api_key) > 8 else api_key
        
        # Encrypt the full API key
        encrypted_key = encrypt_api_key(api_key)
        
        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            raise ValueError("Astra DB credentials not configured")
        
        # Store in users collection instead of creating a new collection
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        # Find the user first
        find_payload = {
            "findOne": {
                "filter": {"user_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=find_payload)
        response.raise_for_status()
        
        user_doc = response.json().get("data", {}).get("document")
        
        if not user_doc:
            raise ValueError(f"User with ID {user_id} not found")
        
        # Create new third-party key entry
        key_entry = {
            "key_id": str(uuid.uuid4()),
            "service": service,
            "key_hash": encrypted_key,  # Actually encrypted, not hashed
            "key_prefix": key_prefix,
            "created_at": datetime.utcnow().isoformat(),
            "is_active": True,
            "description": description
        }
        
        # Initialize third_party_api_keys field if it doesn't exist
        if "third_party_api_keys" not in user_doc:
            user_doc["third_party_api_keys"] = []
        
        # Add new key to the array
        user_doc["third_party_api_keys"].append(key_entry)
        
        # Update the user document
        update_payload = {
            "updateOne": {
                "filter": {"user_id": user_id},
                "update": {"$set": {"third_party_api_keys": user_doc["third_party_api_keys"]}}
            }
        }
        
        update_response = requests.post(url, headers=headers, json=update_payload)
        update_response.raise_for_status()
        
        return {
            "service": service,
            "key_prefix": key_prefix,
            "description": description,
            "key_id": key_entry["key_id"],
            "created_at": key_entry["created_at"],
            "is_active": True
        }
    except Exception as e:
        print(f"Error storing third-party API key: {str(e)}")
        raise

def get_third_party_key(user_id: str, service: str) -> Optional[str]:
    """
    Retrieve a decrypted API key for use.
    
    Args:
        user_id: ID of the user who owns the key
        service: Service name (e.g., "openai", "anthropic")
        
    Returns:
        Decrypted API key if found, None otherwise
    """
    try:
        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            return None
        
        # Query users collection for the user
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "findOne": {
                "filter": {"user_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        user_doc = response.json().get("data", {}).get("document")
        
        if not user_doc or "third_party_api_keys" not in user_doc:
            return None
        
        # Find the key for the specified service
        for key_entry in user_doc["third_party_api_keys"]:
            if key_entry["service"] == service and key_entry["is_active"]:
                # Decrypt and return the API key
                return decrypt_api_key(key_entry["key_hash"])
        
        return None
    except Exception as e:
        print(f"Error retrieving third-party API key: {str(e)}")
        return None

def list_third_party_keys(user_id: str) -> list:
    """
    List all third-party API keys for a user.
    
    Args:
        user_id: The user's ID
        
    Returns:
        List of API key entries (without the actual keys)
    """
    try:
        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            return []
        
        # Query users collection for the user
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "findOne": {
                "filter": {"user_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        user_doc = response.json().get("data", {}).get("document")
        
        if not user_doc or "third_party_api_keys" not in user_doc:
            return []
        
        # Return key information without the encrypted keys
        return [
            {
                "key_id": key.get("key_id"),
                "service": key.get("service"),
                "key_prefix": key.get("key_prefix"),
                "created_at": key.get("created_at"),
                "is_active": key.get("is_active"),
                "description": key.get("description")
            }
            for key in user_doc["third_party_api_keys"]
        ]
    except Exception as e:
        print(f"Error listing third-party API keys: {str(e)}")
        return []

def update_third_party_key(user_id: str, key_id: str, new_api_key: str) -> bool:
    """
    Update an existing third-party API key.
    
    Args:
        user_id: ID of the user who owns the key
        key_id: ID of the key to update
        new_api_key: New API key value
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            return False
        
        # Query users collection for the user
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "findOne": {
                "filter": {"user_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        user_doc = response.json().get("data", {}).get("document")
        
        if not user_doc or "third_party_api_keys" not in user_doc:
            return False
        
        # Find and update the key
        updated = False
        for i, key_entry in enumerate(user_doc["third_party_api_keys"]):
            if key_entry["key_id"] == key_id:
                # Update with new encrypted key
                key_prefix = new_api_key[:8] + "..." if len(new_api_key) > 8 else new_api_key
                user_doc["third_party_api_keys"][i]["key_hash"] = encrypt_api_key(new_api_key)
                user_doc["third_party_api_keys"][i]["key_prefix"] = key_prefix
                updated = True
                break
        
        if not updated:
            return False

def user_has_api_keys(user_id: str, service: Optional[str] = None) -> bool:
    """
    Check if a user has API keys configured.
    
    Args:
        user_id: ID of the user to check
        service: Optional specific service to check (e.g., "openai", "anthropic")
                If None, checks if the user has any API keys configured
        
    Returns:
        True if the user has the specified API keys, False otherwise
    """
    try:
        keys = list_third_party_keys(user_id)
        
        if not keys:
            return False
            
        if service:
            # Check for specific service
            return any(key.get("service") == service and key.get("is_active") for key in keys)
        else:
            # Check for any active key
            return any(key.get("is_active") for key in keys)
            
    except Exception as e:
        print(f"Error checking if user has API keys: {str(e)}")
        return False

        
        # Update the user document
        update_payload = {
            "updateOne": {
                "filter": {"user_id": user_id},
                "update": {"$set": {"third_party_api_keys": user_doc["third_party_api_keys"]}}
            }
        }
        
        update_response = requests.post(url, headers=headers, json=update_payload)
        update_response.raise_for_status()
        
        return True
    except Exception as e:
        print(f"Error updating third-party API key: {str(e)}")
        return False

def deactivate_third_party_key(user_id: str, key_id: str) -> bool:
    """
    Deactivate a third-party API key.
    
    Args:
        user_id: ID of the user who owns the key
        key_id: ID of the key to deactivate
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            return False
        
        # Query users collection for the user
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "findOne": {
                "filter": {"user_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        user_doc = response.json().get("data", {}).get("document")
        
        if not user_doc or "third_party_api_keys" not in user_doc:
            return False
        
        # Find and deactivate the key
        deactivated = False
        for i, key_entry in enumerate(user_doc["third_party_api_keys"]):
            if key_entry["key_id"] == key_id:
                user_doc["third_party_api_keys"][i]["is_active"] = False
                deactivated = True
                break
        
        if not deactivated:
            return False
        
        # Update the user document
        update_payload = {
            "updateOne": {
                "filter": {"user_id": user_id},
                "update": {"$set": {"third_party_api_keys": user_doc["third_party_api_keys"]}}
            }
        }
        
        update_response = requests.post(url, headers=headers, json=update_payload)
        update_response.raise_for_status()
        
        return True
    except Exception as e:
        print(f"Error deactivating third-party API key: {str(e)}")
        return False

def delete_third_party_key(user_id: str, key_id: str) -> bool:
    """
    Delete a third-party API key.
    
    Args:
        user_id: ID of the user who owns the key
        key_id: ID of the key to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get Astra DB credentials
        ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
        ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
            return False
        
        # Query users collection for the user
        url = f"{ASTRA_DB_API_ENDPOINT}/api/json/v1/users_keyspace/users"
        headers = {
            "Token": ASTRA_DB_APPLICATION_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "findOne": {
                "filter": {"user_id": user_id}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        user_doc = response.json().get("data", {}).get("document")
        
        if not user_doc or "third_party_api_keys" not in user_doc:
            return False
        
        # Filter out the key to delete
        original_length = len(user_doc["third_party_api_keys"])
        user_doc["third_party_api_keys"] = [
            key for key in user_doc["third_party_api_keys"] if key["key_id"] != key_id
        ]
        
        if len(user_doc["third_party_api_keys"]) == original_length:
            return False  # No key was removed
        
        # Update the user document
        update_payload = {
            "updateOne": {
                "filter": {"user_id": user_id},
                "update": {"$set": {"third_party_api_keys": user_doc["third_party_api_keys"]}}
            }
        }
        
        update_response = requests.post(url, headers=headers, json=update_payload)
        update_response.raise_for_status()
        
        return True
    except Exception as e:
        print(f"Error deleting third-party API key: {str(e)}")
        return False
