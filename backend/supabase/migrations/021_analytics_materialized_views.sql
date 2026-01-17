-- Migration 021: Analytics Materialized Views
-- Precomputed views for all common analytics queries
-- These views are refreshed periodically, not on every query

-- A) Average accuracy per tag
drop materialized view if exists public.tag_accuracy;
create materialized view public.tag_accuracy as
select
  t.name as tag,
  avg(mm.accuracy) as avg_accuracy,
  count(*) as sample_size
from move_tags mt
join tags t on t.id = mt.tag_id
join move_metrics mm on mm.move_id = mt.move_id
where mm.accuracy is not null
group by t.name;

create unique index tag_accuracy_tag_idx on public.tag_accuracy (tag);

-- B) Average accuracy per tag over time
drop materialized view if exists public.tag_accuracy_over_time;
create materialized view public.tag_accuracy_over_time as
select
  t.name as tag,
  date_trunc('week', mr.created_at) as week,
  avg(mm.accuracy) as avg_accuracy,
  count(*) as sample_size
from move_tags mt
join tags t on t.id = mt.tag_id
join moves_raw mr on mr.id = mt.move_id
join move_metrics mm on mm.move_id = mt.move_id
where mm.accuracy is not null
group by t.name, week;

create unique index tag_accuracy_over_time_idx on public.tag_accuracy_over_time (tag, week);

-- C) Tag frequency
drop materialized view if exists public.tag_frequency;
create materialized view public.tag_frequency as
select
  t.name as tag,
  count(*) as occurrences
from move_tags mt
join tags t on t.id = mt.tag_id
group by t.name;

create unique index tag_frequency_tag_idx on public.tag_frequency (tag);

-- D) Tag delta vs best move
drop materialized view if exists public.tag_delta_vs_best;
create materialized view public.tag_delta_vs_best as
select
  t.name as tag,
  avg(mm.delta_vs_best_cp) as avg_delta_vs_best,
  avg(mm.eval_delta_cp) as avg_played_delta,
  avg(mm.best_delta_cp) as avg_best_delta,
  count(*) as sample_size
from move_tags mt
join tags t on t.id = mt.tag_id
join move_metrics mm on mm.move_id = mt.move_id
where mm.delta_vs_best_cp is not null
group by t.name;

create unique index tag_delta_vs_best_tag_idx on public.tag_delta_vs_best (tag);

-- E) Tag deltas only in non-mistake positions
drop materialized view if exists public.tag_delta_non_mistake;
create materialized view public.tag_delta_non_mistake as
select
  t.name as tag,
  avg(mm.delta_vs_best_cp) as avg_delta_vs_best,
  count(*) as sample_size
from move_tags mt
join tags t on t.id = mt.tag_id
join move_metrics mm on mm.move_id = mt.move_id
where mm.is_non_mistake = true
  and mm.delta_vs_best_cp is not null
group by t.name;

create unique index tag_delta_non_mistake_tag_idx on public.tag_delta_non_mistake (tag);

-- F) Accuracy by phase
drop materialized view if exists public.phase_accuracy;
create materialized view public.phase_accuracy as
select
  phase,
  avg(accuracy) as avg_accuracy,
  count(*) as sample_size
from move_metrics
where phase is not null
  and accuracy is not null
group by phase;

create unique index phase_accuracy_phase_idx on public.phase_accuracy (phase);

-- G) Accuracy by phase and tag
drop materialized view if exists public.tag_phase_accuracy;
create materialized view public.tag_phase_accuracy as
select
  t.name as tag,
  mm.phase,
  avg(mm.accuracy) as avg_accuracy,
  count(*) as sample_size
from move_tags mt
join tags t on t.id = mt.tag_id
join move_metrics mm on mm.move_id = mt.move_id
where mm.phase is not null
  and mm.accuracy is not null
group by t.name, mm.phase;

create unique index tag_phase_accuracy_idx on public.tag_phase_accuracy (tag, phase);

-- Comments
comment on materialized view public.tag_accuracy is 'Average accuracy per tag across all moves';
comment on materialized view public.tag_accuracy_over_time is 'Average accuracy per tag grouped by week';
comment on materialized view public.tag_frequency is 'Frequency count of each tag';
comment on materialized view public.tag_delta_vs_best is 'Tag performance vs best move (negative = underperforms, positive = strong)';
comment on materialized view public.tag_delta_non_mistake is 'Tag deltas only for non-mistake positions (instructional value)';
comment on materialized view public.phase_accuracy is 'Average accuracy by game phase';
comment on materialized view public.tag_phase_accuracy is 'Average accuracy by tag and phase (heatmap data)';

