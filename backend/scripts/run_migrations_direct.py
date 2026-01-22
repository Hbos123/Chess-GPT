#!/usr/bin/env python3
"""
Run Supabase migrations directly via PostgreSQL connection.
This bypasses the CLI and may work better with connection issues.
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

# Load environment variables from .env file
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"📄 Loaded environment from: {env_file}")

def get_db_connection():
    """Get PostgreSQL connection from Supabase URL.
    Tries transaction pooler first (more reliable), then direct connection.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        print("❌ SUPABASE_URL not set in environment")
        sys.exit(1)
    
    # Extract project ref from URL: https://xxxxx.supabase.co -> xxxxx
    try:
        project_ref = supabase_url.replace("https://", "").replace("http://", "").split(".supabase.co")[0]
    except:
        print("❌ Could not extract project ref from SUPABASE_URL")
        sys.exit(1)
    
    # Get database password from environment or prompt
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    if not db_password:
        print("⚠️  SUPABASE_DB_PASSWORD not set. You can:")
        print("   1. Set it in your .env file: SUPABASE_DB_PASSWORD=your_password")
        print("   2. Or enter it when prompted below")
        print("   (Find it in: Supabase Dashboard → Settings → Database → Database Password)")
        db_password = input("Enter your Supabase database password: ").strip()
        if not db_password:
            print("❌ Password required")
            sys.exit(1)
    
    # Try transaction pooler first (port 6543) - more reliable, bypasses firewalls
    pooler_conn_string = f"postgresql://postgres.{project_ref}:{db_password}@{project_ref}.pooler.supabase.com:6543/postgres"
    
    # Direct connection as fallback (port 5432)
    direct_conn_string = f"postgresql://postgres:{db_password}@db.{project_ref}.supabase.co:5432/postgres"
    
    connection_options = {
        'connect_timeout': 30,
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5
    }
    
    # Try pooler first
    print(f"🔌 Attempting connection via Transaction Pooler (recommended)...")
    print(f"   Host: {project_ref}.pooler.supabase.com:6543")
    try:
        conn = psycopg2.connect(pooler_conn_string, **connection_options)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print("✅ Connected via Transaction Pooler!")
        return conn
    except psycopg2.OperationalError as e:
        pooler_error = str(e)
        print(f"   ⚠️  Pooler connection failed: {pooler_error[:100]}")
        print(f"\n🔌 Trying direct connection as fallback...")
        print(f"   Host: db.{project_ref}.supabase.co:5432")
        try:
            conn = psycopg2.connect(direct_conn_string, **connection_options)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            print("✅ Connected via direct connection!")
            return conn
        except psycopg2.OperationalError as e2:
            print(f"\n❌ Both connection methods failed!")
            print(f"\n📊 Connection Diagnostics:")
            print(f"   Pooler error: {pooler_error[:150]}")
            print(f"   Direct error: {str(e2)[:150]}")
            print(f"\n💡 Troubleshooting:")
            print(f"   1. Verify password: Supabase Dashboard → Settings → Database")
            print(f"   2. Check network: Try mobile hotspot or different WiFi")
            print(f"   3. DNS issue: The 'db.' subdomain may not be resolving")
            print(f"   4. Port blocked: Your network may block ports 5432/6543")
            print(f"   5. Project paused: Check Supabase Dashboard for project status")
            print(f"\n🔗 Get connection string from:")
            print(f"   Supabase Dashboard → Settings → Database → Connection Pooling")
            sys.exit(1)

def execute_migration_file(conn, file_path):
    """Execute a single migration file."""
    print(f"\n📄 Executing: {file_path.name}")
    
    try:
        with open(file_path, 'r') as f:
            sql = f.read()
        
        # Split by semicolons and execute statements one by one
        # This helps with error reporting
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        cursor = conn.cursor()
        executed = 0
        
        for i, statement in enumerate(statements, 1):
            if not statement:
                continue
            
            try:
                # Add semicolon back for execution
                cursor.execute(statement + ';')
                executed += 1
            except Exception as e:
                # Some statements might fail if already applied (IF NOT EXISTS)
                error_msg = str(e)
                if "already exists" in error_msg.lower() or "does not exist" in error_msg.lower():
                    print(f"   ⚠️  Statement {i} skipped (already applied or not needed): {error_msg[:100]}")
                else:
                    print(f"   ❌ Statement {i} failed: {error_msg[:200]}")
                    raise
        
        cursor.close()
        print(f"   ✅ Executed {executed} statements successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Migration failed: {e}")
        return False

def main():
    """Main execution."""
    print("🚀 Running Supabase migrations via direct PostgreSQL connection\n")
    
    # Get migrations directory
    migrations_dir = backend_dir / "supabase" / "migrations"
    if not migrations_dir.exists():
        print(f"❌ Migrations directory not found: {migrations_dir}")
        sys.exit(1)
    
    # Migration files in order
    migration_files = [
        migrations_dir / "025a_fix_analytics_schema_part1.sql",
        migrations_dir / "025b_fix_analytics_schema_part2.sql",
        migrations_dir / "025c_fix_analytics_schema_part3.sql",
    ]
    
    # Check all files exist
    for f in migration_files:
        if not f.exists():
            print(f"❌ Migration file not found: {f}")
            sys.exit(1)
    
    # Connect to database
    conn = get_db_connection()
    
    try:
        # Execute migrations in order
        for migration_file in migration_files:
            success = execute_migration_file(conn, migration_file)
            if not success:
                print(f"\n❌ Migration {migration_file.name} failed. Stopping.")
                sys.exit(1)
        
        print("\n✅ All migrations completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)
    finally:
        conn.close()
        print("🔌 Connection closed")

if __name__ == "__main__":
    main()

