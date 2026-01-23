-- ============================================================================
-- Subscription System
-- Tiered subscription management with Stripe integration
-- ============================================================================

-- Subscription tiers table
create table public.subscription_tiers (
  id text primary key,  -- 'unpaid', 'lite', 'starter', 'full'
  name text not null,
  daily_messages int not null,  -- Display/fallback (excludes LGP)
  daily_tokens int not null,  -- Primary limit (excludes LGP)
  max_games_storage int not null,
  max_lessons_per_day int,  -- NULL = unlimited
  max_game_reviews_per_day int,  -- NULL = unlimited
  stripe_price_id text,  -- Stripe Price ID for this tier
  created_at timestamptz default now()
);

-- Insert tier definitions
-- Token limits: ~2k tokens per simple request, ~30k per complex request
insert into public.subscription_tiers (id, name, daily_messages, daily_tokens, max_games_storage, max_lessons_per_day, max_game_reviews_per_day, stripe_price_id) values
  ('unpaid', 'Unpaid', 3, 15000, 0, 0, 0, null),  -- ~3 simple requests
  ('lite', 'Lite', 20, 100000, 5, 1, 1, null),  -- ~20 simple or ~3 complex
  ('starter', 'Starter', 100, 500000, 40, 5, 5, null),  -- ~100 simple or ~16 complex
  ('full', 'Full', 200, 1000000, 400, null, null, null);  -- ~200 simple or ~33 complex

-- User subscriptions table
create table public.user_subscriptions (
  user_id uuid primary key references auth.users(id) on delete cascade,
  tier_id text not null references public.subscription_tiers(id),
  stripe_subscription_id text unique,  -- Stripe Subscription ID
  stripe_customer_id text,  -- Stripe Customer ID
  status text check (status in ('active', 'canceled', 'past_due', 'trialing')) default 'active',
  current_period_start timestamptz,
  current_period_end timestamptz,
  canceled_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Auto-update updated_at timestamp
create trigger set_user_subscriptions_updated_at
  before update on public.user_subscriptions
  for each row execute procedure extensions.moddatetime(updated_at);

-- Daily usage tracking (for rate limiting)
create table public.daily_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  ip_address inet,  -- For anonymous/unpaid tracking
  usage_date date not null default current_date,
  messages_count int default 0,  -- Regular messages (excludes LGP) - display only
  tokens_used int default 0,  -- Primary metric: total tokens used (excludes LGP)
  lessons_count int default 0,
  game_reviews_count int default 0,
  created_at timestamptz default now(),
  unique(user_id, usage_date) where user_id is not null,  -- One record per user per day
  unique(ip_address, usage_date) where user_id is null  -- One record per IP per day (for anonymous)
);

-- Indexes for fast lookups
create index daily_usage_user_date_idx on public.daily_usage (user_id, usage_date desc) where user_id is not null;
create index daily_usage_ip_date_idx on public.daily_usage (ip_address, usage_date desc) where user_id is null;
create index user_subscriptions_tier_idx on public.user_subscriptions (tier_id);
create index user_subscriptions_status_idx on public.user_subscriptions (status);

-- RLS policies
alter table public.subscription_tiers enable row level security;
alter table public.user_subscriptions enable row level security;
alter table public.daily_usage enable row level security;

-- Subscription tiers are public (read-only)
create policy "Anyone can view subscription tiers"
  on public.subscription_tiers for select
  using (true);

-- Users can view their own subscription
create policy "Users can view own subscription"
  on public.user_subscriptions for select
  using (auth.uid() = user_id);

-- Users can view their own usage
create policy "Users can view own usage"
  on public.daily_usage for select
  using (auth.uid() = user_id);

-- Service role can manage all (backend operations)
-- Note: Service role bypasses RLS, so we don't need explicit policies for backend
-- But we add them for clarity and future-proofing

create policy "Service role can manage subscriptions"
  on public.user_subscriptions for all
  using (true)
  with check (true);

create policy "Service role can manage usage"
  on public.daily_usage for all
  using (true)
  with check (true);

-- Comments
comment on table public.subscription_tiers is 'Subscription tier definitions with limits';
comment on table public.user_subscriptions is 'User subscription status and Stripe integration';
comment on table public.daily_usage is 'Daily usage tracking for rate limiting (by user_id or ip_address)';
