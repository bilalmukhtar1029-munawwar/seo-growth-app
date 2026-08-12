-- Run this in the Supabase SQL editor to set up the core tables.
-- Supabase's built-in `auth.users` table handles login/signup already —
-- these tables reference it via user_id.

create table if not exists connected_accounts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    platform text not null check (platform in ('instagram', 'facebook', 'linkedin', 'twitter', 'google_search_console')),
    access_token text not null,
    refresh_token text,
    account_label text,
    connected_at timestamptz default now(),
    unique (user_id, platform)
);

create table if not exists seo_reports (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    seo_score int,
    findings jsonb,
    recommended_actions jsonb,
    created_at timestamptz default now()
);

create table if not exists content_drafts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) on delete cascade,
    content_type text not null check (content_type in ('blog', 'landing_page', 'ad', 'video_script', 'linkedin_post')),
    source text not null check (source in ('manual', 'auto')),
    product_name text,
    payload jsonb not null,
    status text default 'draft' check (status in ('draft', 'approved', 'published')),
    created_at timestamptz default now()
);

-- Snapshot table written by the Instagram scan (core/tasks.py). One row per
-- user, updated in place each scan.
create table if not exists instagram_snapshots (
    user_id uuid primary key references auth.users(id) on delete cascade,
    posts_per_week numeric,
    avg_engagement numeric,
    last_post_days_ago int,
    recent_posts jsonb,
    scanned_at timestamptz default now()
);

-- Row Level Security: each user only sees their own rows.
alter table connected_accounts enable row level security;
alter table seo_reports enable row level security;
alter table content_drafts enable row level security;
alter table instagram_snapshots enable row level security;

create policy "Users manage their own connected accounts"
    on connected_accounts for all
    using (auth.uid() = user_id);

create policy "Users manage their own seo reports"
    on seo_reports for all
    using (auth.uid() = user_id);

create policy "Users manage their own content drafts"
    on content_drafts for all
    using (auth.uid() = user_id);

-- The feed query filters on (user_id, source, status) — make it fast.
create index if not exists content_drafts_user_source_status_idx
    on content_drafts (user_id, source, status);
create index if not exists connected_accounts_user_idx
    on connected_accounts (user_id);

-- Snapshot is read by the dashboard with the user's own JWT.
create policy "Users read their own instagram snapshot"
    on instagram_snapshots for select
    using (auth.uid() = user_id);

-- Migration for databases created before the LinkedIn post suggestions feature:
-- the check constraint above already includes 'linkedin_post' for fresh
-- installs; this updates existing databases without recreating the table.
alter table content_drafts drop constraint if exists content_drafts_content_type_check;
alter table content_drafts add constraint content_drafts_content_type_check
    check (content_type in ('blog', 'landing_page', 'ad', 'video_script', 'linkedin_post'));
