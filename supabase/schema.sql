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
    content_type text not null check (content_type in ('blog', 'landing_page', 'ad', 'video_script')),
    source text not null check (source in ('manual', 'auto')),
    product_name text,
    payload jsonb not null,
    status text default 'draft' check (status in ('draft', 'approved', 'published')),
    created_at timestamptz default now()
);

-- Row Level Security: each user only sees their own rows.
alter table connected_accounts enable row level security;
alter table seo_reports enable row level security;
alter table content_drafts enable row level security;

create policy "Users manage their own connected accounts"
    on connected_accounts for all
    using (auth.uid() = user_id);

create policy "Users manage their own seo reports"
    on seo_reports for all
    using (auth.uid() = user_id);

create policy "Users manage their own content drafts"
    on content_drafts for all
    using (auth.uid() = user_id);
