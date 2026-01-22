-- ============================================================================
-- CHESS GPT - Complete Supabase Schema
-- Run this entire script in Supabase SQL Editor
-- ============================================================================

-- Enable necessary extensions
create extension if not exists moddatetime schema extensions;

-- ============================================================================
-- 1. AUTH & PROFILES
-- ============================================================================

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

-- Profile stats table --------------------------------------------------------
create table public.profile_stats (
  user_id uuid primary key references auth.users(id) on delete cascade,
  stats jsonb not null default '{}'::jsonb,
  updated_at timestamptz default now()
);

alter table public.profile_stats enable row level security;

create policy "Users can view their profile stats"
  on public.profile_stats for select
  using (auth.uid() = user_id);

create policy "Users can insert their profile stats"
  on public.profile_stats for insert
  with check (auth.uid() = user_id);

create policy "Users can update their profile stats"
  on public.profile_stats for update
  using (auth.uid() = user_id);

create policy "Users can delete their profile stats"
  on public.profile_stats for delete
  using (auth.uid() = user_id);

create index profile_stats_updated_idx on public.profile_stats (updated_at desc);

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

-- ============================================================================
-- 2. COLLECTIONS
-- ============================================================================

create table public.collections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  description text,
  color text default '#667eea',
  icon text default '📁',
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint unique_user_collection_name unique (user_id, name)
);

create index collections_user_id_idx on public.collections (user_id);
create index collections_user_name_idx on public.collections (user_id, name);
create index collections_created_at_idx on public.collections (created_at desc);

create trigger set_collections_updated_at
  before update on public.collections
  for each row execute procedure extensions.moddatetime(updated_at);

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

-- ============================================================================
-- 3. GAMES
-- ============================================================================

create table public.games (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  platform text check (platform in ('lichess','chesscom','manual')) not null,
  external_id text,
  constraint unique_user_platform_game unique (user_id, platform, external_id),
  game_date timestamptz,
  user_color text check (user_color in ('white','black')),
  opponent_name text,
  user_rating int,
  opponent_rating int,
  result text check (result in ('win','loss','draw','abort','unknown')),
  termination text,
  time_control text,
  time_category text check (time_category in ('bullet','blitz','rapid','classical','correspondence','unknown')),
  opening_eco text,
  opening_name text,
  theory_exit_ply int,
  accuracy_overall numeric,
  accuracy_opening numeric,
  accuracy_middlegame numeric,
  accuracy_endgame numeric,
  avg_cp_loss numeric,
  blunders int default 0,
  mistakes int default 0,
  inaccuracies int default 0,
  total_moves int,
  game_character text check (game_character in ('tactical_battle','dynamic','balanced','positional','unknown')),
  endgame_type text check (endgame_type in ('queen_endgame','rook_endgame','minor_piece_endgame','pawn_endgame','none')),
  pgn text not null,
  eval_trace jsonb,
  time_trace jsonb,
  key_points jsonb,
  game_review jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  analyzed_at timestamptz
);

create index games_user_id_idx on public.games (user_id);
create index games_user_date_idx on public.games (user_id, game_date desc nulls last);
create index games_user_opening_idx on public.games (user_id, opening_eco);
create index games_user_result_idx on public.games (user_id, result);
create index games_user_rating_idx on public.games (user_id, user_rating);
create index games_platform_external_idx on public.games (platform, external_id);
create index games_analyzed_at_idx on public.games (analyzed_at desc nulls last);
create index games_key_points_gin_idx on public.games using gin (key_points);
create index games_game_review_gin_idx on public.games using gin (game_review);

create trigger set_games_updated_at
  before update on public.games
  for each row execute procedure extensions.moddatetime(updated_at);

alter table public.games enable row level security;

create policy "Users can view their own games"
  on public.games for select
  using (auth.uid() = user_id);

create policy "Users can insert their own games"
  on public.games for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own games"
  on public.games for update
  using (auth.uid() = user_id);

create policy "Users can delete their own games"
  on public.games for delete
  using (auth.uid() = user_id);

-- Junction table: Collections ↔ Games
create table public.collection_games (
  collection_id uuid references public.collections(id) on delete cascade,
  game_id uuid references public.games(id) on delete cascade,
  added_at timestamptz default now(),
  primary key (collection_id, game_id)
);

create index collection_games_collection_idx on public.collection_games (collection_id);
create index collection_games_game_idx on public.collection_games (game_id);

alter table public.collection_games enable row level security;

