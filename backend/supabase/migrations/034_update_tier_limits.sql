-- ============================================================================
-- Update Subscription Tier Limits
-- Based on $1, $4.50, $9 USD monthly token costs
-- ============================================================================

-- Update Lite tier: $1 USD/month token cost = 43k tokens/day
UPDATE public.subscription_tiers 
SET 
  daily_tokens = 43000,
  daily_messages = 15,
  max_games_storage = 5,
  max_lessons_per_day = 1,
  max_game_reviews_per_day = 1
WHERE id = 'lite';

-- Update Starter tier: $4.50 USD/month token cost = 193.5k tokens/day
UPDATE public.subscription_tiers 
SET 
  daily_tokens = 193500,
  daily_messages = 65,
  max_games_storage = 40,
  max_lessons_per_day = 5,
  max_game_reviews_per_day = 5
WHERE id = 'starter';

-- Update Full tier: $9 USD/month token cost = 387k tokens/day
UPDATE public.subscription_tiers 
SET 
  daily_tokens = 387000,
  daily_messages = 130,
  max_games_storage = 400,
  max_lessons_per_day = NULL,  -- unlimited
  max_game_reviews_per_day = NULL  -- unlimited
WHERE id = 'full';

-- Update Unpaid tier: 2 messages/day for signed-in users
UPDATE public.subscription_tiers 
SET 
  daily_messages = 2,
  daily_tokens = 15000,
  max_games_storage = 0,
  max_lessons_per_day = 0,
  max_game_reviews_per_day = 0
WHERE id = 'unpaid';
