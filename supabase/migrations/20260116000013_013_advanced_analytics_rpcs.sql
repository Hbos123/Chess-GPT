-- Migration 013: Advanced Profile Analytics RPCs
-- Moves computation of lifetime stats, patterns, and strength profile to database-side SQL

-- 1. Lifetime Stats
create or replace function public.get_lifetime_stats_v2(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_stats jsonb;
begin
  with game_data as (
    select 
      game_date,
      user_rating,
      result,
      time_control,
      time_category
    from public.games
    where user_id = p_user_id
      and archived_at is null
      and (review_type = 'full' or review_type is null)
    order by game_date asc
  ),
  rating_history as (
    select jsonb_agg(jsonb_build_object(
      'date', substring(game_date::text from 1 for 10),
      'rating', user_rating
    )) as history
    from game_data
    where user_rating is not null
  ),
  win_rates as (
    select jsonb_object_agg(tc, stats) as rates
    from (
      select 
        coalesce(time_control, 'unknown') as tc,
        jsonb_build_object(
          'total', count(*),
          'wins', count(*) filter (where result = 'win'),
          'losses', count(*) filter (where result = 'loss'),
          'draws', count(*) filter (where result = 'draw'),
          'win_rate', round((count(*) filter (where result = 'win')::numeric / nullif(count(*), 0)) * 100, 1)
        ) as stats
      from game_data
      group by time_control
    ) t
  ),
  improvement as (
    with ranked as (
      select user_rating, row_number() over (order by game_date desc) as rn_desc, row_number() over (order by game_date asc) as rn_asc
      from game_data
      where user_rating is not null
    ),
    recent_avg as (select avg(user_rating) as val from ranked where rn_desc <= 5),
    oldest_avg as (select avg(user_rating) as val from ranked where rn_asc <= 5)
    select jsonb_build_object(
      'rating_delta', round((r.val - o.val)::numeric, 1),
      'trend', case 
        when (r.val - o.val) > 10 then 'improving'
        when (r.val - o.val) < -10 then 'declining'
        else 'stable'
      end
    )
    from recent_avg r, oldest_avg o
  )
  select jsonb_build_object(
    'total_games_analyzed', (select count(*) from game_data),
    'rating_history', coalesce((select history from rating_history), '[]'::jsonb),
    'win_rates', coalesce((select rates from win_rates), '{}'::jsonb),
    'improvement_velocity', (select * from improvement),
    'peak_rating', (select max(user_rating) from game_data)
  ) into v_stats;

  return v_stats;
end;
$$;

-- 2. Advanced Patterns
create or replace function public.get_advanced_patterns_v2(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_patterns jsonb;
begin
  with game_data as (
    select 
      opening_name,
      opening_eco,
      result,
      user_rating,
      opponent_rating
    from public.games
    where user_id = p_user_id
      and archived_at is null
      and (review_type = 'full' or review_type is null)
    limit 50
  ),
  openings as (
    select jsonb_agg(t) as repertoire from (
      select 
        opening_name as name,
        opening_eco as eco,
        count(*) as frequency,
        round((count(*) filter (where result = 'win')::numeric / count(*)) * 100, 1) as win_rate
      from game_data
      where opening_name is not null
      group by opening_name, opening_eco
      order by count(*) desc
      limit 5
    ) t
  ),
  opponents as (
    select jsonb_build_object(
      'win_rate_vs_higher', round(avg(case when result = 'win' then 100 when result = 'draw' then 50 else 0 end) filter (where opponent_rating > user_rating + 50), 1),
      'win_rate_vs_lower', round(avg(case when result = 'win' then 100 when result = 'draw' then 50 else 0 end) filter (where opponent_rating < user_rating - 50), 1)
    ) as analysis
    from game_data
    where user_rating is not null and opponent_rating is not null
  )
  select jsonb_build_object(
    'opening_repertoire', coalesce((select repertoire from openings), '[]'::jsonb),
    'opponent_analysis', (select analysis from opponents)
  ) into v_patterns;

  return v_patterns;
end;
$$;

-- 3. Strength Profile
create or replace function public.get_strength_profile_v2(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_profile jsonb;
begin
  with game_data as (
    select 
      accuracy_opening,
      accuracy_middlegame,
      accuracy_endgame,
      game_review
    from public.games
    where user_id = p_user_id
      and archived_at is null
      and (review_type = 'full' or review_type is null)
    limit 50
  ),
  phases as (
    select jsonb_build_object(
      'opening', round(avg(accuracy_opening)::numeric, 1),
      'middlegame', round(avg(accuracy_middlegame)::numeric, 1),
      'endgame', round(avg(accuracy_endgame)::numeric, 1)
    ) as proficiency
    from game_data
  ),
  ply_data as (
    select 
      (record->>'accuracy_pct')::numeric as accuracy,
      (record->>'eval_delta')::numeric as eval_delta,
      (record->>'san') as san
    from game_data,
    jsonb_array_elements(game_review->'ply_records') as record
    where game_review ? 'ply_records'
  ),
  skill_types as (
    select jsonb_build_object(
      'tactical_accuracy', round(avg(accuracy) filter (where abs(eval_delta) > 150), 1),
      'positional_accuracy', round(avg(accuracy) filter (where abs(eval_delta) <= 150), 1)
    ) as skills
    from ply_data
  ),
  piece_acc as (
    select jsonb_object_agg(piece, avg_acc) as performance
    from (
      select piece, round(avg(accuracy), 1) as avg_acc
      from (
        select 
          case 
            when san ~ '^K' then 'King'
            when san ~ '^Q' then 'Queen'
            when san ~ '^R' then 'Rook'
            when san ~ '^B' then 'Bishop'
            when san ~ '^N' then 'Knight'
            else 'Pawn'
          end as piece,
          accuracy
        from ply_data
        where san is not null and accuracy is not null
      ) p2
      group by piece
    ) p3
  )
  select jsonb_build_object(
    'phase_proficiency', (select proficiency from phases),
    'tactical_vs_positional', (select skills from skill_types),
    'piece_performance', coalesce((select performance from piece_acc), '{}'::jsonb)
  ) into v_profile;

  return v_profile;
end;
$$;

-- Comments
comment on function public.get_lifetime_stats_v2 is 'Computes lifetime performance stats directly in SQL';
comment on function public.get_advanced_patterns_v2 is 'Identifies playing patterns and repertoire in SQL';
comment on function public.get_strength_profile_v2 is 'Calculates strength/weakness profile by analyzing game phases and ply-level data in SQL';
