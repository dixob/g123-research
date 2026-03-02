"""
VLM provider adapters — unified interface for calling each model.
"""
import base64, os, re, json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _clean_json(raw: str) -> str:
    """Strip markdown fences and whitespace from model output."""
    cleaned = re.sub(r"```json\n?|\n?```", "", raw).strip()
    # Some models wrap in ```\n...\n```
    cleaned = re.sub(r"^```\n?|\n?```$", "", cleaned).strip()
    return cleaned


def call_openai(image_path: str, prompt: str, cfg: dict) -> str:
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
    return response.choices[0].message.content


def call_google(image_path: str, prompt: str, cfg: dict) -> str:
    from google import genai
    from PIL import Image

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
    img = Image.open(image_path)

    response = client.models.generate_content(
        model=cfg["model_id"],
        contents=[img, prompt],
    )
    return response.text


def call_together(image_path: str, prompt: str, cfg: dict) -> str:
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
    return response.choices[0].message.content


# Provider dispatch
PROVIDERS = {
    "openai": call_openai,
    "google": call_google,
    "together": call_together,
}


def call_model(model_name: str, image_path: str, prompt: str, models_cfg: dict) -> dict | None:
    """
    Call a VLM and return parsed JSON, or None on failure.
    Also returns raw response and timing metadata.
    """
    import time

    cfg = models_cfg[model_name]
    provider_fn = PROVIDERS[cfg["provider"]]

    start = time.time()
    try:
        raw = provider_fn(image_path, prompt, cfg)
    except Exception as e:
        return {
            "raw": None,
            "parsed": None,
            "error": str(e),
            "latency_s": time.time() - start,
        }
    latency = time.time() - start

    cleaned = _clean_json(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = None

    return {
        "raw": raw,
        "parsed": parsed,
        "error": None,
        "latency_s": latency,
    }
