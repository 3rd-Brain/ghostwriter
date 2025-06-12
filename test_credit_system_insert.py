
import os
from credit_system.credit_transaction_logger import log_credit_purchase

def test_credit_purchase():
    """Test the credit system purchase logging"""
    print("🧪 Testing Credit System Purchase Logging")
    print("-" * 50)
    
    try:
        # Test credit purchase
        user_id = "test_user_credit_system"
        amount = 10.0
        purchase_details = {
            "payment_method": "credit_system_test",
            "payment_amount": 10.0,
            "currency": "USD",
            "purchase_package": "test_package"
        }
        
        print(f"🔍 Testing credit purchase for user: {user_id}")
        print(f"   Amount: ${amount}")
        
        # This should now work with the fixed PostgreSQL connection
        transaction_id = log_credit_purchase(user_id, amount, purchase_details)
        
        print(f"✅ SUCCESS: Credit purchase logged!")
        print(f"   Transaction ID: {transaction_id}")
        
        # Verify by checking the database
        from credit_system.credit_transaction_logger import get_user_transaction_history
        history = get_user_transaction_history(user_id, 5)
        
        print(f"✅ Transaction history retrieved: {len(history)} transactions")
        if history:
            latest = history[0]
            print(f"   Latest transaction: {latest['type']} ${latest['amount']}")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_credit_purchase()
