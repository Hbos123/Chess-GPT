"""
Subscription Tier Descriptions
Defines tier limits and descriptions for display
"""

TIER_DESCRIPTIONS = {
    "unpaid": {
        "name": "Unpaid",
        "monthly_token_allowance": "450,000 tokens/month",
        "daily_tokens": "15,000 tokens/day",
        "approximate_daily_messages": "~3 messages/day",
        "tool_usage": {
            "game_reviews": "Not available",
            "lessons": "Not available",
            "game_storage": "0 games"
        },
        "price": "Free"
    },
    "lite": {
        "name": "Lite",
        "monthly_token_allowance": "1.29M tokens/month",
        "daily_tokens": "100,000 tokens/day",
        "approximate_daily_messages": "~20 messages/day",
        "tool_usage": {
            "game_reviews": "1 per day",
            "lessons": "1 per day",
            "game_storage": "5 games"
        },
        "price": "$1.99 USD/month"
    },
    "starter": {
        "name": "Starter",
        "monthly_token_allowance": "5.8M tokens/month",
        "daily_tokens": "500,000 tokens/day",
        "approximate_daily_messages": "~100 messages/day",
        "tool_usage": {
            "game_reviews": "5 per day",
            "lessons": "5 per day",
            "game_storage": "40 games"
        },
        "price": "$5.99 USD/month"
    },
    "full": {
        "name": "Full",
        "monthly_token_allowance": "11.6M tokens/month",
        "daily_tokens": "1,000,000 tokens/day",
        "approximate_daily_messages": "~200 messages/day",
        "tool_usage": {
            "game_reviews": "Unlimited",
            "lessons": "Unlimited",
            "game_storage": "400 games"
        },
        "price": "$11.99 USD/month"
    }
}
