
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import uuid
import json
from datetime import datetime

def insert_sample_transaction():
    """Insert a sample transaction directly into PostgreSQL"""
    print("🧪 Testing Direct PostgreSQL Transaction Insert")
    print("-" * 50)
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return
    
    try:
        # Connect directly to PostgreSQL
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✅ Connected to PostgreSQL")
        
        # Sample transaction data
        transaction_id = str(uuid.uuid4())
        user_id = "test_user_direct_insert"
        transaction_type = "purchase"
        amount = 5.0
        balance_before = 10.0
        balance_after = 15.0
        reference_id = "direct_test_" + str(uuid.uuid4())[:8]
        metadata = {
            "payment_method": "direct_test",
            "payment_amount": 5.0,
            "currency": "USD",
            "test_insert": True
        }
        created_at = datetime.utcnow()
        
        print(f"🔍 Inserting transaction:")
        print(f"   ID: {transaction_id}")
        print(f"   User: {user_id}")
        print(f"   Type: {transaction_type}")
        print(f"   Amount: ${amount}")
        
        # Insert query
        insert_query = """
        INSERT INTO credit_transactions 
        (transaction_id, user_id, type, amount, balance_before, balance_after, reference_id, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING transaction_id, created_at;
        """
        
        params = (
            transaction_id,
            user_id,
            transaction_type,
            amount,
            balance_before,
            balance_after,
            reference_id,
            json.dumps(metadata),
            created_at
        )
        
        # Execute insert
        cur.execute(insert_query, params)
        result = cur.fetchone()
        
        # IMPORTANT: Commit the transaction
        conn.commit()
        
        print(f"✅ Transaction inserted successfully!")
        print(f"   Returned ID: {result['transaction_id']}")
        print(f"   Created at: {result['created_at']}")
        
        # Verify the insert by querying back
        print(f"\n🔍 Verifying insert by querying back...")
        cur.execute("SELECT COUNT(*) as count FROM credit_transactions WHERE user_id = %s", (user_id,))
        count_result = cur.fetchone()
        print(f"✅ Found {count_result['count']} transactions for user {user_id}")
        
        # Get the inserted record
        cur.execute("""
            SELECT transaction_id, user_id, type, amount, metadata, created_at 
            FROM credit_transactions 
            WHERE transaction_id = %s
        """, (transaction_id,))
        
        inserted_record = cur.fetchone()
        if inserted_record:
            print(f"✅ Retrieved inserted record:")
            print(f"   ID: {inserted_record['transaction_id']}")
            print(f"   User: {inserted_record['user_id']}")
            print(f"   Type: {inserted_record['type']}")
            print(f"   Amount: ${inserted_record['amount']}")
            print(f"   Metadata: {inserted_record['metadata']}")
        
        cur.close()
        conn.close()
        
        print(f"\n🎉 SUCCESS: Direct PostgreSQL insert worked!")
        
    except Exception as e:
        print(f"❌ Error inserting transaction: {str(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    insert_sample_transaction()
