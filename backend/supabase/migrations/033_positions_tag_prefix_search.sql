-- Migration 033: Tag prefix search RPCs for aggregated drill buckets
-- Supports matching tags like "Piece Overworked" against arrays containing
-- "Piece Overworked D4", "Piece Overworked F8", etc.

create or replace function public.count_positions_by_tag_prefix_v1(
  p_user_id uuid,
  p_transition text,
  p_prefix text,
  p_error_side text default null,
  p_min_cp_loss numeric default null
)
returns table (count bigint)
language sql
stable
as $$
  with base as (
    select *
    from public.positions
    where user_id = p_user_id
      and (p_error_side is null or (p_error_side = '__null__' and error_side is null) or (p_error_side <> '__null__' and error_side = p_error_side))
      and (p_min_cp_loss is null or cp_loss >= p_min_cp_loss)
      and (error_category in ('blunder','mistake'))
  ),
  matched as (
    select id
    from base b
    where
      case lower(p_transition)
        when 'gained' then exists (select 1 from unnest(coalesce(b.tags_gained, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
        when 'lost' then exists (select 1 from unnest(coalesce(b.tags_lost, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
        when 'missed' then (
          exists (select 1 from unnest(coalesce(b.tags_after_best, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
          and not exists (select 1 from unnest(coalesce(b.tags_after_played, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
        )
        else false
      end
  )
  select count(*)::bigint as count from matched;
$$;


create or replace function public.search_positions_by_tag_prefix_v1(
  p_user_id uuid,
  p_transition text,
  p_prefix text,
  p_error_side text default null,
  p_min_cp_loss numeric default null,
  p_limit int default 20,
  p_prioritize_fresh boolean default true
)
returns setof public.positions
language sql
stable
as $$
  with base as (
    select *
    from public.positions
    where user_id = p_user_id
      and (p_error_side is null or (p_error_side = '__null__' and error_side is null) or (p_error_side <> '__null__' and error_side = p_error_side))
      and (p_min_cp_loss is null or cp_loss >= p_min_cp_loss)
      and (error_category in ('blunder','mistake'))
  ),
  matched as (
    select *
    from base b
    where
      case lower(p_transition)
        when 'gained' then exists (select 1 from unnest(coalesce(b.tags_gained, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
        when 'lost' then exists (select 1 from unnest(coalesce(b.tags_lost, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
        when 'missed' then (
          exists (select 1 from unnest(coalesce(b.tags_after_best, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
          and not exists (select 1 from unnest(coalesce(b.tags_after_played, '{}'::text[])) t where lower(t) like lower(p_prefix) || '%')
        )
        else false
      end
  )
  select *
  from matched
  order by
    case when p_prioritize_fresh then (last_used_in_drill is not null) else false end asc,
    case when p_prioritize_fresh then last_used_in_drill else null end asc nulls first,
    cp_loss desc
  limit greatest(1, least(p_limit, 50));
$$;

