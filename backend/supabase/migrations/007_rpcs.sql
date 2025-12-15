-- Stored procedures for atomic operations

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
  -- Verify user_id matches auth
  if p_user_id != auth.uid() then
    raise exception 'Unauthorized';
  end if;

  -- Upsert game
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
  -- Verify user_id matches auth
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

-- Get user statistics (aggregated performance)
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
  -- Get card and verify ownership
  select * into v_card
  from public.training_cards
  where id = p_card_id and user_id = auth.uid();

  if not found then
    raise exception 'Card not found or unauthorized';
  end if;

  -- Calculate new SRS parameters
  if p_correct then
    -- Successful recall
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
    else  -- review
      v_new_stage := 'review';
      v_new_interval := (v_card.srs_interval_days * v_card.srs_ease_factor)::int;
      v_new_ease := least(2.8, v_card.srs_ease_factor + 0.1);
    end if;
  else
    -- Failed recall
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

  -- Update card
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

-- Comments
comment on function public.save_game_review is 'Atomically save or update a game with full review data';
comment on function public.save_position is 'Save a single chess position with analysis';
comment on function public.get_user_stats is 'Get aggregated performance statistics for user';
comment on function public.get_srs_due_cards is 'Get training cards due for review';
comment on function public.update_card_srs is 'Update SRS state after drill attempt';

