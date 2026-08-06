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
"""
from datetime import date, timedelta

from core.auth import get_admin_client
from core.ai_client import generate_json

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
