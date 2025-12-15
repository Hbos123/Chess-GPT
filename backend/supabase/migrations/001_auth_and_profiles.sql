-- Auth and Profiles Setup
-- Run this first in your Supabase SQL editor

-- Enable necessary extensions
create extension if not exists moddatetime schema extensions;

-- Profiles table (mirrors auth.users with chess-specific data)
create table public.profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  username text unique,
  display_name text,
  avatar_url text,
  rating_chesscom int,
  rating_lichess int,
  chesscom_username text,
  lichess_username text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Auto-update updated_at timestamp
create trigger set_profiles_updated_at
  before update on public.profiles
  for each row execute procedure extensions.moddatetime(updated_at);

-- RLS policies for profiles
alter table public.profiles enable row level security;

create policy "Users can view their own profile"
  on public.profiles for select
  using (auth.uid() = user_id);

create policy "Users can insert their own profile"
  on public.profiles for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own profile"
  on public.profiles for update
  using (auth.uid() = user_id);

-- Function to create profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (user_id, username, display_name, avatar_url)
  values (
    new.id,
    new.raw_user_meta_data->>'username',
    new.raw_user_meta_data->>'display_name',
    new.raw_user_meta_data->>'avatar_url'
  );
  return new;
end;
$$;

-- Trigger to auto-create profile
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Comments
comment on table public.profiles is 'User profiles with chess platform information';
comment on column public.profiles.username is 'Unique username for Chess GPT';
comment on column public.profiles.chesscom_username is 'Chess.com account username';
comment on column public.profiles.lichess_username is 'Lichess account username';