create policy "Users can manage their collection games"
  on public.collection_games for all
  using (
    exists (
      select 1 from public.collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  );

-- ============================================================================
-- 4. POSITIONS
-- ============================================================================

create table public.positions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  fen text not null,
  side_to_move text check (side_to_move in ('white','black')) not null,
  from_game_id uuid references public.games(id) on delete set null,
  source_ply int,
  move_san text,
  move_uci text,
  eval_cp numeric,
  mate_in int,
  best_move_san text,
  best_move_uci text,
  tags text[] default '{}',
  themes jsonb,
  threats jsonb,
  analysis jsonb,
  user_note text,
  error_note text,
  critical_note text,
  is_critical boolean default false,
  phase text check (phase in ('opening','middlegame','endgame')),
  opening_name text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index positions_user_id_idx on public.positions (user_id);
create index positions_user_game_idx on public.positions (user_id, from_game_id);
create index positions_fen_idx on public.positions (fen);
create index positions_tags_gin_idx on public.positions using gin (tags);
create index positions_phase_idx on public.positions (user_id, phase);
create index positions_critical_idx on public.positions (user_id, is_critical) where is_critical = true;

create trigger set_positions_updated_at
  before update on public.positions
  for each row execute procedure extensions.moddatetime(updated_at);

alter table public.positions enable row level security;

create policy "Users can view their own positions"
  on public.positions for select
  using (auth.uid() = user_id);

create policy "Users can insert their own positions"
  on public.positions for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own positions"
  on public.positions for update
  using (auth.uid() = user_id);

create policy "Users can delete their own positions"
  on public.positions for delete
  using (auth.uid() = user_id);

-- Junction table: Collections ↔ Positions
create table public.collection_positions (
  collection_id uuid references public.collections(id) on delete cascade,
  position_id uuid references public.positions(id) on delete cascade,
  added_at timestamptz default now(),
  primary key (collection_id, position_id)
);

create index collection_positions_collection_idx on public.collection_positions (collection_id);
create index collection_positions_position_idx on public.collection_positions (position_id);

alter table public.collection_positions enable row level security;

create policy "Users can manage their collection positions"
  on public.collection_positions for all
  using (
    exists (
      select 1 from public.collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.collections c
      where c.id = collection_id and c.user_id = auth.uid()
    )
  );

-- ============================================================================
-- 5. CHAT
-- ============================================================================

create table public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  mode text check (mode in ('PLAY','ANALYZE','TACTICS','DISCUSS','LESSON','REVIEW')) default 'DISCUSS',
  linked_game_id uuid references public.games(id) on delete set null,
  linked_position_id uuid references public.positions(id) on delete set null,
  message_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  last_message_at timestamptz default now()
);

create index chat_sessions_user_id_idx on public.chat_sessions (user_id);
create index chat_sessions_user_updated_idx on public.chat_sessions (user_id, last_message_at desc);
create index chat_sessions_linked_game_idx on public.chat_sessions (linked_game_id) where linked_game_id is not null;

create trigger set_chat_sessions_updated_at
  before update on public.chat_sessions
  for each row execute procedure extensions.moddatetime(updated_at);

alter table public.chat_sessions enable row level security;

create policy "Users can view their own chat sessions"
  on public.chat_sessions for select
  using (auth.uid() = user_id);

create policy "Users can create their own chat sessions"
  on public.chat_sessions for insert
  with check (auth.uid() = user_id);

create policy "Users can update their own chat sessions"
  on public.chat_sessions for update
  using (auth.uid() = user_id);

create policy "Users can delete their own chat sessions"
  on public.chat_sessions for delete
  using (auth.uid() = user_id);

-- Chat messages
create table public.chat_messages (
  id bigserial primary key,
  session_id uuid not null references public.chat_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text check (role in ('user','assistant','system')) not null,
  content text not null,
  tool_name text,
  tool_input jsonb,
  tool_output jsonb,
  citations jsonb,
  model text,
  tokens_used int,
  created_at timestamptz default now()
);

create index chat_messages_session_idx on public.chat_messages (session_id, created_at);
create index chat_messages_user_idx on public.chat_messages (user_id);
create index chat_messages_role_idx on public.chat_messages (session_id, role);

alter table public.chat_messages enable row level security;

