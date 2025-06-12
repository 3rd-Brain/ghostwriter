
"""
Credit Database Manager - Database operations for credit system

This file handles:
- All database operations related to credit management
- User document credit field updates (current_balance, total_purchased, etc.) in AstraDB
- Credit transaction database operations in PostgreSQL
- Database connection and error handling specific to credit operations

Key Functions:
- update_user_credit_balance(user_id: str, new_balance: float) -> dict
- get_user_credit_info(user_id: str) -> dict
- create_credit_transaction_record(transaction_data: dict) -> str
- initialize_user_credits(user_id: str, initial_balance: float) -> dict
"""

import os
import json
from datetime import datetime
from typing import Dict, Optional, List
import uuid
from astrapy import DataAPIClient
from credit_system.postgres_setup import PostgresConnection

class CreditDatabaseManager:
    def __init__(self):
        # AstraDB setup for user credit balance management
        self.astra_endpoint = os.environ.get("ASTRA_DB_API_ENDPOINT")
        self.astra_token = os.environ.get("ASTRA_DB_APPLICATION_TOKEN_GHOSTWRITER")
        
        # PostgreSQL setup for transaction logging
        self.postgres = PostgresConnection()
        
        if not self.astra_endpoint or not self.astra_token:
            raise ValueError("AstraDB credentials not configured")
    
    def get_astra_collection(self):
        """Get AstraDB users collection"""
        client = DataAPIClient(self.astra_token)
        database = client.get_database(self.astra_endpoint, keyspace="users_keyspace")
        return database.get_collection("users")
    
    def update_user_credit_balance(self, user_id: str, new_balance: float) -> Dict:
        """Update user's credit balance in AstraDB"""
        try:
            users_collection = self.get_astra_collection()
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            result = users_collection.update_one(
                {"user_id": user_id},
                {"$set": {
                    "credits.current_balance": new_balance,
                    "credits.last_credit_update": current_time
                }}
            )
            
            if result.update_info['nModified'] > 0:
                return {
                    "status": "success",
                    "message": f"Updated balance for user {user_id}",
                    "new_balance": new_balance
                }
            else:
                return {"status": "error", "message": "User not found or no changes made"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def update_user_credit_balance_and_purchased(self, user_id: str, new_balance: float, purchase_amount: float) -> Dict:
        """Update user's credit balance and increment total_purchased in AstraDB"""
        try:
            users_collection = self.get_astra_collection()
            current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            result = users_collection.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "credits.current_balance": new_balance,
                        "credits.last_credit_update": current_time
                    },
                    "$inc": {
                        "credits.total_purchased": purchase_amount
                    }
                }
            )
            
            if result.update_info['nModified'] > 0:
                return {
                    "status": "success",
                    "message": f"Updated balance and total_purchased for user {user_id}",
                    "new_balance": new_balance,
                    "purchase_amount_added": purchase_amount
                }
            else:
                return {"status": "error", "message": "User not found or no changes made"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def get_user_credit_info(self, user_id: str) -> Dict:
        """Get user's credit information from AstraDB"""
        try:
            users_collection = self.get_astra_collection()
            
            user = users_collection.find_one(
                {"user_id": user_id},
                projection={"credits": 1}
            )
            
            if user and "credits" in user:
                return {
                    "status": "success",
                    "credits": user["credits"]
                }
            else:
                return {"status": "error", "message": "User credits not found"}
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def create_credit_transaction_record(self, transaction_data: Dict) -> str:
        """Create a credit transaction record in PostgreSQL"""
        try:
            # Generate transaction ID if not provided
            transaction_id = transaction_data.get('transaction_id', str(uuid.uuid4()))
            
            print(f"🔍 DEBUG: Attempting to create PostgreSQL transaction with ID: {transaction_id}")
            
            insert_query = """
            INSERT INTO credit_transactions 
            (transaction_id, user_id, type, amount, balance_before, balance_after, reference_id, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING transaction_id;
            """
            
            params = (
                transaction_id,
                transaction_data['user_id'],
                transaction_data['type'],
                transaction_data['amount'],
                transaction_data['balance_before'],
                transaction_data['balance_after'],
                transaction_data.get('reference_id'),
                json.dumps(transaction_data.get('metadata')) if transaction_data.get('metadata') else None,
                transaction_data.get('created_at', datetime.utcnow())
            )
            
            print(f"🔍 DEBUG: Query params: {params}")
            print(f"🔍 DEBUG: Executing PostgreSQL query...")
            
            result = self.postgres.execute_query(insert_query, params, fetch=True)
            
            print(f"🔍 DEBUG: PostgreSQL query result: {result}")
            
            if result:
                final_transaction_id = str(result[0]['transaction_id'])
                print(f"✅ DEBUG: PostgreSQL transaction created successfully: {final_transaction_id}")
                return final_transaction_id
            else:
                raise Exception("Failed to create transaction record - no result returned")
                
        except Exception as e:
            print(f"❌ DEBUG: PostgreSQL transaction creation failed: {str(e)}")
            import traceback
            print(f"❌ DEBUG: Full PostgreSQL traceback: {traceback.format_exc()}")
            raise Exception(f"Error creating transaction record: {str(e)}")
    
    def get_user_transaction_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get user's transaction history from PostgreSQL"""
        try:
            query = """
            SELECT transaction_id, user_id, type, amount, balance_before, balance_after, 
                   reference_id, metadata, created_at
            FROM credit_transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s;
            """
            
            results = self.postgres.execute_query(query, (user_id, limit), fetch=True)
            
            # Convert to list of dicts and handle datetime serialization
            transactions = []
            for row in results:
                transaction = dict(row)
                transaction['transaction_id'] = str(transaction['transaction_id'])
                transaction['created_at'] = transaction['created_at'].isoformat()
                transactions.append(transaction)
            
            return transactions
            
        except Exception as e:
            raise Exception(f"Error retrieving transaction history: {str(e)}")
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict]:
        """Get a specific transaction by ID from PostgreSQL"""
        try:
            query = """
            SELECT transaction_id, user_id, type, amount, balance_before, balance_after,
                   reference_id, metadata, created_at
            FROM credit_transactions
            WHERE transaction_id = %s;
            """
            
            results = self.postgres.execute_query(query, (transaction_id,), fetch=True)
            
            if results:
                transaction = dict(results[0])
                transaction['transaction_id'] = str(transaction['transaction_id'])
                transaction['created_at'] = transaction['created_at'].isoformat()
                return transaction
            else:
                return None
                
        except Exception as e:
            raise Exception(f"Error retrieving transaction: {str(e)}")
    
    def initialize_user_credits(self, user_id: str, initial_balance: float) -> Dict:
        """Initialize credit fields for a new user"""
        # Import here to avoid circular imports
        from migration_script import initialize_user_credits
        return initialize_user_credits(user_id, initial_balance)
