"""
Basic tests that don't require live API keys — run with:
    cd backend && pytest tests/
"""
import sys
import os
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from schemas import ContentRequest, BlogResponse
from routers.audit import _last_30_days


def test_content_request_requires_core_fields():
    req = ContentRequest(product_name="Widget", target_audience="Devs", goal="Signups")
    assert req.tone == "confident and clear"  # default applied
    assert req.key_points is None


def test_blog_response_shape():
    data = {
        "title": "Test",
        "meta_description": "desc",
        "body_markdown": "## Heading\ntext",
        "target_keywords": ["a", "b"],
    }
    resp = BlogResponse(**data)
    assert resp.title == "Test"
    assert len(resp.target_keywords) == 2


def test_json_fence_stripping():
    """Mirrors the cleaning logic in core/ai_client.generate_json — models
    sometimes wrap JSON in markdown fences despite instructions not to."""
    raw = '```json\n{"a": 1}\n```'
    cleaned = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    assert json.loads(cleaned) == {"a": 1}


def test_last_30_days_is_a_rolling_window():
    start, end = _last_30_days()
    # Just check they're valid ISO dates and start is before end
    from datetime import date

    start_d = date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    assert start_d < end_d
    assert (end_d - start_d).days == 30
