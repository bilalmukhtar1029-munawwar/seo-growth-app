"""
The "Auto-Suggested Content Feed" from your original plan (Part 2).

Module 2's Celery task (core/tasks.py) drops auto-generated drafts into
`content_drafts` with source='auto', status='draft'. These endpoints let
the frontend list them, and let the user approve or dismiss each one.
"""
from fastapi import APIRouter, HTTPException, Depends

from core.auth import get_current_user_id, get_admin_client
from core.wordpress_client import is_configured as wp_configured, publish_blog_post

router = APIRouter()


@router.get("/")
def get_auto_feed(user_id: str = Depends(get_current_user_id)):
    """All pending auto-suggested drafts for the logged-in user, newest first."""
    try:
        result = (
            get_admin_client()
            .table("content_drafts")
            .select("*")
            .eq("user_id", user_id)
            .eq("source", "auto")
            .eq("status", "draft")
            .order("created_at", desc=True)
            .execute()
        )
        return result.data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load feed: {e}")


@router.post("/{draft_id}/approve")
def approve_draft(draft_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Marks a draft approved. If it's a blog post and WordPress is configured,
    also pushes it to WordPress as a draft post (never auto-publishes live —
    that final click still happens in WordPress itself).
    """
    db = get_admin_client()
    try:
        result = (
            db.table("content_drafts")
            .select("*")
            .eq("id", draft_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Draft not found")
        draft = result.data[0]

        update = {"status": "approved"}
        wp_result = None
        if draft["content_type"] == "blog" and wp_configured():
            try:
                payload = draft["payload"]
                wp_result = publish_blog_post(
                    title=payload.get("title", draft.get("product_name", "Untitled")),
                    body_markdown=payload.get("body_markdown", ""),
                    meta_description=payload.get("meta_description", ""),
                )
                update["status"] = "published"
            except Exception as e:
                # Don't fail the approval just because WP publish failed —
                # the draft is still approved, just not pushed yet.
                wp_result = {"error": str(e)}

        updated = (
            db.table("content_drafts").update(update).eq("id", draft_id).execute()
        )
        response = updated.data[0]
        if wp_result:
            response["wordpress"] = wp_result
        return response
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to approve draft: {e}")


@router.delete("/{draft_id}")
def dismiss_draft(draft_id: str, user_id: str = Depends(get_current_user_id)):
    try:
        get_admin_client().table("content_drafts").delete().eq("id", draft_id).eq(
            "user_id", user_id
        ).execute()
        return {"status": "dismissed"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to dismiss draft: {e}")
