
"""
Credit Manager - Core credit system functionality

This file handles:
- Credit validation functions (validate_user_credits, get_user_credit_balance, reserve_credits)
- Credit deduction operations (deduct_credits, release_reserved_credits) 
- Cost estimation functions (estimate_generation_cost, calculate_actual_cost)
- Integration with credit_database_manager for all database operations
- Atomic credit operations to ensure data consistency

Key Functions to Implement:
- validate_user_credits(user_id: str, estimated_cost: float) -> bool
- get_user_credit_balance(user_id: str) -> float  
- reserve_credits(user_id: str, amount: float) -> bool
- deduct_credits(user_id: str, actual_cost: float, operation_details: dict) -> dict
- release_reserved_credits(user_id: str, amount: float) -> bool
- estimate_generation_cost(workflow_name: str, content_length: int) -> float
- calculate_actual_cost(tokens_used: int, model_used: str) -> float
"""

import json
import os
from typing import Dict, Optional, List
from decimal import Decimal, ROUND_HALF_UP
from credit_system.credit_database_manager import CreditDatabaseManager
from credit_system.credit_transaction_logger import CreditTransactionLogger


class CreditManager:
    def __init__(self):
        self.db_manager = CreditDatabaseManager()
        self.transaction_logger = CreditTransactionLogger()
        self.pricing_config = self._load_pricing_config()
    
    def _load_pricing_config(self) -> Dict:
        """Load pricing configuration from JSON file"""
        config_path = os.path.join(os.path.dirname(__file__), 'pricing_config.json')
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise Exception(f"Pricing config file not found at: {config_path}")
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON in pricing config file: {config_path}")
    
    def _round_cost(self, amount: float) -> float:
        """Round cost to 6 decimal places for consistency"""
        return float(Decimal(str(amount)).quantize(Decimal('0.000001'), rounding=ROUND_HALF_UP))
    
    def validate_user_credits(self, user_id: str, estimated_cost: float) -> bool:
        """
        Validate if user has sufficient credits for an operation
        
        Args:
            user_id: User ID to check
            estimated_cost: Estimated cost of the operation
            
        Returns:
            True if user has sufficient credits, False otherwise
        """
        try:
            current_balance = self.get_user_credit_balance(user_id)
            return current_balance >= estimated_cost
        except Exception:
            return False
    
    def get_user_credit_balance(self, user_id: str) -> float:
        """
        Get user's current credit balance
        
        Args:
            user_id: User ID
            
        Returns:
            Current credit balance
        """
        try:
            credit_info = self.db_manager.get_user_credit_info(user_id)
            if credit_info["status"] == "success":
                return float(credit_info["credits"]["current_balance"])
            else:
                raise Exception(f"Could not retrieve balance for user {user_id}")
        except Exception as e:
            raise Exception(f"Error getting user credit balance: {str(e)}")
    
    def reserve_credits(self, user_id: str, amount: float) -> bool:
        """
        Reserve credits for an operation (prevents concurrent operations from overdrawing)
        
        Args:
            user_id: User ID
            amount: Amount to reserve
            
        Returns:
            True if reservation successful, False otherwise
        """
        try:
            current_balance = self.get_user_credit_balance(user_id)
            
            # Check if user has sufficient credits
            if current_balance < amount:
                return False
            
            # Get current reserved credits
            credit_info = self.db_manager.get_user_credit_info(user_id)
            current_reserved = float(credit_info["credits"].get("reserved_credits", 0.0))
            
            # Update reserved credits
            new_reserved = current_reserved + amount
            
            # Update in AstraDB
            users_collection = self.db_manager.get_astra_collection()
            result = users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"credits.reserved_credits": new_reserved}}
            )
            
            return result.update_info['nModified'] > 0
            
        except Exception as e:
            print(f"Error reserving credits: {str(e)}")
            return False
    
    def release_reserved_credits(self, user_id: str, amount: float) -> bool:
        """
        Release reserved credits (when operation is cancelled or completed)
        
        Args:
            user_id: User ID
            amount: Amount to release
            
        Returns:
            True if release successful, False otherwise
        """
        try:
            # Get current reserved credits
            credit_info = self.db_manager.get_user_credit_info(user_id)
            current_reserved = float(credit_info["credits"].get("reserved_credits", 0.0))
            
            # Calculate new reserved amount (ensure it doesn't go negative)
            new_reserved = max(0.0, current_reserved - amount)
            
            # Update in AstraDB
            users_collection = self.db_manager.get_astra_collection()
            result = users_collection.update_one(
                {"user_id": user_id},
                {"$set": {"credits.reserved_credits": new_reserved}}
            )
            
            return result.update_info['nModified'] > 0
            
        except Exception as e:
            print(f"Error releasing reserved credits: {str(e)}")
            return False
    
    def deduct_credits(self, user_id: str, actual_cost: float, operation_details: Dict) -> Dict:
        """
        Deduct credits from user account and log the transaction
        
        Args:
            user_id: User ID
            actual_cost: Actual cost of the operation
            operation_details: Details about the operation
            
        Returns:
            Dictionary with deduction result and transaction details
        """
        try:
            # Round the cost
            actual_cost = self._round_cost(actual_cost)
            
            # Apply minimum charge
            minimum_charge = self.pricing_config.get("pricing_settings", {}).get("minimum_charge", 0.001)
            if actual_cost < minimum_charge:
                actual_cost = minimum_charge
            
            # Validate user has sufficient credits
            if not self.validate_user_credits(user_id, actual_cost):
                return {
                    "status": "error",
                    "message": "Insufficient credits",
                    "required": actual_cost,
                    "available": self.get_user_credit_balance(user_id)
                }
            
            # Log the transaction (this also updates the balance)
            transaction_id = self.transaction_logger.log_credit_deduction(
                user_id, actual_cost, operation_details
            )
            
            # Release any reserved credits for this operation
            reserved_amount = operation_details.get("reserved_amount", 0.0)
            if reserved_amount > 0:
                self.release_reserved_credits(user_id, reserved_amount)
            
            return {
                "status": "success",
                "message": f"Successfully deducted {actual_cost} credits",
                "transaction_id": transaction_id,
                "amount_deducted": actual_cost,
                "new_balance": self.get_user_credit_balance(user_id)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error deducting credits: {str(e)}"
            }
    
    def estimate_generation_cost(self, workflow_name: str, content_length: int, model_name: str = "gpt-4o-mini") -> float:
        """
        Estimate the cost of a generation operation
        
        Args:
            workflow_name: Name of the workflow
            content_length: Estimated content length in characters
            model_name: Model to use for generation
            
        Returns:
            Estimated cost in credits
        """
        try:
            # Get model pricing
            if model_name not in self.pricing_config["models"]:
                # Default to cheapest model if specified model not found
                model_name = "gpt-4o-mini"
            
            model_config = self.pricing_config["models"][model_name]
            
            # Rough estimation: 1 character ≈ 0.25 tokens
            estimated_input_tokens = content_length * 0.25
            # Assume output is roughly 50% of input for most workflows
            estimated_output_tokens = estimated_input_tokens * 0.5
            
            # Calculate base cost
            input_cost = (estimated_input_tokens / 1_000_000) * model_config["input_cost_per_1M_tokens"]
            output_cost = (estimated_output_tokens / 1_000_000) * model_config["output_cost_per_1M_tokens"]
            base_cost = input_cost + output_cost
            
            # Apply markup
            markup_percentage = self.pricing_config.get("pricing_settings", {}).get("markup_percentage", 0.10)
            final_cost = base_cost * (1 + markup_percentage)
            
            # Apply minimum charge
            minimum_charge = self.pricing_config.get("pricing_settings", {}).get("minimum_charge", 0.001)
            final_cost = max(final_cost, minimum_charge)
            
            return self._round_cost(final_cost)
            
        except Exception as e:
            # Return a default estimate if calculation fails
            print(f"Error estimating cost: {str(e)}")
            return 0.01  # Default 1 cent estimate
    
    def calculate_actual_cost(self, tokens_used: Dict[str, int], model_used: str) -> float:
        """
        Calculate actual cost based on tokens used
        
        Args:
            tokens_used: Dictionary with 'input' and 'output' token counts
            model_used: Model that was used
            
        Returns:
            Actual cost in credits
        """
        try:
            # Get model pricing
            if model_used not in self.pricing_config["models"]:
                raise Exception(f"Unknown model: {model_used}")
            
            model_config = self.pricing_config["models"][model_used]
            
            # Calculate base cost
            input_tokens = tokens_used.get("input", 0)
            output_tokens = tokens_used.get("output", 0)
            
            input_cost = (input_tokens / 1_000_000) * model_config["input_cost_per_1M_tokens"]
            output_cost = (output_tokens / 1_000_000) * model_config["output_cost_per_1M_tokens"]
            base_cost = input_cost + output_cost
            
            # Apply markup
            markup_percentage = self.pricing_config.get("pricing_settings", {}).get("markup_percentage", 0.10)
            final_cost = base_cost * (1 + markup_percentage)
            
            # Apply minimum charge
            minimum_charge = self.pricing_config.get("pricing_settings", {}).get("minimum_charge", 0.001)
            final_cost = max(final_cost, minimum_charge)
            
            return self._round_cost(final_cost)
            
        except Exception as e:
            raise Exception(f"Error calculating actual cost: {str(e)}")
    
    def get_user_credit_summary(self, user_id: str) -> Dict:
        """
        Get comprehensive credit summary for a user
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with credit summary
        """
        try:
            # Get current balance
            balance = self.get_user_credit_balance(user_id)
            
            # Get full credit info
            credit_info = self.db_manager.get_user_credit_info(user_id)
            credits = credit_info.get("credits", {})
            
            # Get transaction summary
            transaction_summary = self.transaction_logger.get_user_transaction_summary(user_id)
            
            return {
                "status": "success",
                "user_id": user_id,
                "current_balance": balance,
                "total_purchased": credits.get("total_purchased", 0.0),
                "total_consumed": credits.get("total_consumed", 0.0),
                "reserved_credits": credits.get("reserved_credits", 0.0),
                "last_credit_update": credits.get("last_credit_update"),
                "transaction_summary": transaction_summary
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error getting credit summary: {str(e)}"
            }


# Convenience functions for direct usage
credit_manager = CreditManager()

def validate_user_credits(user_id: str, estimated_cost: float) -> bool:
    return credit_manager.validate_user_credits(user_id, estimated_cost)

def get_user_credit_balance(user_id: str) -> float:
    return credit_manager.get_user_credit_balance(user_id)

def reserve_credits(user_id: str, amount: float) -> bool:
    return credit_manager.reserve_credits(user_id, amount)

def deduct_credits(user_id: str, actual_cost: float, operation_details: Dict) -> Dict:
    return credit_manager.deduct_credits(user_id, actual_cost, operation_details)

def release_reserved_credits(user_id: str, amount: float) -> bool:
    return credit_manager.release_reserved_credits(user_id, amount)

def estimate_generation_cost(workflow_name: str, content_length: int, model_name: str = "gpt-4o-mini") -> float:
    return credit_manager.estimate_generation_cost(workflow_name, content_length, model_name)

def calculate_actual_cost(tokens_used: Dict[str, int], model_used: str) -> float:
    return credit_manager.calculate_actual_cost(tokens_used, model_used)

def get_user_credit_summary(user_id: str) -> Dict:
    return credit_manager.get_user_credit_summary(user_id)
