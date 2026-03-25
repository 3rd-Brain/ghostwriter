# Applying the changes to correctly access the number of modified documents in AstraDB responses.
import os
import requests
from datetime import datetime
from typing import Dict, List
from astrapy import DataAPIClient

def migrate_users_to_credit_system(initial_balance: float = 5.0) -> Dict:
    """
    Add credit fields to all existing user documents in AstraDB

    Args:
        initial_balance: Initial credit balance to give each user

    Returns:
        Dictionary containing migration results
    """
    print(f"\n=== Starting Credit System Migration ===")
    print(f"Initial balance per user: {initial_balance}")

    # Get environment variables
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT:
        return {"status": "error", "message": "ASTRA_DB_API_ENDPOINT not configured"}
    if not ASTRA_DB_APPLICATION_TOKEN:
        return {"status": "error", "message": "ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER not configured"}

    try:
        # Initialize the DataAPI client with keyspace
        client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
        database = client.get_database(ASTRA_DB_API_ENDPOINT, keyspace="users_keyspace")
        users_collection = database.get_collection("users")

        # Get all users that don't already have credit fields
        users_without_credits = users_collection.find(
            {"credits": {"$exists": False}},
            projection={"user_id": 1, "username": 1, "email": 1}
        )

        users_list = list(users_without_credits)
        total_users = len(users_list)

        print(f"Found {total_users} users without credit fields")

        if total_users == 0:
            return {
                "status": "success",
                "message": "No users need migration - all users already have credit fields",
                "users_migrated": 0,
                "total_users": 0
            }

        # Prepare the credit fields to add under 'credits' umbrella
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        credit_fields = {
            "credits": {
                "current_balance": initial_balance,
                "total_purchased": initial_balance,  # Initial balance counts as purchased
                "total_consumed": 0.0,
                "reserved_credits": 0.0,
                "last_credit_update": current_time,
                "credit_history_enabled": True
            }
        }

        # Update all users without credit fields
        update_result = users_collection.update_many(
            {"credits": {"$exists": False}},
            {"$set": credit_fields}
        )

        print(f"Direct update_result response: {update_result}")
        print(f"Type of update_result: {type(update_result)}")
        print(f"Available attributes: {dir(update_result)}")

        print(f"Migration completed successfully")
        print(f"Users updated: {update_result.update_info['nModified']}")

        # Create the credit_transactions collection if it doesn't exist
        try:
            transactions_collection = database.get_collection("credit_transactions")
            print("Credit transactions collection already exists")
        except Exception:
            # Collection doesn't exist, create it
            transactions_collection = database.create_collection("credit_transactions")
            print("Created credit_transactions collection")

        return {
            "status": "success",
            "message": f"Successfully migrated {update_result.update_info['nModified']} users to credit system",
            "users_migrated": update_result.update_info['nModified'],
            "total_users": total_users,
            "initial_balance": initial_balance,
            "migration_time": current_time
        }

    except Exception as e:
        print(f"Migration error: {str(e)}")
        return {
            "status": "error", 
            "message": f"Migration failed: {str(e)}"
        }

def add_credit_fields_to_user(user_id: str, initial_balance: float) -> Dict:
    """
    Add credit fields to a specific user document

    Args:
        user_id: User ID to add credit fields to
        initial_balance: Initial credit balance for the user

    Returns:
        Dictionary containing the operation result
    """
    print(f"\n=== Adding Credit Fields to User: {user_id} ===")

    # Get environment variables
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return {"status": "error", "message": "Database credentials not configured"}

    try:
        # Initialize the DataAPI client with keyspace
        client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
        database = client.get_database(ASTRA_DB_API_ENDPOINT, keyspace="users_keyspace")
        users_collection = database.get_collection("users")

        # Check if user exists and doesn't have credit fields
        user = users_collection.find_one({"user_id": user_id})

        if not user:
            return {"status": "error", "message": f"User {user_id} not found"}

        if "credits" in user:
            return {
                "status": "warning", 
                "message": f"User {user_id} already has credit fields",
                "current_balance": user.get("credits", {}).get("current_balance")
            }

        # Prepare credit fields under 'credits' umbrella
        current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        credit_fields = {
            "credits": {
                "current_balance": initial_balance,
                "total_purchased": initial_balance,
                "total_consumed": 0.0,
                "reserved_credits": 0.0,
                "last_credit_update": current_time,
                "credit_history_enabled": True
            }
        }

        # Update the user document
        result = users_collection.update_one(
            {"user_id": user_id},
            {"$set": credit_fields}
        )

        if result.update_info['nModified'] > 0:
            print(f"Successfully added credit fields to user {user_id}")
            return {
                "status": "success",
                "message": f"Added credit fields to user {user_id}",
                "initial_balance": initial_balance,
                "update_time": current_time
            }
        else:
            return {"status": "error", "message": "Failed to update user document"}

    except Exception as e:
        print(f"Error adding credit fields to user: {str(e)}")
        return {"status": "error", "message": str(e)}

