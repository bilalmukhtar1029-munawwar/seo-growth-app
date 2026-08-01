"""
Thin wrapper around the Groq API — genuinely free, no credit card required.

Groq exposes an OpenAI-compatible endpoint, so we use the `openai` SDK
pointed at Groq's base URL. Reads GROQ_API_KEY from the environment
(set it in backend/.env, see .env.example). Get a free key at
https://console.groq.com/keys — no payment info needed.
"""
import json
import os
import re

from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Add it to backend/.env (see .env.example). "
                "Get a free key at https://console.groq.com/keys — no card needed."
            )
        _client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    return _client


# "llama-3.3-70b-versatile" is Groq's free, fast, general-purpose model —
# reliable at following "return only JSON" instructions.
# "deepseek-r1-distill-llama-70b" is also free on Groq and closer in spirit
# to the original DeepSeek choice, but reasoning models emit extra
# "thinking" text that can break strict JSON parsing — swap in if you want
# to try it, just expect to loosen the JSON-cleaning step below.
DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def generate_json(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> dict:
    """
    Calls Groq and asks for a JSON-only response, then parses it.
    Strips markdown code fences defensively in case the model adds them.
    """
    client = get_client()
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "system",
                "content": system_prompt
                + "\n\nRespond with ONLY a valid JSON object. No preamble, no markdown fences, no commentary.",
            },
            {"role": "user", "content": user_prompt},
        ],
    )
    text = response.choices[0].message.content
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)
