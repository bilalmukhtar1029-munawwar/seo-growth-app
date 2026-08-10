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


def _extract_json(text: str) -> str:
    """
    Best-effort extraction of a JSON object from a model response.
    Handles markdown fences, stray prose before/after, and the model
    occasionally wrapping the JSON in extra text.
    """
    stripped = text.strip()
    # Strip ```json ... ``` fences
    cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", stripped, flags=re.MULTILINE).strip()
    if cleaned.startswith("{"):
        return cleaned
    # Fall back to the first {...} block in the text
    match = re.search(r"\{[^{}]*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")
    return match.group(0)


def generate_json(
    system_prompt: str, user_prompt: str, max_tokens: int = 1500, attempts: int = 2
) -> dict:
    """
    Calls Groq and asks for a JSON-only response, then parses it.
    Retries once with a stricter instruction if the first parse fails,
    so a single flaky response doesn't 502 the user.
    """
    client = get_client()
    last_error: Exception | None = None
    for i in range(attempts):
        strict = (
            ""
            if i == 0
            else "\n\nIMPORTANT: Your previous response could not be parsed as JSON. "
            "Return ONLY a single valid JSON object. No markdown, no code fences, no explanation."
        )
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                    + "\n\nRespond with ONLY a valid JSON object. No preamble, no markdown fences, no commentary."
                    + strict,
                },
                {"role": "user", "content": user_prompt},
            ],
        )
        text = (response.choices[0].message.content or "").strip()
        try:
            return json.loads(_extract_json(text))
        except Exception as e:  # JSONDecodeError or ValueError
            last_error = e
    raise RuntimeError(f"AI returned unparsable JSON after {attempts} attempts: {last_error}")
