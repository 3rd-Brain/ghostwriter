import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from typing import Dict, Optional, List
from datetime import datetime
import uuid

class PostgresConnection:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")

    def get_connection(self):
        """Get a PostgreSQL connection"""
        return psycopg2.connect(self.database_url)

    def execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Execute a query with optional parameters"""
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)

            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)

            # CRITICAL: Always commit the transaction
            conn.commit()

            if fetch:
                return cur.fetchall()

            return True

        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()

def create_credit_transactions_table():
    """Create the credit_transactions table"""
    postgres = PostgresConnection()

    create_table_query = """
    CREATE TABLE IF NOT EXISTS credit_transactions (
        transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id VARCHAR(255) NOT NULL,
        type VARCHAR(50) NOT NULL CHECK (type IN ('purchase', 'consumption', 'refund', 'bonus')),
        amount DECIMAL(10, 6) NOT NULL,
        balance_before DECIMAL(10, 6) NOT NULL,
        balance_after DECIMAL(10, 6) NOT NULL,
        reference_id VARCHAR(255),
        metadata JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    """

    # Create indexes for better performance
    create_indexes_query = """
    CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
    CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON credit_transactions(type);
    CREATE INDEX IF NOT EXISTS idx_credit_transactions_created_at ON credit_transactions(created_at);
    CREATE INDEX IF NOT EXISTS idx_credit_transactions_reference_id ON credit_transactions(reference_id);
    """

    try:
        postgres.execute_query(create_table_query)
        postgres.execute_query(create_indexes_query)
        print("✅ Credit transactions table created successfully!")
        return {"status": "success", "message": "Table created successfully"}
    except Exception as e:
        print(f"❌ Error creating table: {str(e)}")
        return {"status": "error", "message": str(e)}

def verify_table_creation():
    """Verify that the table was created correctly"""
    postgres = PostgresConnection()

    # Check if table exists and get its structure
    check_query = """
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'credit_transactions'
    ORDER BY ordinal_position;
    """

    try:
        columns = postgres.execute_query(check_query, fetch=True)
        if columns:
            print("✅ Table structure:")
            for col in columns:
                print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
            return {"status": "success", "columns": len(columns)}
        else:
            print("❌ Table not found")
            return {"status": "error", "message": "Table not found"}
    except Exception as e:
        print(f"❌ Error verifying table: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    print("🗄️  Setting up PostgreSQL Credit Transactions Table")
    print("-" * 50)

    # Create table
    result = create_credit_transactions_table()

    if result["status"] == "success":
        # Verify creation
        verify_result = verify_table_creation()
        print(f"\nTable verification: {verify_result['status']}")