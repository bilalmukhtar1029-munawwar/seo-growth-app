"""
Publishes approved blog drafts to a WordPress site via the WP REST API.

Unlike Meta/LinkedIn, this needs no platform review — WordPress's REST API
works out of the box on any self-hosted site (or WordPress.com Business
plan) using an "Application Password":
  1. In WP admin: Users -> Profile -> Application Passwords -> generate one
  2. Set WORDPRESS_URL, WORDPRESS_USERNAME, WORDPRESS_APP_PASSWORD in .env

This only covers blog posts, since that maps directly to a WP post. Landing
pages/ads/video scripts don't have an obvious "publish" target — those stay
manual (copy from the generator into wherever they're used).
"""
import base64
import os

import httpx


def is_configured() -> bool:
    return bool(
        os.environ.get("WORDPRESS_URL")
        and os.environ.get("WORDPRESS_USERNAME")
        and os.environ.get("WORDPRESS_APP_PASSWORD")
    )


def publish_blog_post(title: str, body_markdown: str, meta_description: str = "") -> dict:
    """
    Publishes a post as a draft on WordPress (status='draft', not 'publish')
    so a human still does the final "make it live" click in WP itself —
    this app auto-drafts, it doesn't auto-publish to the public internet.
    Returns the created post's admin edit link.
    """
    site_url = os.environ.get("WORDPRESS_URL", "").rstrip("/")
    username = os.environ.get("WORDPRESS_USERNAME")
    app_password = os.environ.get("WORDPRESS_APP_PASSWORD")
    if not (site_url and username and app_password):
        raise RuntimeError(
            "WordPress isn't configured. Set WORDPRESS_URL / WORDPRESS_USERNAME / "
            "WORDPRESS_APP_PASSWORD in backend/.env."
        )

    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    # WP's block editor expects HTML, not markdown — a naive markdown->HTML
    # pass for the ## headings this app generates. Swap for a real markdown
    # library (e.g. `markdown2`) if you need full markdown support.
    body_html = "\n".join(
        f"<h2>{line[3:]}</h2>" if line.startswith("## ") else f"<p>{line}</p>"
        for line in body_markdown.split("\n")
        if line.strip()
    )

    resp = httpx.post(
        f"{site_url}/wp-json/wp/v2/posts",
        headers={"Authorization": f"Basic {token}"},
        json={
            "title": title,
            "content": body_html,
            "status": "draft",
            "excerpt": meta_description,
        },
        timeout=20,
    )
    resp.raise_for_status()
    post = resp.json()
    return {
        "wp_post_id": post["id"],
        "wp_edit_link": f"{site_url}/wp-admin/post.php?post={post['id']}&action=edit",
    }
