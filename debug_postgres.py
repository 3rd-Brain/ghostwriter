
import os
import psycopg2
from psycopg2.extras import RealDictCursor

def test_postgres_connection():
    """Test PostgreSQL connection and table existence"""
    print("🔍 Testing PostgreSQL Connection...")
    print("-" * 50)
    
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL environment variable not set")
        return
    
    print(f"✅ DATABASE_URL found: {database_url[:50]}...")
    
    try:
        # Test basic connection
        conn = psycopg2.connect(database_url)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("✅ Successfully connected to PostgreSQL")
        
        # Check if table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'credit_transactions'
            );
        """)
        
        table_exists = cur.fetchone()[0]
        print(f"✅ credit_transactions table exists: {table_exists}")
        
        if table_exists:
            # Check table structure
            cur.execute("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'credit_transactions'
                ORDER BY ordinal_position;
            """)
            
            columns = cur.fetchall()
            print("✅ Table structure:")
            for col in columns:
                print(f"   - {col['column_name']}: {col['data_type']}")
            
            # Check existing records count
            cur.execute("SELECT COUNT(*) FROM credit_transactions;")
            count = cur.fetchone()[0]
            print(f"✅ Existing records count: {count}")
            
            # Show recent records if any
            if count > 0:
                cur.execute("""
                    SELECT transaction_id, user_id, type, amount, created_at 
                    FROM credit_transactions 
                    ORDER BY created_at DESC 
                    LIMIT 5;
                """)
                records = cur.fetchall()
                print("✅ Recent records:")
                for record in records:
                    print(f"   - {record['transaction_id']}: {record['type']} ${record['amount']} for {record['user_id']}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ PostgreSQL connection/query failed: {str(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    test_postgres_connection()