def verify_migration_success() -> Dict:
    """
    Verify that the migration was successful by checking user documents

    Returns:
        Dictionary containing verification results
    """
    print(f"\n=== Verifying Migration Success ===")

    # Get environment variables
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return {"status": "error", "message": "Database credentials not configured"}

    try:
        # Initialize the DataAPI client with keyspace
        client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
        database = client.get_database(ASTRA_DB_API_ENDPOINT, keyspace="users_keyspace")
        users_collection = database.get_collection("users")

        # Count total users
        total_users = users_collection.count_documents({})

        # Count users with credit fields
        users_with_credits = users_collection.count_documents({"credits": {"$exists": True}})

        # Count users without credit fields
        users_without_credits = users_collection.count_documents({"credits": {"$exists": False}})

        # Get sample user with credits
        sample_user = users_collection.find_one(
            {"credits": {"$exists": True}},
            projection={"user_id": 1, "credits.current_balance": 1, "credits.total_purchased": 1}
        )

        # Check if credit_transactions collection exists
        try:
            transactions_collection = database.get_collection("credit_transactions")
            transactions_exist = True
        except Exception:
            transactions_exist = False

        migration_complete = users_without_credits == 0

        print(f"Total users: {total_users}")
        print(f"Users with credit fields: {users_with_credits}")
        print(f"Users without credit fields: {users_without_credits}")
        print(f"Credit transactions collection exists: {transactions_exist}")
        print(f"Migration complete: {migration_complete}")

        return {
            "status": "success",
            "migration_complete": migration_complete,
            "total_users": total_users,
            "users_with_credits": users_with_credits,
            "users_without_credits": users_without_credits,
            "transactions_collection_exists": transactions_exist,
            "sample_user": sample_user,
            "verification_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }

    except Exception as e:
        print(f"Verification error: {str(e)}")
        return {"status": "error", "message": str(e)}

def rollback_migration() -> Dict:
    """
    Rollback the migration by removing credit fields from all users
    WARNING: This will permanently delete all credit data

    Returns:
        Dictionary containing rollback results
    """
    print(f"\n=== ROLLBACK WARNING ===")
    print(f"This will permanently delete all credit data from user documents")

    # Get environment variables
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return {"status": "error", "message": "Database credentials not configured"}

    try:
        # Initialize the DataAPI client with keyspace
        client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
        database = client.get_database(ASTRA_DB_API_ENDPOINT, keyspace="users_keyspace")
        users_collection = database.get_collection("users")

        # Remove credit fields from all users
        result = users_collection.update_many(
            {"credits": {"$exists": True}},
            {"$unset": {
                "credits": ""
            }}
        )

        print(f"Rollback completed: {result.update_info['nModified']} users updated")

        return {
            "status": "success",
            "message": f"Rollback completed - removed credit fields from {result.update_info['nModified']} users",
            "users_affected": result.update_info['nModified'],
            "rollback_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }

    except Exception as e:
        print(f"Rollback error: {str(e)}")
        return {"status": "error", "message": str(e)}

def get_migration_progress() -> Dict:
    """
    Get current migration progress and statistics

    Returns:
        Dictionary containing migration progress information
    """
    print(f"\n=== Checking Migration Progress ===")

    # Get environment variables
    ASTRA_DB_API_ENDPOINT = os.environ.get("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")

    if not ASTRA_DB_API_ENDPOINT or not ASTRA_DB_APPLICATION_TOKEN:
        return {"status": "error", "message": "Database credentials not configured"}

    try:
        # Initialize the DataAPI client with keyspace
        client = DataAPIClient(ASTRA_DB_APPLICATION_TOKEN)
        database = client.get_database(ASTRA_DB_API_ENDPOINT, keyspace="users_keyspace")
        users_collection = database.get_collection("users")

        # Get counts
        total_users = users_collection.count_documents({})
        users_with_credits = users_collection.count_documents({"credits": {"$exists": True}})
        users_without_credits = total_users - users_with_credits

        # Calculate progress percentage
        progress_percentage = (users_with_credits / total_users * 100) if total_users > 0 else 0

        # Get credit statistics for migrated users
        credit_stats = {}
        if users_with_credits > 0:
            # Use aggregation to get credit statistics
            pipeline = [
                {"$match": {"credits": {"$exists": True}}},
                {"$group": {
                    "_id": None,
                    "total_balance": {"$sum": "$credits.current_balance"},
                    "avg_balance": {"$avg": "$credits.current_balance"},
                    "total_purchased": {"$sum": "$credits.total_purchased"},
                    "total_consumed": {"$sum": "$credits.total_consumed"}
                }}
            ]

            stats_result = list(users_collection.aggregate(pipeline))
            if stats_result:
                credit_stats = stats_result[0]
                del credit_stats["_id"]  # Remove the _id field

        return {
            "status": "success",
            "total_users": total_users,
            "users_with_credits": users_with_credits,
            "users_without_credits": users_without_credits,
            "progress_percentage": round(progress_percentage, 2),
            "migration_complete": users_without_credits == 0,
            "credit_statistics": credit_stats,
            "check_time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }

    except Exception as e:
        print(f"Progress check error: {str(e)}")
        return {"status": "error", "message": str(e)}

def initialize_user_credits(user_id: str, initial_balance: float) -> Dict:
    """
    Initialize credit fields for a new user
    This is used when creating new user accounts

    Args:
        user_id: User ID to initialize credits for
        initial_balance: Initial credit balance

    Returns:
        Dictionary containing initialization result
    """
    return add_credit_fields_to_user(user_id, initial_balance)

# Main execution for testing
if __name__ == "__main__":
    print("Credit System Migration Script")
    print("1. Run migration with default 5 credits")
    print("2. Verify migration")
    print("3. Check progress")
    print("4. Rollback (WARNING: Destructive)")

    choice = input("Enter choice (1-4): ")

    if choice == "1":
        result = migrate_users_to_credit_system(5.0)
        print(f"Migration result: {result}")
    elif choice == "2":
        result = verify_migration_success()
        print(f"Verification result: {result}")
    elif choice == "3":
        result = get_migration_progress()
        print(f"Progress: {result}")
    elif choice == "4":
        confirm = input("Are you sure you want to rollback? Type 'CONFIRM' to proceed: ")
        if confirm == "CONFIRM":
            result = rollback_migration()
            print(f"Rollback result: {result}")
        else:
            print("Rollback cancelled")
    else:
        print("Invalid choice")