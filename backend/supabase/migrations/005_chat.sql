-- Chat history (sessions and messages)

-- Chat sessions (threads/conversations)
create table public.chat_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  title text,
  mode text check (mode in ('PLAY','ANALYZE','TACTICS','DISCUSS','LESSON','REVIEW')) default 'DISCUSS',
  
  -- Optional links to game or position being discussed
  linked_game_id uuid references public.games(id) on delete set null,
  linked_position_id uuid references public.positions(id) on delete set null,
  
  -- Session metadata
  message_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  last_message_at timestamptz default now()
);

-- Indexes
create index chat_sessions_user_id_idx on public.chat_sessions (user_id);
create index chat_sessions_user_updated_idx on public.chat_sessions (user_id, last_message_at desc);
create index chat_sessions_linked_game_idx on public.chat_sessions (linked_game_id) where linked_game_id is not null;

-- Auto-update timestamp
create trigger set_chat_sessions_updated_at
  before update on public.chat_sessions
  for each row execute procedure extensions.moddatetime(updated_at);

-- RLS policies
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
  
  -- Message data
  role text check (role in ('user','assistant','system')) not null,
  content text not null,
  
  -- Optional structured data
  tool_name text,              -- Name of tool called (if any)
  tool_input jsonb,            -- Tool input parameters
  tool_output jsonb,           -- Tool output
  citations jsonb,             -- References to positions, analysis, etc.
  
  -- Metadata
  model text,                  -- GPT model used
  tokens_used int,
  
  created_at timestamptz default now()
);

-- Indexes
create index chat_messages_session_idx on public.chat_messages (session_id, created_at);
create index chat_messages_user_idx on public.chat_messages (user_id);
create index chat_messages_role_idx on public.chat_messages (session_id, role);

-- RLS policies
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

-- Comments
comment on table public.chat_sessions is 'Chat conversation threads';
comment on table public.chat_messages is 'Individual messages within chat sessions';
comment on column public.chat_messages.tool_name is 'Tool/endpoint called during this message';
comment on column public.chat_messages.citations is 'References to games, positions, or analysis';

