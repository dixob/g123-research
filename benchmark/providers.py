"""
VLM provider adapters — unified interface for calling each model.

Each provider function returns a ProviderResult dict containing:
  - text: The raw text output from the model
  - input_tokens: Number of input/prompt tokens consumed
  - output_tokens: Number of output/completion tokens consumed
"""
import base64, os, re, json
from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv

load_dotenv()


class ProviderResult(TypedDict):
    text: str
    input_tokens: int | None
    output_tokens: int | None


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _clean_json(raw: str) -> str:
    """Strip markdown fences and whitespace from model output."""
    cleaned = re.sub(r"```json\n?|\n?```", "", raw).strip()
    # Some models wrap in ```\n...\n```
    cleaned = re.sub(r"^```\n?|\n?```$", "", cleaned).strip()
    return cleaned


def call_openai(image_path: str, prompt: str, cfg: dict) -> ProviderResult:
    import openai

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    image_data = _encode_image(image_path)

    response = client.chat.completions.create(
        model=cfg["model_id"],
        max_tokens=cfg.get("max_tokens", 500),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    usage = response.usage
    return {
        "text": response.choices[0].message.content,
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
    }


def call_google(image_path: str, prompt: str, cfg: dict) -> ProviderResult:
    from google import genai
    from PIL import Image

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    img = Image.open(image_path)

    response = client.models.generate_content(
        model=cfg["model_id"],
        contents=[img, prompt],
    )

    # google-genai SDK exposes usage_metadata on the response
    meta = getattr(response, "usage_metadata", None)
    return {
        "text": response.text,
        "input_tokens": getattr(meta, "prompt_token_count", None),
        "output_tokens": getattr(meta, "candidates_token_count", None),
    }


def call_together(image_path: str, prompt: str, cfg: dict) -> ProviderResult:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("TOGETHER_API_KEY"),
        base_url="https://api.together.xyz/v1",
    )
    image_data = _encode_image(image_path)

    response = client.chat.completions.create(
        model=cfg["model_id"],
        max_tokens=cfg.get("max_tokens", 1000),
        temperature=cfg.get("temperature", 0.1),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    usage = response.usage
    return {
        "text": response.choices[0].message.content,
        "input_tokens": usage.prompt_tokens if usage else None,
        "output_tokens": usage.completion_tokens if usage else None,
    }


# Provider dispatch
PROVIDERS = {
    "openai": call_openai,
    "google": call_google,
    "together": call_together,
}


def call_model(model_name: str, image_path: str, prompt: str, models_cfg: dict) -> dict:
    """
    Call a VLM and return parsed JSON with token usage and cost metadata.

    Returns dict with keys:
      raw, parsed, error, latency_s,
      input_tokens, output_tokens, cost_usd
    """
    import time
    from .config import compute_cost

    cfg = models_cfg[model_name]
    provider_fn = PROVIDERS[cfg["provider"]]

    start = time.time()
    try:
        result = provider_fn(image_path, prompt, cfg)
    except Exception as e:
        return {
            "raw": None,
            "parsed": None,
            "error": str(e),
            "latency_s": time.time() - start,
            "input_tokens": None,
            "output_tokens": None,
            "cost_usd": None,
        }
    latency = time.time() - start

    raw_text = result["text"]
    input_tokens = result["input_tokens"]
    output_tokens = result["output_tokens"]

    # Compute cost
    cost = compute_cost(model_name, input_tokens, output_tokens)

    cleaned = _clean_json(raw_text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None

    return {
        "raw": raw_text,
        "parsed": parsed,
        "error": None,
        "latency_s": latency,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
    }
