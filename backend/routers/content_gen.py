from fastapi import APIRouter, HTTPException, Depends

from schemas import (
    ContentRequest,
    BlogResponse,
    LandingPageResponse,
    AdResponse,
    VideoScriptResponse,
)
from core.ai_client import generate_json
from core.auth import get_optional_user_id, get_admin_client
from core.rate_limit import rate_limit

router = APIRouter()

BASE_PERSONA = (
    "You are a world-class SEO strategist and direct-response copywriter who has "
    "grown dozens of small businesses through organic search and paid social."
)


def _save_draft(user_id: str | None, content_type: str, product_name: str, payload: dict):
    """Best-effort save — a logged-out user can still generate content, it
    just won't be saved to their account."""
    if not user_id:
        return
    try:
        get_admin_client().table("content_drafts").insert(
            {
                "user_id": user_id,
                "content_type": content_type,
                "source": "manual",
                "product_name": product_name,
                "payload": payload,
            }
        ).execute()
    except Exception:
        # Don't fail the request just because the save failed — surface
        # this in logs in a real deployment.
        pass


def _context(req: ContentRequest) -> str:
    extra = f"\nAdditional context: {req.key_points}" if req.key_points else ""
    return (
        f"Product/Service: {req.product_name}\n"
        f"Target audience: {req.target_audience}\n"
        f"Goal: {req.goal}\n"
        f"Tone: {req.tone}{extra}"
    )


@router.post("/blog", response_model=BlogResponse, dependencies=[Depends(rate_limit)])
def generate_blog(req: ContentRequest, user_id: str | None = Depends(get_optional_user_id)):
    try:
        data = generate_json(
            system_prompt=BASE_PERSONA,
            user_prompt=(
                f"{_context(req)}\n\n"
                "Write an SEO-optimized blog post of roughly 900-1100 words.\n"
                'Return JSON with keys: "title" (string), "meta_description" '
                '(string, under 155 chars), "body_markdown" (string, using ## for '
                'H2 subheadings), and "target_keywords" (array of 5-8 strings).'
            ),
            max_tokens=3000,
        )
        _save_draft(user_id, "blog", req.product_name, data)
        return BlogResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")


@router.post("/landing-page", response_model=LandingPageResponse, dependencies=[Depends(rate_limit)])
def generate_landing_page(req: ContentRequest, user_id: str | None = Depends(get_optional_user_id)):
    try:
        data = generate_json(
            system_prompt=BASE_PERSONA,
            user_prompt=(
                f"{_context(req)}\n\n"
                "Write landing page copy.\n"
                'Return JSON with keys: "headline" (string), "subheadline" (string), '
                '"benefits" (array of 3-5 short benefit strings), and "cta_text" '
                "(string, a short call-to-action button label)."
            ),
        )
        _save_draft(user_id, "landing_page", req.product_name, data)
        return LandingPageResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")


@router.post("/ad", response_model=AdResponse, dependencies=[Depends(rate_limit)])
def generate_ad(req: ContentRequest, user_id: str | None = Depends(get_optional_user_id)):
    try:
        data = generate_json(
            system_prompt=BASE_PERSONA,
            user_prompt=(
                f"{_context(req)}\n\n"
                "Write a text ad suitable for Facebook or LinkedIn.\n"
                'Return JSON with keys: "headline" (string, under 40 chars), '
                '"primary_text" (string, 1-3 short sentences), and "hashtags" '
                "(array of 3-6 strings, without the # symbol)."
            ),
        )
        _save_draft(user_id, "ad", req.product_name, data)
        return AdResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")


@router.post("/video-script", response_model=VideoScriptResponse, dependencies=[Depends(rate_limit)])
def generate_video_script(req: ContentRequest, user_id: str | None = Depends(get_optional_user_id)):
    try:
        data = generate_json(
            system_prompt=BASE_PERSONA,
            user_prompt=(
                f"{_context(req)}\n\n"
                "Write a 30-second video ad script broken into 3-5 scenes.\n"
                'Return JSON with key "scenes": an array of objects, each with '
                '"scene" (string, short label), "visual_suggestion" (string), '
                'and "voiceover_text" (string, 1-2 sentences).'
            ),
        )
        _save_draft(user_id, "video_script", req.product_name, data)
        return VideoScriptResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Generation failed: {e}")
