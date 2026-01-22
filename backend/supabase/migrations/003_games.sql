-- Games table (analyzed games with full review data)

create table public.games (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,

  -- External identity
  platform text check (platform in ('lichess','chesscom','manual')) not null,
  external_id text,
  constraint unique_user_platform_game unique (user_id, platform, external_id),

  -- Game metadata
  game_date timestamptz,
  user_color text check (user_color in ('white','black')),
  opponent_name text,
  user_rating int,
  opponent_rating int,
  result text check (result in ('win','loss','draw','abort','unknown')),
  termination text,
  time_control text,
  time_category text check (time_category in ('bullet','blitz','rapid','classical','correspondence','unknown')),

  -- Opening info
  opening_eco text,
  opening_name text,
  theory_exit_ply int,

  -- Performance metrics
  accuracy_overall numeric,
  accuracy_opening numeric,
  accuracy_middlegame numeric,
  accuracy_endgame numeric,
  avg_cp_loss numeric,
  blunders int default 0,
  mistakes int default 0,
  inaccuracies int default 0,
  
  -- Game characteristics
  total_moves int,
  game_character text check (game_character in ('tactical_battle','dynamic','balanced','positional','unknown')),
  endgame_type text check (endgame_type in ('queen_endgame','rook_endgame','minor_piece_endgame','pawn_endgame','none')),

  -- Raw storage
  pgn text not null,
  eval_trace jsonb,        -- [{ply, eval_cp, mate_in}...]
  time_trace jsonb,        -- [{ply, seconds_remaining}...]
  key_points jsonb,        -- [{ply, labels, category, note}...]
  game_review jsonb,       -- Full GameReview payload from backend

  -- Timestamps
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  analyzed_at timestamptz
);

-- Indexes for common queries
create index games_user_id_idx on public.games (user_id);
create index games_user_date_idx on public.games (user_id, game_date desc nulls last);
create index games_user_opening_idx on public.games (user_id, opening_eco);
create index games_user_result_idx on public.games (user_id, result);
create index games_user_rating_idx on public.games (user_id, user_rating);
create index games_platform_external_idx on public.games (platform, external_id);
create index games_analyzed_at_idx on public.games (analyzed_at desc nulls last);

-- GIN index for key_points JSONB queries
create index games_key_points_gin_idx on public.games using gin (key_points);
create index games_game_review_gin_idx on public.games using gin (game_review);

-- Auto-update timestamp
create trigger set_games_updated_at
  before update on public.games
  for each row execute procedure extensions.moddatetime(updated_at);

-- RLS policies
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

-- RLS for collection_games
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

-- Comments
comment on table public.games is 'User chess games with full analysis data';
comment on column public.games.game_review is 'Complete GameReview JSON payload from analysis engine';
comment on column public.games.key_points is 'Critical moments, blunders, thresholds, etc.';
comment on column public.games.game_character is 'Overall game type: tactical, positional, balanced, dynamic';

