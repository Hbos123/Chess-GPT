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

-- Comments
comment on table public.tags is 'Normalized tag names for chess themes/patterns';
