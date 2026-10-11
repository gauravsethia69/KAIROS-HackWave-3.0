-- Read-only fictional dataset shared with signed-in users. Never put real client records here.
create table public.clients (
  id text primary key check (id in ('acme','nova')), name text not null, sector text not null,
  contact text not null, email text not null, owner text not null, plan text not null,
  seats integer not null check (seats >= 0), health text not null
);
create table public.meetings (
  id text primary key, client_id text not null references public.clients(id), title text not null,
  date date not null, summary text not null, attendees text not null, upcoming boolean not null default false
);
create table public.communications (
  id text primary key, client_id text not null references public.clients(id), date date not null,
  author text not null, channel text not null, message text not null
);
create table public.product_usage (
  id text primary key, client_id text not null references public.clients(id), date date not null,
  active_users integer not null check (active_users >= 0), sessions integer not null check (sessions >= 0),
  errors integer not null check (errors >= 0), unique(client_id,date)
);
create table public.projects (
  id text primary key, client_id text not null references public.clients(id), name text not null,
  owner text not null, progress integer not null check (progress between 0 and 100),
  expected integer not null check (expected between 0 and 100), due_date date not null, status text not null,
  unique (id, client_id)
);
create table public.tasks (
  id text primary key, client_id text not null references public.clients(id), project_id text not null,
  title text not null, owner text not null, due_date date not null, status text not null,
  priority text not null, foreign key (project_id,client_id) references public.projects(id,client_id)
);
create table public.issues (
  id text primary key, client_id text not null references public.clients(id), project_id text not null,
  title text not null, date date not null, status text not null, severity text not null,
  owner text not null, detail text not null,
  foreign key (project_id,client_id) references public.projects(id,client_id)
);
create table public.workspace_sessions (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade,
  title text not null check (length(title) between 1 and 140), plan jsonb not null check (jsonb_typeof(plan) = 'object' and octet_length(plan::text) <= 24000),
  created_at timestamptz not null default now()
);
create index meetings_client_date on public.meetings(client_id,date);
create index communications_client_date on public.communications(client_id,date);
create index projects_client_due on public.projects(client_id,due_date);
create index tasks_client_due on public.tasks(client_id,due_date);
create index tasks_project on public.tasks(project_id,client_id);
create index issues_client_status on public.issues(client_id,status);
create index issues_project on public.issues(project_id,client_id);
create index sessions_user_created on public.workspace_sessions(user_id,created_at desc);

grant usage on schema public to authenticated;
do $$ declare t text; begin
  foreach t in array array['clients','meetings','communications','product_usage','projects','tasks','issues'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('revoke all on public.%I from anon, authenticated',t);
    execute format('grant select on public.%I to authenticated',t);
    execute format('create policy demo_read on public.%I for select to authenticated using (true)',t);
  end loop;
end $$;
alter table public.workspace_sessions enable row level security;
revoke all on public.workspace_sessions from anon, authenticated;
grant select, insert, update, delete on public.workspace_sessions to authenticated;
create policy own_workspace_select on public.workspace_sessions for select to authenticated using ((select auth.uid()) = user_id);
create policy own_workspace_insert on public.workspace_sessions for insert to authenticated with check ((select auth.uid()) = user_id);
create policy own_workspace_update on public.workspace_sessions for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy own_workspace_delete on public.workspace_sessions for delete to authenticated using ((select auth.uid()) = user_id);

-- Maximum 10 attempts per minute per authenticated account, atomic across Edge instances.
create table public.ai_request_limits (user_id uuid primary key references auth.users(id) on delete cascade, window_start timestamptz not null, requests integer not null);
alter table public.ai_request_limits enable row level security;
revoke all on public.ai_request_limits from anon, authenticated;
create or replace function public.claim_ai_request() returns boolean
language plpgsql security definer set search_path = '' as $$
declare allowed boolean; current_user_id uuid := auth.uid();
begin
  if current_user_id is null then return false; end if;
  insert into public.ai_request_limits as limits (user_id, window_start, requests)
    values (current_user_id, now(), 1)
    on conflict (user_id) do update set
      requests = case when limits.window_start < now() - interval '1 minute' then 1 else limits.requests + 1 end,
      window_start = case when limits.window_start < now() - interval '1 minute' then now() else limits.window_start end
    where limits.window_start < now() - interval '1 minute' or limits.requests < 10
    returning true into allowed;
  return coalesce(allowed,false);
end $$;
revoke all on function public.claim_ai_request() from public, anon;
grant execute on function public.claim_ai_request() to authenticated;
