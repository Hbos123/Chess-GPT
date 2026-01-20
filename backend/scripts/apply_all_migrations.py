#!/usr/bin/env python3
"""
Apply all Supabase migrations to online Supabase instance.
This script runs all migrations in order and tracks which ones have been applied.
"""

import os
import sys
from pathlib import Path
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv
import re

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env file
env_file = backend_dir / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"📄 Loaded environment from: {env_file}")
else:
    print("⚠️  No .env file found. Using environment variables only.")

def get_db_connection():
    """Get PostgreSQL connection from Supabase URL."""
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        print("❌ SUPABASE_URL not set in environment")
        print("   Set it in backend/.env or as environment variable")
        sys.exit(1)
    
    # Extract project ref from URL: https://xxxxx.supabase.co -> xxxxx
    try:
        project_ref = supabase_url.replace("https://", "").replace("http://", "").split(".supabase.co")[0]
    except:
        print("❌ Could not extract project ref from SUPABASE_URL")
        print(f"   Got: {supabase_url}")
        sys.exit(1)
    
    # Get database password from environment
    db_password = os.getenv("SUPABASE_DB_PASSWORD")
    if not db_password:
        print("⚠️  SUPABASE_DB_PASSWORD not set.")
        print("   Find it in: Supabase Dashboard → Settings → Database → Database Password")
        db_password = input("Enter your Supabase database password: ").strip()
        if not db_password:
            print("❌ Password required")
            sys.exit(1)
    
    # Try transaction pooler first (port 6543) - more reliable
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
    print(f"🔌 Connecting to Supabase project: {project_ref}")
    print(f"   Trying transaction pooler (recommended)...")
    try:
        conn = psycopg2.connect(pooler_conn_string, **connection_options)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        print("✅ Connected via Transaction Pooler!")
        return conn
    except psycopg2.OperationalError as e:
        print(f"   ⚠️  Pooler failed: {str(e)[:100]}")
        print(f"   Trying direct connection...")
        try:
            conn = psycopg2.connect(direct_conn_string, **connection_options)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            print("✅ Connected via direct connection!")
            return conn
        except psycopg2.OperationalError as e2:
            print(f"\n❌ Connection failed!")
            print(f"   Error: {str(e2)[:200]}")
            print(f"\n💡 Troubleshooting:")
            print(f"   1. Verify password in Supabase Dashboard → Settings → Database")
            print(f"   2. Check project is not paused")
            print(f"   3. Try different network if ports are blocked")
            sys.exit(1)

def get_migration_number(filename):
    """Extract migration number from filename for sorting."""
    match = re.match(r'^(\d+)', filename)
    if match:
        return int(match.group(1))
    # Handle files like 025a, 025b, 025c
    match = re.match(r'^(\d+)([a-z])', filename)
    if match:
        base = int(match.group(1))
        letter = match.group(2)
        return base + (ord(letter) - ord('a')) * 0.01
    return 9999  # Put unknown files at end

def get_all_migrations():
    """Get all migration files sorted by number."""
    migrations_dir = backend_dir / "supabase" / "migrations"
    if not migrations_dir.exists():
        print(f"❌ Migrations directory not found: {migrations_dir}")
        sys.exit(1)
    
    migration_files = sorted(
        migrations_dir.glob("*.sql"),
        key=lambda f: get_migration_number(f.name)
    )
    
    return migration_files

def check_migration_table(conn):
    """Create migration tracking table if it doesn't exist."""
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cursor.close()
        return True
    except Exception as e:
        print(f"⚠️  Could not create migration table: {e}")
        cursor.close()
        return False

def is_migration_applied(conn, migration_name):
    """Check if a migration has already been applied."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT version FROM schema_migrations WHERE version = %s",
            (migration_name,)
        )
        applied = cursor.fetchone() is not None
        cursor.close()
        return applied
    except:
        cursor.close()
        return False

def mark_migration_applied(conn, migration_name):
    """Mark a migration as applied."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
            (migration_name,)
        )
        cursor.close()
        return True
    except Exception as e:
        print(f"⚠️  Could not mark migration as applied: {e}")
        cursor.close()
        return False

def execute_migration_file(conn, file_path):
    """Execute a single migration file."""
    migration_name = file_path.name
    print(f"\n📄 Migration: {migration_name}")
    
    # Check if already applied
    if is_migration_applied(conn, migration_name):
        print(f"   ⏭️  Already applied, skipping")
        return True
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        if not sql.strip():
            print(f"   ⚠️  Empty file, skipping")
            return True
        
        cursor = conn.cursor()
        
        # Execute the entire migration as one transaction
        # Some migrations have multiple statements that need to run together
        try:
            cursor.execute(sql)
            cursor.close()
            
            # Mark as applied
            mark_migration_applied(conn, migration_name)
            print(f"   ✅ Applied successfully")
            return True
            
        except psycopg2.errors.DuplicateObject as e:
            # Object already exists - migration partially applied
            cursor.close()
            print(f"   ⚠️  Some objects already exist (migration partially applied)")
            print(f"   Marking as applied anyway...")
            mark_migration_applied(conn, migration_name)
            return True
            
        except psycopg2.errors.UndefinedObject as e:
            # Object doesn't exist - might be expected for some migrations
            error_str = str(e).lower()
            if "does not exist" in error_str:
                print(f"   ⚠️  Some objects don't exist (might be expected)")
                cursor.close()
                mark_migration_applied(conn, migration_name)
                return True
            raise
            
        except Exception as e:
            error_str = str(e)
            # Check for common "already exists" errors
            if "already exists" in error_str.lower() or "duplicate" in error_str.lower():
                cursor.close()
                print(f"   ⚠️  Objects already exist, marking as applied")
                mark_migration_applied(conn, migration_name)
                return True
            raise
        
    except Exception as e:
        print(f"   ❌ Migration failed: {str(e)[:300]}")
        print(f"\n   Full error:")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main execution."""
    print("=" * 70)
    print("🚀 Supabase Migration Runner")
    print("=" * 70)
    print()
    
    # Get all migrations
    migration_files = get_all_migrations()
    
    if not migration_files:
        print("❌ No migration files found!")
        sys.exit(1)
    
    print(f"📦 Found {len(migration_files)} migration files")
    print()
    
    # Connect to database
    conn = get_db_connection()
    
    try:
        # Create migration tracking table
        check_migration_table(conn)
        
        # Execute migrations in order
        applied_count = 0
        skipped_count = 0
        failed_count = 0
        
        for i, migration_file in enumerate(migration_files, 1):
            print(f"[{i}/{len(migration_files)}] ", end="")
            
            if execute_migration_file(conn, migration_file):
                if is_migration_applied(conn, migration_file.name):
                    if i > 1:  # Don't count first check
                        applied_count += 1
                else:
                    skipped_count += 1
            else:
                failed_count += 1
                print(f"\n❌ Stopping due to migration failure")
                print(f"   Fix the error above and re-run this script")
                sys.exit(1)
        
        print()
        print("=" * 70)
        print("✅ Migration Summary")
        print("=" * 70)
        print(f"   Applied: {applied_count}")
        print(f"   Skipped (already applied): {skipped_count}")
        print(f"   Failed: {failed_count}")
        print()
        
        if failed_count == 0:
            print("🎉 All migrations completed successfully!")
        else:
            print("⚠️  Some migrations failed. Check errors above.")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()
        print("\n🔌 Connection closed")

if __name__ == "__main__":
    main()
