"""
Module 2: the "auto-generator" from your original plan — FREE VERSION.

Originally this ran on a schedule via Celery, which needs a paid background
worker (~$7+/mo on most hosts). Instead, this is a plain function that a free
external cron service (like cron-job.org) triggers by calling
POST /internal/run-weekly-scan once a week — see routers/internal.py.
Same end result, $0 cost.

For each user with a connected Search Console account, it:
  1. Pulls their last 30 days of Search Console data
  2. Asks the AI to flag specific gaps (e.g. "high impressions, low clicks on
     page X" — a classic "ranking but not converting" signal)
  3. Auto-drafts one piece of content per flagged gap and saves it to
     `content_drafts` with source='auto', status='draft'

Nothing gets published automatically — these land in the user's "Auto-Suggested
Content Feed" (query content_drafts where source='auto' and status='draft') for
them to approve or edit, matching Part 2 of your original plan.

Instagram scanning (scan_all_instagram_users / _scan_one_instagram_user) works
the same way: pulls recent posts + engagement via the Meta Graph API and saves
a rollup snapshot to `instagram_snapshots`, which the dashboard's SEO Snapshot
card reads from instead of showing sample data.

Per-user variants (scan_content_gaps_for_user / scan_linkedin_suggestions_for_user)
exist so the frontend's "Run scan now" button (POST /feed/scan) can trigger a
scan for the logged-in user instantly instead of waiting for the weekly cron.

LinkedIn suggestions need no Marketing API review: they repurpose content the
user already approved (from the generator or a previous scan) into ready-to-post
LinkedIn updates, so the auto-suggestion feed fills for LinkedIn-connected users
too.
"""
from datetime import date, timedelta

from core.auth import get_admin_client
from core.ai_client import generate_json
from core.instagram_client import (
    fetch_ig_media,
    fetch_ig_media_insights,
    compute_posting_stats,
)

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def scan_all_users_for_content_gaps() -> list[dict]:
    db = get_admin_client()
    accounts = (
        db.table("connected_accounts")
        .select("*")
        .eq("platform", "google_search_console")
        .execute()
    )
    results = []
    for account in accounts.data or []:
        try:
            results.append(_scan_one_user(db, account))
        except Exception as e:
            results.append({"user_id": account["user_id"], "error": str(e)})
    return results


def _scan_one_user(db, account: dict) -> dict:
    user_id = account["user_id"]

    site_url = account.get("account_label")
    if not site_url:
        return {"user_id": user_id, "skipped": "no site_url on record"}

    creds = Credentials(
        token=account["access_token"],
        refresh_token=account["refresh_token"],
        token_uri=account["token_uri"],
        client_id=account["client_id"],
        client_secret=account["client_secret"],
        scopes=account["scopes"].split(" ") if account.get("scopes") else None,
    )
    service = build("searchconsole", "v1", credentials=creds)
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=30)
    response = (
        service.searchanalytics()
        .query(
            siteUrl=site_url,
            body={"startDate": start.isoformat(), "endDate": end.isoformat(), "dimensions": ["page"], "rowLimit": 25},
        )
        .execute()
    )
    rows = response.get("rows", [])

    gaps = generate_json(
        system_prompt=(
            "You are an SEO analyst. Find pages that are ranking (getting "
            "impressions) but underperforming on clicks or conversions — "
            "these are the highest-leverage content fixes."
        ),
        user_prompt=(
            f"Search Console data (page, clicks, impressions, ctr, position): {rows}\n\n"
            'Return JSON with key "gaps": an array of up to 3 objects, each with '
            '"page_url" (string), "problem" (short string), and '
            '"content_brief" (string — what a new blog post or page rewrite should cover).'
        ),
    ).get("gaps", [])

    drafted = 0
    for gap in gaps:
        blog = generate_json(
            system_prompt=(
                "You are a world-class SEO strategist and direct-response copywriter."
            ),
            user_prompt=(
                f"A page on this site ({gap.get('page_url')}) has this problem: "
                f"{gap.get('problem')}. Brief: {gap.get('content_brief')}\n\n"
                "Write an SEO-optimized blog post of roughly 700-900 words addressing it.\n"
                'Return JSON with keys: "title", "meta_description" (under 155 chars), '
                '"body_markdown" (using ## for H2s), and "target_keywords" (5-8 strings).'
            ),
            max_tokens=2500,
        )
        db.table("content_drafts").insert(
            {
                "user_id": user_id,
                "content_type": "blog",
                "source": "auto",
                "product_name": gap.get("page_url", "auto-detected gap"),
                "payload": blog,
                "status": "draft",
            }
        ).execute()
        drafted += 1

    return {"user_id": user_id, "gaps_found": len(gaps), "drafts_created": drafted}


def scan_content_gaps_for_user(user_id: str) -> dict:
    """
    Runs the Search Console content-gap scan for one user only — the version
    the frontend's "Run scan now" button calls.
    """
    db = get_admin_client()
    accounts = (
        db.table("connected_accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", "google_search_console")
        .execute()
    )
    if not accounts.data:
        return {"user_id": user_id, "skipped": "no Search Console account connected"}
    return _scan_one_user(db, accounts.data[0])


LINKEDIN_POST_CONTENT_TYPE = "linkedin_post"


