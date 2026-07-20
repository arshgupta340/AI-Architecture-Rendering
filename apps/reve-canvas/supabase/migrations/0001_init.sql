create extension if not exists pgcrypto;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  created_at timestamptz not null default now()
);

create table public.projects (
  id uuid primary key default gen_random_uuid(),
  owner uuid not null references auth.users (id) on delete cascade,
  name text not null,
  source_image_path text not null,
  source_width integer not null check (source_width > 0),
  source_height integer not null check (source_height > 0),
  created_at timestamptz not null default now()
);

create table public.snapshots (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  image_path text not null,
  layout jsonb not null,
  parent_id uuid references public.snapshots (id) on delete restrict,
  produced_by_edit_id uuid,
  drift_score real,
  created_at timestamptz not null default now()
);

create table public.layers (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  region_key text not null,
  name text not null,
  semantic text not null,
  type text not null,
  bbox jsonb not null,
  prompt text not null,
  is_building boolean not null default false,
  sort_order integer not null default 0,
  unique (project_id, region_key)
);

create table public.edits (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects (id) on delete cascade,
  layer_id uuid references public.layers (id) on delete set null,
  kind text not null,
  material_id text not null,
  facet text,
  base_snapshot_id uuid not null references public.snapshots (id) on delete restrict,
  result_snapshot_id uuid references public.snapshots (id) on delete restrict,
  status text not null check (status in ('queued', 'running', 'completed', 'failed')),
  credits_cost integer not null check (credits_cost >= 0),
  created_at timestamptz not null default now()
);

alter table public.snapshots
  add constraint snapshots_produced_by_edit_id_fkey
  foreign key (produced_by_edit_id) references public.edits (id) on delete restrict;

create table public.credit_ledger (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  delta integer not null,
  reason text not null,
  edit_id uuid references public.edits (id) on delete set null,
  balance_after integer not null,
  created_at timestamptz not null default now()
);

create index projects_owner_created_at_idx on public.projects (owner, created_at desc);
create index snapshots_project_created_at_idx on public.snapshots (project_id, created_at desc);
create index layers_project_sort_order_idx on public.layers (project_id, sort_order);
create index edits_project_created_at_idx on public.edits (project_id, created_at desc);
create index credit_ledger_user_created_at_idx on public.credit_ledger (user_id, created_at desc);

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, coalesce(new.email, ''))
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

create or replace function public.debit_credits(amount integer, reason text)
returns integer
language plpgsql
security definer set search_path = public
as $$
declare
  current_balance integer;
  next_balance integer;
begin
  if amount <= 0 then
    raise exception 'amount must be positive';
  end if;

  select balance_after into current_balance
  from public.credit_ledger
  where user_id = auth.uid()
  order by created_at desc, id desc
  limit 1
  for update;

  current_balance := coalesce(current_balance, 0);
  if current_balance < amount then
    raise exception 'insufficient credits';
  end if;

  next_balance := current_balance - amount;
  insert into public.credit_ledger (user_id, delta, reason, balance_after)
  values (auth.uid(), -amount, reason, next_balance);
  return next_balance;
end;
$$;

alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.snapshots enable row level security;
alter table public.layers enable row level security;
alter table public.edits enable row level security;
alter table public.credit_ledger enable row level security;

create policy "profiles are private" on public.profiles for select using (id = auth.uid());
create policy "profiles update themselves" on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());

create policy "project owners read" on public.projects for select using (owner = auth.uid());
create policy "project owners create" on public.projects for insert with check (owner = auth.uid());
create policy "project owners update" on public.projects for update using (owner = auth.uid()) with check (owner = auth.uid());
create policy "project owners delete" on public.projects for delete using (owner = auth.uid());

create policy "snapshot owners read" on public.snapshots for select using (
  exists (select 1 from public.projects where projects.id = snapshots.project_id and projects.owner = auth.uid())
);
create policy "snapshot owners append" on public.snapshots for insert with check (
  exists (select 1 from public.projects where projects.id = snapshots.project_id and projects.owner = auth.uid())
);

create policy "layer owners read" on public.layers for select using (
  exists (select 1 from public.projects where projects.id = layers.project_id and projects.owner = auth.uid())
);
create policy "layer owners create" on public.layers for insert with check (
  exists (select 1 from public.projects where projects.id = layers.project_id and projects.owner = auth.uid())
);
create policy "layer owners update" on public.layers for update using (
  exists (select 1 from public.projects where projects.id = layers.project_id and projects.owner = auth.uid())
) with check (
  exists (select 1 from public.projects where projects.id = layers.project_id and projects.owner = auth.uid())
);
create policy "layer owners delete" on public.layers for delete using (
  exists (select 1 from public.projects where projects.id = layers.project_id and projects.owner = auth.uid())
);

create policy "edit owners read" on public.edits for select using (
  exists (select 1 from public.projects where projects.id = edits.project_id and projects.owner = auth.uid())
);
create policy "edit owners create" on public.edits for insert with check (
  exists (select 1 from public.projects where projects.id = edits.project_id and projects.owner = auth.uid())
);
create policy "edit owners update" on public.edits for update using (
  exists (select 1 from public.projects where projects.id = edits.project_id and projects.owner = auth.uid())
) with check (
  exists (select 1 from public.projects where projects.id = edits.project_id and projects.owner = auth.uid())
);

create policy "ledger owners read" on public.credit_ledger for select using (user_id = auth.uid());

revoke insert, update, delete on public.credit_ledger from anon, authenticated;
grant execute on function public.debit_credits(integer, text) to authenticated;

insert into storage.buckets (id, name, public)
values ('images', 'images', false)
on conflict (id) do nothing;

create policy "image owners read" on storage.objects for select using (
  bucket_id = 'images' and (storage.foldername(name))[1] = auth.uid()::text
);
create policy "image owners upload" on storage.objects for insert with check (
  bucket_id = 'images' and (storage.foldername(name))[1] = auth.uid()::text
);
create policy "image owners update" on storage.objects for update using (
  bucket_id = 'images' and (storage.foldername(name))[1] = auth.uid()::text
) with check (
  bucket_id = 'images' and (storage.foldername(name))[1] = auth.uid()::text
);
create policy "image owners delete" on storage.objects for delete using (
  bucket_id = 'images' and (storage.foldername(name))[1] = auth.uid()::text
);
