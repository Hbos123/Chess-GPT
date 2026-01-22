-- Migration 017: Normalized Tags System
-- Creates normalized tags lookup table and move_tags junction table
-- This enables efficient tag queries, frequency analysis, and co-occurrence detection

-- Tags lookup table
create table if not exists public.tags (
  id serial primary key,
  name text unique not null,
  created_at timestamptz default now()
);

create index if not exists tags_name_idx on public.tags (name);

-- Move tags junction table (many-to-many)
-- Note: References moves_raw which will be created in migration 018
-- This migration can run first, but move_tags inserts will fail until moves_raw exists
create table if not exists public.move_tags (
  move_id uuid references public.moves_raw(id) on delete cascade,
  tag_id int references public.tags(id) on delete cascade,
  primary key (move_id, tag_id)
);

create index if not exists move_tags_move_idx on public.move_tags (move_id);
create index if not exists move_tags_tag_idx on public.move_tags (tag_id);

-- Comments
comment on table public.tags is 'Normalized tag names for chess themes/patterns';
comment on table public.move_tags is 'Many-to-many relationship between moves and tags';
