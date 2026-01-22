-- Collections (folders for organizing games and positions)

create table public.collections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text,
  color text default '#667eea',  -- UI color for the collection
  icon text default '📁',          -- Emoji icon
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  
  -- Ensure unique collection names per user
  constraint unique_user_collection_name unique (user_id, name)
);

-- Indexes
create index collections_user_id_idx on public.collections (user_id);
create index collections_user_name_idx on public.collections (user_id, name);
create index collections_created_at_idx on public.collections (created_at desc);

-- Auto-update timestamp
create trigger set_collections_updated_at
  before update on public.collections
  for each row execute procedure extensions.moddatetime(updated_at);

-- RLS policies
alter table public.collections enable row level security;

create policy "Users can view their own collections"
  on public.collections for select
  using (auth.uid() = user_id);

create policy "Users can create their own collections"
  on public.collections for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own collections"
  on public.collections for update
  using (auth.uid() = user_id);

create policy "Users can delete their own collections"
  on public.collections for delete
  using (auth.uid() = user_id);

-- Comments
comment on table public.collections is 'User-created folders for organizing games and positions';
comment on column public.collections.color is 'Hex color for UI display';
comment on column public.collections.icon is 'Emoji or icon identifier';

