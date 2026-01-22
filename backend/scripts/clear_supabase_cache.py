"""
Utility script to clear cached Supabase lessons/stats when rolling out schema updates.
"""

import os
import argparse

from supabase_client import SupabaseClient


def clear_cache(confirm: bool = False) -> None:
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not service_key:
        raise SystemExit("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set.")

    if not confirm:
        print("⚠️  Pass --confirm to actually delete cached rows.")
        return

    client = SupabaseClient(url, service_key).client
    print("🧹 Clearing cached lesson/stat tables…")
    client.table("opening_lessons").delete().neq("user_id", "").execute()
    client.table("profile_stats").delete().neq("user_id", "").execute()
    print("✅ Supabase cache cleared.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clear Supabase caches for lessons/stats.")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required to actually run the deletion.",
    )
    args = parser.parse_args()
    clear_cache(confirm=args.confirm)