def scan_linkedin_suggestions_for_user(user_id: str) -> dict:
    """
    Turns the user's approved content into LinkedIn post drafts.

    Works with tier-1 LinkedIn access (OpenID Connect — no app review): we
    don't read their LinkedIn feed, we write *for* it, from content they've
    already approved elsewhere in the app. Each approved piece becomes one
    auto-drafted LinkedIn post in the suggestion feed.

    Re-running is safe: pieces that already have a pending linkedin_post
    draft are skipped, so you don't get duplicates.
    """
    db = get_admin_client()

    approved = (
        db.table("content_drafts")
        .select("product_name, payload")
        .eq("user_id", user_id)
        .in_("status", ["approved", "published"])
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    if not approved.data:
        return {"user_id": user_id, "skipped": "no approved content yet — approve something first"}

    existing = {
        row["product_name"]
        for row in (
            db.table("content_drafts")
            .select("product_name")
            .eq("user_id", user_id)
            .eq("source", "auto")
            .eq("content_type", LINKEDIN_POST_CONTENT_TYPE)
            .eq("status", "draft")
            .execute()
        ).data or []
    }

    drafts_created = 0
    skipped_dupes = 0
    for piece in approved.data[:3]:  # cap at 3 posts per scan
        source_title = piece.get("product_name") or "your content"
        if source_title in existing:
            skipped_dupes += 1
            continue
        payload = piece.get("payload") or {}
        try:
            post = generate_json(
                system_prompt=(
                    "You are a LinkedIn ghostwriter. You turn existing long-form "
                    "content into native LinkedIn posts: a strong hook, a personal "
                    "tone, one clear takeaway, no salesy clichés, and a soft "
                    "call-to-action."
                ),
                user_prompt=(
                    "Turn this content into ONE LinkedIn post.\n\n"
                    f"Title: {source_title}\n"
                    f"Meta description: {payload.get('meta_description', '')}\n"
                    f"Body:\n{(payload.get('body_markdown') or '')[:1500]}\n\n"
                    'Return JSON with keys: "hook" (a first line that stops the '
                    'scroll, under 200 chars), "post_text" (the body, 150-250 '
                    'words, plain paragraphs with line breaks), and "hashtags" '
                    '(3-5 strings, no leading #).'
                ),
                max_tokens=1200,
            )
            hashtags = " ".join(f"#{h}" for h in (post.get("hashtags") or []))
            body = "\n\n".join(
                filter(None, [post.get("hook"), post.get("post_text"), hashtags])
            )
            db.table("content_drafts").insert(
                {
                    "user_id": user_id,
                    "content_type": LINKEDIN_POST_CONTENT_TYPE,
                    "source": "auto",
                    "product_name": source_title,
                    "payload": {
                        "title": f"LinkedIn post: {source_title}",
                        "body_markdown": body,
                        "meta_description": (
                            "A LinkedIn post turning your approved content into "
                            "a conversation starter."
                        ),
                    },
                    "status": "draft",
                }
            ).execute()
            drafts_created += 1
        except Exception as e:
            # One flaky AI call shouldn't sink the whole scan.
            return {"user_id": user_id, "error": str(e), "drafts_created": drafts_created}

    return {
        "user_id": user_id,
        "drafts_created": drafts_created,
        "skipped_duplicates": skipped_dupes,
        "eligible_content": len(approved.data),
    }


def scan_all_users_linkedin_suggestions() -> list[dict]:
    """Weekly-cron version: LinkedIn post drafts for every user with approved content."""
    db = get_admin_client()
    users = db.table("content_drafts").select("user_id").in_("status", ["approved", "published"]).execute()
    seen = set()
    results = []
    for row in users.data or []:
        uid = row["user_id"]
        if uid in seen:
            continue
        seen.add(uid)
        try:
            results.append(scan_linkedin_suggestions_for_user(uid))
        except Exception as e:
            results.append({"user_id": uid, "error": str(e)})
    return results


def scan_all_instagram_users() -> list[dict]:
    db = get_admin_client()
    accounts = (
        db.table("connected_accounts")
        .select("*")
        .eq("platform", "instagram")
        .execute()
    )
    results = []
    for account in accounts.data or []:
        try:
            results.append(_scan_one_instagram_user(db, account))
        except Exception as e:
            results.append({"user_id": account["user_id"], "error": str(e)})
    return results


def _scan_one_instagram_user(db, account: dict) -> dict:
    user_id = account["user_id"]

    ig_business_account_id = account.get("account_label")
    access_token = account.get("access_token")
    if not (ig_business_account_id and access_token):
        return {"user_id": user_id, "skipped": "no IG business account id or token on record"}

    posts = fetch_ig_media(ig_business_account_id, access_token)

    for post in posts:
        insights = fetch_ig_media_insights(post["id"], post["media_type"], access_token)
        post["reach"] = insights.get("reach")
        post["impressions"] = insights.get("impressions")
        post["saved"] = insights.get("saved")

    stats = compute_posting_stats(posts)

    # Mirrors how the Search Console scan stores its result.
    db.table("instagram_snapshots").upsert(
        {
            "user_id": user_id,
            "posts_per_week": stats["posts_per_week"],
            "avg_engagement": stats["avg_engagement"],
            "last_post_days_ago": stats["last_post_days_ago"],
            "recent_posts": posts,
            "scanned_at": "now()",
        },
        on_conflict="user_id",
    ).execute()

    return {
        "user_id": user_id,
        "posts_scanned": len(posts),
        "posts_per_week": stats["posts_per_week"],
    }
