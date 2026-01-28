"""
Script to fetch Stripe Price IDs from Product IDs and update database
Run this after setting up Stripe products to populate price IDs in the database
"""
import os
import sys
import stripe
from supabase import create_client, Client

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    print("❌ Error: STRIPE_SECRET_KEY environment variable not set")
    sys.exit(1)

# Initialize Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
if not supabase_url or not supabase_key:
    print("❌ Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables not set")
    sys.exit(1)

supabase: Client = create_client(supabase_url, supabase_key)

# Product IDs provided by user
PRODUCT_IDS = {
    "lite": "prod_TsQo1zbH6bGfdI",
    "starter": "prod_TsQoQi21vEIH81",
    "full": "prod_TsQphLJLlX0wO1"
}

def get_price_id_from_product(product_id: str) -> str:
    """Get the default/active price ID for a product"""
    try:
        # List all prices for this product
        prices = stripe.Price.list(product=product_id, active=True, limit=1)
        
        if prices.data:
            price_id = prices.data[0].id
            price_info = prices.data[0]
            print(f"   ✅ Found price: {price_id}")
            print(f"      Amount: ${price_info.unit_amount / 100:.2f} {price_info.currency.upper()}")
            print(f"      Interval: {price_info.recurring.interval if price_info.recurring else 'one-time'}")
            return price_id
        else:
            print(f"   ⚠️  No active prices found for product {product_id}")
            return None
    except Exception as e:
        print(f"   ❌ Error fetching price for product {product_id}: {e}")
        return None

def update_database(tier_id: str, price_id: str):
    """Update subscription_tiers table with price ID"""
    try:
        result = supabase.table("subscription_tiers")\
            .update({"stripe_price_id": price_id})\
            .eq("id", tier_id)\
            .execute()
        
        if result.data:
            print(f"   ✅ Updated database: tier '{tier_id}' → price '{price_id}'")
            return True
        else:
            print(f"   ⚠️  No rows updated for tier '{tier_id}'")
            return False
    except Exception as e:
        print(f"   ❌ Error updating database: {e}")
        return False

def main():
    print("🔍 Fetching Stripe Price IDs from Product IDs...\n")
    
    price_mapping = {}
    
    for tier_id, product_id in PRODUCT_IDS.items():
        print(f"📦 Tier: {tier_id}")
        print(f"   Product ID: {product_id}")
        
        price_id = get_price_id_from_product(product_id)
        if price_id:
            price_mapping[tier_id] = price_id
        print()
    
    if not price_mapping:
        print("❌ No price IDs found. Please check your Stripe products have active prices.")
        sys.exit(1)
    
    print("💾 Updating database...\n")
    
    success_count = 0
    for tier_id, price_id in price_mapping.items():
        if update_database(tier_id, price_id):
            success_count += 1
        print()
    
    print(f"✅ Successfully updated {success_count}/{len(price_mapping)} tiers")
    print("\n📋 Summary:")
    for tier_id, price_id in price_mapping.items():
        print(f"   {tier_id}: {price_id}")

if __name__ == "__main__":
    main()