create policy "Users can view messages in their sessions"
  on public.chat_messages for select
  using (
    exists (
      select 1 from public.chat_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );

create policy "Users can insert messages in their sessions"
  on public.chat_messages for insert
  with check (
    auth.uid() = user_id and
    exists (
      select 1 from public.chat_sessions s
      where s.id = session_id and s.user_id = auth.uid()
    )
  );

-- Function to update session metadata when message added
create or replace function public.update_chat_session_on_message()
returns trigger
language plpgsql
as $$
begin
  update public.chat_sessions
  set 
    message_count = message_count + 1,
    last_message_at = new.created_at
  where id = new.session_id;
  return new;
end;
$$;

create trigger on_chat_message_insert
  after insert on public.chat_messages
  for each row execute procedure public.update_chat_session_on_message();

-- ============================================================================
-- 6. TRAINING & DRILLS
-- ============================================================================

create table public.training_cards (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  card_id text not null,
  fen text not null,
  side_to_move text check (side_to_move in ('white','black')) not null,
  best_move_san text not null,
  best_move_uci text not null,
  drill_type text check (drill_type in ('tactics','defense','critical_choice','conversion','opening','strategic')) not null,
  question text,
  hint text,
  explanation text,
  tags text[] default '{}',
  themes jsonb,
  difficulty_rating int,
  cp_loss_if_wrong numeric,
  source_type text check (source_type in ('own_game','opening_explorer','puzzle_bank')) default 'own_game',
  source_game_id uuid references public.games(id) on delete set null,
  source_ply int,
  phase text,
  opening text,
  srs_stage text check (srs_stage in ('new','learning','review')) default 'new',
  srs_due_date timestamptz default now(),
  srs_interval_days int default 0,
  srs_ease_factor numeric default 2.5,
  srs_lapses int default 0,
  attempts int default 0,
  correct_attempts int default 0,
  total_time_s numeric default 0,
  hints_used int default 0,
  last_attempt_at timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  constraint unique_user_card unique (user_id, card_id)
);

create index training_cards_user_id_idx on public.training_cards (user_id);
create index training_cards_user_due_idx on public.training_cards (user_id, srs_due_date);
create index training_cards_user_stage_idx on public.training_cards (user_id, srs_stage);
create index training_cards_tags_gin_idx on public.training_cards using gin (tags);
create index training_cards_drill_type_idx on public.training_cards (user_id, drill_type);

create trigger set_training_cards_updated_at
  before update on public.training_cards
  for each row execute procedure extensions.moddatetime(updated_at);

alter table public.training_cards enable row level security;

create policy "Users can view their own training cards"
  on public.training_cards for select
  using (auth.uid() = user_id);

create policy "Users can manage their own training cards"
  on public.training_cards for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Training sessions
create table public.training_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id text not null,
  mode text check (mode in ('quick','focused','opening','endgame')) default 'quick',
  total_cards int not null,
  completed_cards int default 0,
  correct_count int default 0,
  incorrect_count int default 0,
  skipped_count int default 0,
  accuracy_pct numeric,
  avg_time_s numeric,
  training_query text,
  blueprint jsonb,
  started_at timestamptz default now(),
  completed_at timestamptz
);

create index training_sessions_user_idx on public.training_sessions (user_id, started_at desc);

alter table public.training_sessions enable row level security;

create policy "Users can view their own training sessions"
  on public.training_sessions for select
  using (auth.uid() = user_id);

create policy "Users can manage their own training sessions"
  on public.training_sessions for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Training attempts
create table public.training_attempts (
  id bigserial primary key,
  user_id uuid not null references auth.users(id) on delete cascade,
  session_id uuid references public.training_sessions(id) on delete cascade,
  card_id uuid references public.training_cards(id) on delete set null,
  correct boolean not null,
  time_s numeric not null,
  hints_used int default 0,
  user_move text,
  attempted_at timestamptz default now()
);

create index training_attempts_user_idx on public.training_attempts (user_id, attempted_at desc);
create index training_attempts_session_idx on public.training_attempts (session_id);
create index training_attempts_card_idx on public.training_attempts (card_id);

alter table public.training_attempts enable row level security;

create policy "Users can view their own attempts"
  on public.training_attempts for select
  using (auth.uid() = user_id);

create policy "Users can insert their own attempts"
  on public.training_attempts for insert
  with check (auth.uid() = user_id);

-- ============================================================================
-- 7. STORED PROCEDURES (RPCs)
-- ============================================================================

