-- Migration 020: Backfill Moves Raw Function
-- Extracts moves from game_review->ply_records JSONB and populates normalized tables
-- Can be run for all users or a specific user

create or replace function public.backfill_moves_raw(p_user_id uuid default null)
returns table (games_processed bigint, moves_inserted bigint)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_game record;
  v_ply jsonb;
  v_move_id uuid;
  v_tag_name text;
  v_tag_id int;
  v_games_processed bigint := 0;
  v_moves_inserted bigint := 0;
  v_engine jsonb;
  v_analyse jsonb;
  v_tags jsonb;
begin
  -- Process all games or user-specific
  for v_game in 
    select id, user_id, game_review
    from public.games
    where (p_user_id is null or user_id = p_user_id)
      and game_review is not null
      and game_review ? 'ply_records'
      and jsonb_typeof(game_review->'ply_records') = 'array'
      and not exists (
        select 1 from public.moves_raw where game_id = games.id limit 1
      )
    order by analyzed_at desc nulls last, created_at desc
  loop
    -- Extract each ply record
    for v_ply in select * from jsonb_array_elements(v_game.game_review->'ply_records')
    loop
      -- Extract nested JSONB objects
      v_engine := v_ply->'engine';
      v_analyse := v_ply->'analyse';
      
      -- Skip if required fields are missing
      if v_ply->>'ply' is null or v_ply->>'fen_before' is null or v_ply->>'san' is null then
        continue;
      end if;
      
      -- Calculate deltas (handle nulls)
      declare
        v_eval_before int := (v_engine->>'eval_before_cp')::int;
        v_eval_after int := (v_engine->>'played_eval_after_cp')::int;
        v_best_eval_after int := (v_engine->>'best_eval_after_cp')::int;
        v_cp_loss int := coalesce((v_ply->>'cp_loss')::int, 0);
        v_eval_delta int;
        v_best_delta int;
        v_delta_vs_best int;
      begin
        -- Calculate deltas, handling nulls
        v_eval_delta := case 
          when v_eval_before is not null and v_eval_after is not null 
          then v_eval_after - v_eval_before 
          else null 
        end;
        
        v_best_delta := case 
          when v_eval_before is not null and v_best_eval_after is not null 
          then v_best_eval_after - v_eval_before 
          else null 
        end;
        
        v_delta_vs_best := coalesce(v_cp_loss, 
          case 
            when v_eval_after is not null and v_best_eval_after is not null 
            then v_eval_after - v_best_eval_after 
            else null 
          end
        );
        
        -- Insert into moves_raw
        insert into public.moves_raw (
          game_id, user_id, move_number, ply, side_moved,
          fen_before, fen_after, phase,
          move_san, move_uci,
          eval_before_cp, eval_after_cp, best_eval_after_cp,
          best_move_san, best_move_uci,
          accuracy, cp_loss, eval_delta_cp, best_delta_cp, delta_vs_best_cp,
          is_mistake, is_blunder, is_inaccuracy,
          category, time_spent_s
        ) values (
          v_game.id, v_game.user_id,
          (v_ply->>'ply')::int, (v_ply->>'ply')::int,
          coalesce((v_ply->>'side_moved')::text, 
            case when (v_ply->>'ply')::int % 2 = 1 then 'white' else 'black' end),
          v_ply->>'fen_before', 
          v_ply->>'fen_after',
          (v_ply->>'phase')::text,
          v_ply->>'san', 
          v_ply->>'uci',
          v_eval_before,
          v_eval_after,
          v_best_eval_after,
          v_engine->>'best_move_san',
          v_engine->>'best_move_uci',
          coalesce((v_ply->>'accuracy_pct')::float, null),
          v_cp_loss,
          v_eval_delta,
          v_best_delta,
          v_delta_vs_best,
          coalesce((v_ply->>'category')::text = 'mistake', false),
          coalesce((v_ply->>'category')::text = 'blunder', false),
          coalesce((v_ply->>'category')::text = 'inaccuracy', false),
          (v_ply->>'category')::text,
          (v_ply->>'time_spent_s')::numeric
        ) returning id into v_move_id;
        
        -- Extract and normalize tags
        if v_analyse is not null and v_analyse ? 'tags' then
          v_tags := v_analyse->'tags';
          
          -- Handle both array of strings and array of objects
          if jsonb_typeof(v_tags) = 'array' then
            for v_tag_name in 
              select jsonb_array_elements_text(v_tags)
            loop
              if v_tag_name is not null and length(trim(v_tag_name)) > 0 then
                -- Get or create tag
                insert into public.tags (name) values (trim(v_tag_name))
                on conflict (name) do nothing;
                
                select id into v_tag_id from public.tags where name = trim(v_tag_name);
                
                -- Link move to tag
                if v_tag_id is not null then
                  insert into public.move_tags (move_id, tag_id)
                  values (v_move_id, v_tag_id)
                  on conflict do nothing;
                end if;
              end if;
            end loop;
          end if;
        end if;
        
        -- Populate move_metrics
        declare
          v_category text := (v_ply->>'category')::text;
          v_is_non_mistake boolean := not (v_category in ('blunder','mistake','inaccuracy'));
        begin
          insert into public.move_metrics (
            move_id, eval_delta_cp, best_delta_cp, delta_vs_best_cp,
            accuracy, phase, is_non_mistake
          ) values (
            v_move_id,
            v_eval_delta,
            v_best_delta,
            v_delta_vs_best,
            coalesce((v_ply->>'accuracy_pct')::float, null),
            (v_ply->>'phase')::text,
            v_is_non_mistake
          ) on conflict (move_id) do update set
            eval_delta_cp = excluded.eval_delta_cp,
            best_delta_cp = excluded.best_delta_cp,
            delta_vs_best_cp = excluded.delta_vs_best_cp,
            accuracy = excluded.accuracy,
            phase = excluded.phase,
            is_non_mistake = excluded.is_non_mistake;
        end;
        
        v_moves_inserted := v_moves_inserted + 1;
      end;
    end loop;
    
    v_games_processed := v_games_processed + 1;
    
    -- Log progress every 10 games
    if v_games_processed % 10 = 0 then
      raise notice 'Processed % games, inserted % moves', v_games_processed, v_moves_inserted;
    end if;
  end loop;
  
  return query select v_games_processed, v_moves_inserted;
end;
$$;

-- Comments
comment on function public.backfill_moves_raw is 'Extracts moves from game_review JSONB and populates normalized tables. Call with user_id or null for all users.';
