from pydantic import BaseModel, Field
from typing import Optional, Literal


class ContentRequest(BaseModel):
    product_name: str = Field(..., description="Product or service name")
    target_audience: str = Field(..., description="Who the content is aimed at")
    goal: str = Field(..., description="The desired outcome, e.g. 'email signups'")
    tone: Optional[str] = Field(
        "confident and clear", description="Voice/tone for the generated copy"
    )
    key_points: Optional[str] = Field(
        None, description="Optional extra facts, offers, or differentiators to include"
    )


class BlogResponse(BaseModel):
    title: str
    meta_description: str
    body_markdown: str
    target_keywords: list[str]


class LandingPageResponse(BaseModel):
    headline: str
    subheadline: str
    benefits: list[str]
    cta_text: str


class AdResponse(BaseModel):
    headline: str
    primary_text: str
    hashtags: list[str]


class VideoScriptScene(BaseModel):
    scene: str
    visual_suggestion: str
    voiceover_text: str


class VideoScriptResponse(BaseModel):
    scenes: list[VideoScriptScene]
