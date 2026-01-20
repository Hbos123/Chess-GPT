#!/usr/bin/env python3
"""
Apply migration 030_detailed_analytics_cache.sql via direct PostgreSQL connection.
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)

def get_db_connection():
    """Get PostgreSQL connection from Supabase URL."""
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        print("❌ SUPABASE_URL not set in environment")
        sys.exit(1)
    
    # Extract project ref from URL
    try:
        project_ref = supabase_url.replace("https://", "").replace("http://", "").split(".supabase.co")[0]
    except:
        print("❌ Could not extract project ref from SUPABASE_URL")
        sys.exit(1)
    
    # Get database password
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    if not db_password:
        print("⚠️  SUPABASE_DB_PASSWORD not set in .env")
        print("   Find it in: Supabase Dashboard → Settings → Database → Database Password")
        db_password = input("Enter your Supabase database password: ").strip()
        if not db_password:
            print("❌ Password required")
            sys.exit(1)
    
    # Try transaction pooler first (port 6543)
    pooler_conn_string = f"postgresql://postgres.{project_ref}:{db_password}@{project_ref}.pooler.supabase.com:6543/postgres"
    direct_conn_string = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
    
    connection_options = {
        'connect_timeout': 30,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5
    }
    
    # Try pooler first
    print(f"🔌 Attempting connection via Transaction Pooler...")
    try:
        conn = psycopg2.connect(pooler_conn_string, **connection_options)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print("✅ Connected via Transaction Pooler!")
        return conn
    except psycopg2.OperationalError:
        print(f"   ⚠️  Pooler connection failed, trying direct connection...")
        try:
            conn = psycopg2.connect(direct_conn_string, **connection_options)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            print("✅ Connected via direct connection!")
            return conn
        except psycopg2.OperationalError as e:
            print(f"❌ Connection failed: {e}")
            sys.exit(1)

def main():
    """Apply migration 030."""
    print("🚀 Applying migration 030: detailed_analytics_cache\n")
    
    migration_file = backend_dir / "supabase" / "migrations" / "030_detailed_analytics_cache.sql"
    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)
    
    # Connect to database
    conn = get_db_connection()
    
    try:
        print(f"\n📄 Executing: {migration_file.name}")
        
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        # Split by semicolons and execute statements
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        cursor = conn.cursor()
        executed = 0
        
        for i, statement in enumerate(statements, 1):
            if not statement:
                continue
            
            try:
                cursor.execute(statement + ';')
                executed += 1
            except Exception as e:
                error_msg = str(e)
                if "already exists" in error_msg.lower():
                    print(f"   ⚠️  Statement {i} skipped (already exists): {error_msg[:100]}")
                else:
                    print(f"   ❌ Statement {i} failed: {error_msg[:200]}")
                    raise
        
        cursor.close()
        print(f"   ✅ Executed {executed} statements successfully")
        print("\n✅ Migration 030 completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()
        print("🔌 Connection closed")

if __name__ == "__main__":
    main()