-- Save or upsert a complete game review
create or replace function public.save_game_review(
  p_user_id uuid,
  p_game jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_game_id uuid;
begin
  if p_user_id != auth.uid() then
    raise exception 'Unauthorized';
  end if;

  insert into public.games (
    id, user_id, platform, external_id, game_date, user_color, opponent_name,
    user_rating, opponent_rating, result, termination, time_control, time_category,
    opening_eco, opening_name, theory_exit_ply,
    accuracy_overall, accuracy_opening, accuracy_middlegame, accuracy_endgame,
    avg_cp_loss, blunders, mistakes, inaccuracies,
    total_moves, game_character, endgame_type,
    pgn, eval_trace, time_trace, key_points, game_review, analyzed_at
  )
  values (
    coalesce((p_game->>'id')::uuid, gen_random_uuid()),
    p_user_id,
    p_game->>'platform',
    p_game->>'external_id',
    (p_game->>'game_date')::timestamptz,
    p_game->>'user_color',
    p_game->>'opponent_name',
    (p_game->>'user_rating')::int,
    (p_game->>'opponent_rating')::int,
    p_game->>'result',
    p_game->>'termination',
    p_game->>'time_control',
    p_game->>'time_category',
    p_game->>'opening_eco',
    p_game->>'opening_name',
    (p_game->>'theory_exit_ply')::int,
    (p_game->>'accuracy_overall')::numeric,
    (p_game->>'accuracy_opening')::numeric,
    (p_game->>'accuracy_middlegame')::numeric,
    (p_game->>'accuracy_endgame')::numeric,
    (p_game->>'avg_cp_loss')::numeric,
    coalesce((p_game->>'blunders')::int, 0),
    coalesce((p_game->>'mistakes')::int, 0),
    coalesce((p_game->>'inaccuracies')::int, 0),
    (p_game->>'total_moves')::int,
    p_game->>'game_character',
    p_game->>'endgame_type',
    p_game->>'pgn',
    p_game->'eval_trace',
    p_game->'time_trace',
    p_game->'key_points',
    p_game,
    now()
  )
  on conflict (user_id, platform, external_id)
  where external_id is not null
  do update set
    game_date = excluded.game_date,
    opening_eco = excluded.opening_eco,
    opening_name = excluded.opening_name,
    accuracy_overall = excluded.accuracy_overall,
    accuracy_opening = excluded.accuracy_opening,
    accuracy_middlegame = excluded.accuracy_middlegame,
    accuracy_endgame = excluded.accuracy_endgame,
    avg_cp_loss = excluded.avg_cp_loss,
    blunders = excluded.blunders,
    mistakes = excluded.mistakes,
    inaccuracies = excluded.inaccuracies,
    total_moves = excluded.total_moves,
    game_character = excluded.game_character,
    endgame_type = excluded.endgame_type,
    pgn = excluded.pgn,
    eval_trace = excluded.eval_trace,
    time_trace = excluded.time_trace,
    key_points = excluded.key_points,
    game_review = excluded.game_review,
    analyzed_at = now(),
    updated_at = now()
  returning id into v_game_id;

  return v_game_id;
end;
$$;

-- Save a single position
create or replace function public.save_position(
  p_user_id uuid,
  p_position jsonb
)
returns uuid
language plpgsql
security definer
set search_path = public
as $$
declare
  v_position_id uuid;
begin
  if p_user_id != auth.uid() then
    raise exception 'Unauthorized';
  end if;

  insert into public.positions (
    user_id, fen, side_to_move, from_game_id, source_ply,
    move_san, move_uci, eval_cp, mate_in,
    best_move_san, best_move_uci,
    tags, themes, threats, analysis,
    user_note, error_note, critical_note, is_critical,
    phase, opening_name
  )
  values (
    p_user_id,
    p_position->>'fen',
    p_position->>'side_to_move',
    nullif((p_position->>'from_game_id'),'')::uuid,
    (p_position->>'source_ply')::int,
    p_position->>'move_san',
    p_position->>'move_uci',
    (p_position->>'eval_cp')::numeric,
    (p_position->>'mate_in')::int,
    p_position->>'best_move_san',
    p_position->>'best_move_uci',
    array(select jsonb_array_elements_text(coalesce(p_position->'tags', '[]'::jsonb))),
    p_position->'themes',
    p_position->'threats',
    p_position,
    p_position->>'user_note',
    p_position->>'error_note',
    p_position->>'critical_note',
    coalesce((p_position->>'is_critical')::boolean, false),
    p_position->>'phase',
    p_position->>'opening_name'
  )
  returning id into v_position_id;

  return v_position_id;
end;
$$;

-- Get user statistics
create or replace function public.get_user_stats(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_stats jsonb;
begin
  if p_user_id != auth.uid() then
    raise exception 'Unauthorized';
  end if;

  select jsonb_build_object(
    'total_games', count(*),
    'total_analyzed', count(*) filter (where analyzed_at is not null),
    'avg_accuracy', avg(accuracy_overall),
    'win_rate', (count(*) filter (where result = 'win')::numeric / nullif(count(*), 0)) * 100,
    'total_blunders', sum(blunders),
    'total_mistakes', sum(mistakes),
    'avg_blunders_per_game', avg(blunders),
    'avg_mistakes_per_game', avg(mistakes),
    'most_played_opening', (
      select opening_name
      from public.games
      where user_id = p_user_id and opening_name is not null
      group by opening_name
      order by count(*) desc
      limit 1
    ),
    'recent_accuracy_trend', (
      select avg(accuracy_overall)
      from public.games
      where user_id = p_user_id
      and game_date > now() - interval '30 days'
    )
  )
  into v_stats
  from public.games
  where user_id = p_user_id;

  return v_stats;
end;
$$;

-- Get SRS due cards
create or replace function public.get_srs_due_cards(
  p_user_id uuid,
  p_max_cards int default 20
)
returns setof public.training_cards
language plpgsql
security definer
set search_path = public
as $$
begin
  if p_user_id != auth.uid() then
    raise exception 'Unauthorized';
  end if;

  return query
  select *
  from public.training_cards
  where user_id = p_user_id
    and srs_due_date <= now()
  order by srs_due_date asc
  limit p_max_cards;
end;
$$;

-- Update SRS state after attempt
create or replace function public.update_card_srs(
  p_card_id uuid,
  p_correct boolean,
  p_time_s numeric,
  p_hints_used int
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_card public.training_cards;
  v_new_interval int;
  v_new_stage text;
  v_new_ease numeric;
  v_new_due timestamptz;
begin
  select * into v_card
  from public.training_cards
  where id = p_card_id and user_id = auth.uid();

  if not found then
    raise exception 'Card not found or unauthorized';
  end if;

  if p_correct then
    if v_card.srs_stage = 'new' then
      v_new_stage := 'learning';
      v_new_interval := 1;
      v_new_ease := 2.5;
    elsif v_card.srs_stage = 'learning' then
      if v_card.srs_interval_days < 7 then
        v_new_stage := 'learning';
        v_new_interval := least(7, v_card.srs_interval_days * 2);
        v_new_ease := v_card.srs_ease_factor;
      else
        v_new_stage := 'review';
        v_new_interval := 21;
        v_new_ease := v_card.srs_ease_factor;
      end if;
    else
      v_new_stage := 'review';
      v_new_interval := (v_card.srs_interval_days * v_card.srs_ease_factor)::int;
      v_new_ease := least(2.8, v_card.srs_ease_factor + 0.1);
    end if;
  else
    if v_card.srs_stage = 'review' then
      v_new_stage := 'learning';
      v_new_interval := 1;
    else
      v_new_stage := v_card.srs_stage;
      v_new_interval := greatest(1, v_card.srs_interval_days / 2);
    end if;
    v_new_ease := greatest(1.3, v_card.srs_ease_factor - 0.2);
  end if;

  v_new_due := now() + (v_new_interval || ' days')::interval;

  update public.training_cards
  set
    attempts = attempts + 1,
    correct_attempts = correct_attempts + (case when p_correct then 1 else 0 end),
    total_time_s = total_time_s + p_time_s,
    hints_used = hints_used + p_hints_used,
    last_attempt_at = now(),
    srs_stage = v_new_stage,
    srs_interval_days = v_new_interval,
    srs_ease_factor = v_new_ease,
    srs_due_date = v_new_due,
    srs_lapses = srs_lapses + (case when p_correct then 0 else 1 end)
  where id = p_card_id;

  return jsonb_build_object(
    'success', true,
    'new_stage', v_new_stage,
    'new_interval_days', v_new_interval,
    'new_due_date', v_new_due,
    'new_ease_factor', v_new_ease
  );
end;
$$;

-- ============================================================================
-- COMPLETE! Tables created: 11, Indexes: 30+, Policies: 25+
-- ============================================================================

-- Verify setup
do $$
begin
  raise notice '✅ Chess GPT Supabase schema setup complete!';
  raise notice '   Tables created: profiles, collections, games, positions, chat_sessions, chat_messages, training_cards, training_sessions, training_attempts, collection_games, collection_positions';
  raise notice '   RLS enabled on all tables';
  raise notice '   Indexes created for performance';
  raise notice '   RPCs ready: save_game_review, save_position, get_user_stats, get_srs_due_cards, update_card_srs';
end $$;

