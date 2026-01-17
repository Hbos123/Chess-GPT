-- Migration 022: Refresh Analytics Views
-- Function to refresh all materialized views
-- Can be called manually or via cron job

create or replace function public.refresh_analytics_views()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  -- Refresh all materialized views concurrently (non-blocking)
  -- Note: CONCURRENTLY requires unique indexes (which we created)
  refresh materialized view concurrently tag_accuracy;
  refresh materialized view concurrently tag_accuracy_over_time;
  refresh materialized view concurrently tag_frequency;
  refresh materialized view concurrently tag_delta_vs_best;
  refresh materialized view concurrently tag_delta_non_mistake;
  refresh materialized view concurrently phase_accuracy;
  refresh materialized view concurrently tag_phase_accuracy;
  
  raise notice 'All analytics views refreshed successfully';
exception
  when others then
    raise warning 'Error refreshing views: %', sqlerrm;
    -- Try non-concurrent refresh as fallback (blocks reads but more reliable)
    refresh materialized view tag_accuracy;
    refresh materialized view tag_accuracy_over_time;
    refresh materialized view tag_frequency;
    refresh materialized view tag_delta_vs_best;
    refresh materialized view tag_delta_non_mistake;
    refresh materialized view phase_accuracy;
    refresh materialized view tag_phase_accuracy;
    raise notice 'Views refreshed using non-concurrent method';
end;
$$;

-- Comments
comment on function public.refresh_analytics_views is 'Refreshes all analytics materialized views. Use CONCURRENTLY when possible, falls back to blocking refresh.';

