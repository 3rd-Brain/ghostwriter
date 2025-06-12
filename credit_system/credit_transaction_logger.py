
"""
Credit Transaction Logger - Audit trail and transaction logging

This file handles:
- Detailed logging of all credit transactions
- Transaction audit trails for billing/support purposes  
- Transaction categorization (generation, purchase, refund, etc.)
- Transaction history retrieval and reporting
- Integration with credit_database_manager for persistence

Key Functions:
- log_credit_deduction(user_id: str, amount: float, operation_details: dict) -> str
- log_credit_purchase(user_id: str, amount: float, purchase_details: dict) -> str
- log_credit_reservation(user_id: str, amount: float, operation_id: str) -> str
- log_credit_release(user_id: str, amount: float, operation_id: str) -> str
- get_user_transaction_history(user_id: str, limit: int = 50) -> list
- get_transaction_by_id(transaction_id: str) -> dict
"""

from typing import Dict, List, Optional
import uuid
from datetime import datetime
from credit_system.credit_database_manager import CreditDatabaseManager

class CreditTransactionLogger:
    def __init__(self):
        self.db_manager = CreditDatabaseManager()
    
    def _get_user_balance(self, user_id: str) -> float:
        """Helper method to get current user balance"""
        credit_info = self.db_manager.get_user_credit_info(user_id)
        if credit_info["status"] == "success":
            return float(credit_info["credits"]["current_balance"])
        else:
            raise Exception(f"Could not retrieve balance for user {user_id}")
    
    def log_credit_deduction(self, user_id: str, amount: float, operation_details: Dict) -> str:
        """
        Log a credit deduction transaction (consumption)
        
        Args:
            user_id: User ID
            amount: Amount deducted (positive value)
            operation_details: Details about the operation that consumed credits
            
        Returns:
            Transaction ID
        """
        try:
            balance_before = self._get_user_balance(user_id)
            balance_after = balance_before - amount
            
            transaction_data = {
                "user_id": user_id,
                "type": "consumption",
                "amount": -amount,  # Negative for deduction
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_id": operation_details.get("operation_id"),
                "metadata": {
                    "operation_type": operation_details.get("operation_type"),
                    "workflow_name": operation_details.get("workflow_name"),
                    "tokens_used": operation_details.get("tokens_used"),
                    "model_used": operation_details.get("model_used"),
                    "actual_cost": operation_details.get("actual_cost"),
                    "estimated_cost": operation_details.get("estimated_cost")
                }
            }
            
            transaction_id = self.db_manager.create_credit_transaction_record(transaction_data)
            
            # Update user balance in AstraDB
            self.db_manager.update_user_credit_balance(user_id, balance_after)
            
            return transaction_id
            
        except Exception as e:
            raise Exception(f"Error logging credit deduction: {str(e)}")
    
    def log_credit_purchase(self, user_id: str, amount: float, purchase_details: Dict) -> str:
        """
        Log a credit purchase transaction
        
        Args:
            user_id: User ID
            amount: Amount purchased (positive value)
            purchase_details: Details about the purchase
            
        Returns:
            Transaction ID
        """
        try:
            balance_before = self._get_user_balance(user_id)
            balance_after = balance_before + amount
            
            transaction_data = {
                "user_id": user_id,
                "type": "purchase",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_id": purchase_details.get("payment_id"),
                "metadata": {
                    "payment_method": purchase_details.get("payment_method"),
                    "payment_amount": purchase_details.get("payment_amount"),
                    "currency": purchase_details.get("currency"),
                    "purchase_package": purchase_details.get("purchase_package")
                }
            }
            
            print(f"🔍 DEBUG: Creating transaction record with data: {transaction_data}")
            
            # Create PostgreSQL transaction record first
            transaction_id = self.db_manager.create_credit_transaction_record(transaction_data)
            print(f"✅ DEBUG: PostgreSQL transaction created with ID: {transaction_id}")
            
            # Update user balance in AstraDB
            update_result = self.db_manager.update_user_credit_balance(user_id, balance_after)
            print(f"✅ DEBUG: AstraDB balance update result: {update_result}")
            
            return transaction_id
            
        except Exception as e:
            print(f"❌ DEBUG: Error in log_credit_purchase: {str(e)}")
            import traceback
            print(f"❌ DEBUG: Full traceback: {traceback.format_exc()}")
            raise Exception(f"Error logging credit purchase: {str(e)}")
    
    def log_credit_bonus(self, user_id: str, amount: float, bonus_details: Dict) -> str:
        """
        Log a credit bonus transaction
        
        Args:
            user_id: User ID
            amount: Bonus amount (positive value)
            bonus_details: Details about the bonus
            
        Returns:
            Transaction ID
        """
        try:
            balance_before = self._get_user_balance(user_id)
            balance_after = balance_before + amount
            
            transaction_data = {
                "user_id": user_id,
                "type": "bonus",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_id": bonus_details.get("bonus_id"),
                "metadata": {
                    "bonus_type": bonus_details.get("bonus_type"),
                    "reason": bonus_details.get("reason"),
                    "admin_user": bonus_details.get("admin_user")
                }
            }
            
            transaction_id = self.db_manager.create_credit_transaction_record(transaction_data)
            
            # Update user balance in AstraDB
            self.db_manager.update_user_credit_balance(user_id, balance_after)
            
            return transaction_id
            
        except Exception as e:
            raise Exception(f"Error logging credit bonus: {str(e)}")
    
    def log_credit_refund(self, user_id: str, amount: float, refund_details: Dict) -> str:
        """
        Log a credit refund transaction
        
        Args:
            user_id: User ID
            amount: Refund amount (positive value)
            refund_details: Details about the refund
            
        Returns:
            Transaction ID
        """
        try:
            balance_before = self._get_user_balance(user_id)
            balance_after = balance_before + amount
            
            transaction_data = {
                "user_id": user_id,
                "type": "refund",
                "amount": amount,
                "balance_before": balance_before,
                "balance_after": balance_after,
                "reference_id": refund_details.get("refund_id"),
                "metadata": {
                    "original_transaction_id": refund_details.get("original_transaction_id"),
                    "refund_reason": refund_details.get("refund_reason"),
                    "admin_user": refund_details.get("admin_user")
                }
            }
            
            transaction_id = self.db_manager.create_credit_transaction_record(transaction_data)
            
            # Update user balance in AstraDB
            self.db_manager.update_user_credit_balance(user_id, balance_after)
            
            return transaction_id
            
        except Exception as e:
            raise Exception(f"Error logging credit refund: {str(e)}")
    
    def get_user_transaction_history(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get user's transaction history"""
        return self.db_manager.get_user_transaction_history(user_id, limit)
    
    def get_transaction_by_id(self, transaction_id: str) -> Optional[Dict]:
        """Get a specific transaction by ID"""
        return self.db_manager.get_transaction_by_id(transaction_id)
    
    def get_user_transaction_summary(self, user_id: str) -> Dict:
        """Get a summary of user's transactions"""
        try:
            transactions = self.get_user_transaction_history(user_id, limit=1000)
            
            summary = {
                "total_transactions": len(transactions),
                "total_purchased": 0.0,
                "total_consumed": 0.0,
                "total_refunded": 0.0,
                "total_bonus": 0.0,
                "last_transaction": None
            }
            
            for transaction in transactions:
                amount = float(transaction['amount'])
                transaction_type = transaction['type']
                
                if transaction_type == 'purchase':
                    summary['total_purchased'] += amount
                elif transaction_type == 'consumption':
                    summary['total_consumed'] += abs(amount)
                elif transaction_type == 'refund':
                    summary['total_refunded'] += amount
                elif transaction_type == 'bonus':
                    summary['total_bonus'] += amount
            
            if transactions:
                summary['last_transaction'] = transactions[0]
            
            return summary
            
        except Exception as e:
            raise Exception(f"Error generating transaction summary: {str(e)}")

# Convenience functions for direct usage
transaction_logger = CreditTransactionLogger()

def log_credit_deduction(user_id: str, amount: float, operation_details: Dict) -> str:
    return transaction_logger.log_credit_deduction(user_id, amount, operation_details)

def log_credit_purchase(user_id: str, amount: float, purchase_details: Dict) -> str:
    return transaction_logger.log_credit_purchase(user_id, amount, purchase_details)

def log_credit_bonus(user_id: str, amount: float, bonus_details: Dict) -> str:
    return transaction_logger.log_credit_bonus(user_id, amount, bonus_details)

def log_credit_refund(user_id: str, amount: float, refund_details: Dict) -> str:
    return transaction_logger.log_credit_refund(user_id, amount, refund_details)

def get_user_transaction_history(user_id: str, limit: int = 50) -> List[Dict]:
    return transaction_logger.get_user_transaction_history(user_id, limit)

def get_transaction_by_id(transaction_id: str) -> Optional[Dict]:
    return transaction_logger.get_transaction_by_id(transaction_id)
