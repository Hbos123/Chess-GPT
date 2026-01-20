-- Computed Habits - Database-side habit calculation
-- Automatically computes and updates habits when games are analyzed

-- Table to store computed habits summary (aggregated from habit_trends)
create table if not exists public.computed_habits (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  
  -- Aggregated habit data (matches frontend ProfileHabitsResponse structure)
  habits_data jsonb not null default '{}'::jsonb,
  
  -- Metadata
  total_games_with_tags integer default 0,
  computed_at timestamptz default now(),
  last_game_analyzed_at timestamptz,
  
  -- Ensure one record per user
  constraint unique_user_habits unique (user_id)
);

-- Indexes
create index if not exists computed_habits_user_idx on public.computed_habits (user_id);
create index if not exists computed_habits_computed_at_idx on public.computed_habits (computed_at desc);

-- RLS policies
alter table public.computed_habits enable row level security;

-- Drop existing policies if they exist
drop policy if exists "Users can view their own computed habits" on public.computed_habits;
drop policy if exists "System can update computed habits" on public.computed_habits;

create policy "Users can view their own computed habits"
  on public.computed_habits for select
  using (auth.uid() = user_id);

create policy "System can update computed habits"
  on public.computed_habits for all
  using (true)  -- Allow system to update (will be called from trigger)
  with check (true);

-- Function to mark habits as needing recomputation
-- The actual computation is done by the backend Python code (too complex for SQL)
create or replace function public.mark_habits_for_recomputation(p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_total_games integer;
begin
  -- Count games with tags
  select count(*) into v_total_games
  from public.games
  where user_id = p_user_id
    and archived_at is null
    and (review_type = 'full' or review_type is null)
    and game_review is not null
    and game_review ? 'ply_records'
    and exists (
      select 1
      from jsonb_array_elements(game_review->'ply_records') as record
      where (record->'analyse'->'tags') is not null
        and jsonb_array_length(record->'analyse'->'tags') > 0
    );

  -- Upsert computed_habits record with needs_computation flag
  insert into public.computed_habits (
    user_id,
    habits_data,
    total_games_with_tags,
    computed_at,
    last_game_analyzed_at
  )
  values (
    p_user_id,
    jsonb_build_object(
      'habits', '[]'::jsonb,
      'strengths', '[]'::jsonb,
      'weaknesses', '[]'::jsonb,
      'baseline_accuracy', 75,
      'total_games', v_total_games,
      'trend_chart', jsonb_build_object(
        'dates', '[]'::jsonb,
        'series', '[]'::jsonb,
        'baseline', 75
      ),
      'needs_computation', true
    ),
    v_total_games,
    now(),
    (select max(analyzed_at) from public.games where user_id = p_user_id and analyzed_at is not null)
  )
  on conflict (user_id) do update
  set total_games_with_tags = excluded.total_games_with_tags,
      last_game_analyzed_at = excluded.last_game_analyzed_at,
      habits_data = jsonb_set(
        coalesce((select habits_data from public.computed_habits where user_id = p_user_id), '{}'::jsonb),
        '{needs_computation}',
        'true'::jsonb
      ),
      computed_at = now();
end;
$$;

-- Trigger to compute habits when a game is analyzed
create or replace function public.trigger_compute_habits()
returns trigger
language plpgsql
security definer
as $$
begin
  -- Only trigger if game_review has been updated and has tags
  if NEW.game_review is not null 
     and NEW.game_review ? 'ply_records'
     and NEW.analyzed_at is not null then
    
    -- Check if game has tags
    declare
      v_has_tags boolean := false;
      v_record jsonb;
      v_tags jsonb;
    begin
      for v_record in select * from jsonb_array_elements(NEW.game_review->'ply_records')
      loop
        v_tags := v_record->'analyse'->'tags';
        if v_tags is not null and jsonb_array_length(v_tags) > 0 then
          v_has_tags := true;
          exit;
        end if;
      end loop;
      
      if v_has_tags then
        -- Mark habits for recomputation (backend will compute)
        perform public.mark_habits_for_recomputation(NEW.user_id);
      end if;
    end;
  end if;
  
  return NEW;
end;
$$;

-- Create trigger
drop trigger if exists games_compute_habits_trigger on public.games;
create trigger games_compute_habits_trigger
  after insert or update of game_review, analyzed_at on public.games
  for each row
  when (NEW.game_review is not null and NEW.analyzed_at is not null)
  execute function public.trigger_compute_habits();

-- Function to get computed habits (for backend to call)
create or replace function public.get_computed_habits(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_habits jsonb;
begin
  select habits_data into v_habits
  from public.computed_habits
  where user_id = p_user_id;
  
  return coalesce(v_habits, '{"habits": [], "strengths": [], "weaknesses": [], "baseline_accuracy": 75, "total_games": 0, "trend_chart": {"dates": [], "series": [], "baseline": 75}}'::jsonb);
end;
$$;

-- Comments
comment on table public.computed_habits is 'Pre-computed habits summary for fast frontend access. Computed by backend Python code.';
comment on function public.mark_habits_for_recomputation(uuid) is 'Marks habits as needing recomputation when new games are analyzed';
comment on function public.get_computed_habits(uuid) is 'Retrieves computed habits for a user';
