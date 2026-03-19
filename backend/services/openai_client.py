from __future__ import annotations

import asyncio
import json
import logging

import openai
from openai import AsyncOpenAI

from backend.config import OPENAI_API_KEY, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS
from backend.models.menu import Category, MenuItem, MenuResponse

log = logging.getLogger(__name__)


_client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=OPENAI_TIMEOUT_SECONDS)

_SYSTEM_PROMPT = """\
You are a multilingual menu extraction assistant. Your job is to analyse restaurant menu content
and return structured JSON.

Rules:
- Detect the primary language of the menu and provide both a human-readable language name and a BCP-47
  language code (e.g. "Japanese" / "ja", "French" / "fr", "English" / "en").
- Find the restaurant name if it appears anywhere in the content; otherwise use null.
- Group all items into categories. If the menu has explicit category headings, use them.
  If not, infer sensible categories (e.g. "Appetizers", "Main Dishes", "Drinks", "Desserts").
- For each item extract:
    name_original  — the item name in its non-English language. Set to null if the title
                     is English-only.
    name_english   — the English name. If the source is already English, use the title as-is.
                     If the title contains BOTH a non-English word/phrase AND an English
                     word/phrase (e.g. "枝豆 Edamame", "Karaage 唐揚げ", "크림 파스타 Cream Pasta"),
                     split them: put the non-English part in name_original and the English part
                     in name_english. Otherwise, translate the non-English name to English.
    description    — short description or null if none
    price          — numeric price value or null
    currency       — ISO 4217 currency code inferred from symbols (e.g. "USD", "JPY", "EUR") or null
    tags           — list of labels from ["gluten-free", "spicy", "caffeine", "hot", "cold"].
                     Only include a label when the menu explicitly indicates it (text note, icon,
                     or symbol). There can be multiple labels for each dish. Use an empty array [] if nothing applies.
    sizes          — for drinks/beverages, list available sizes exactly as printed
                     (e.g. ["S", "M", "L"] or ["Regular", "Large"]). Use [] for food items.
- Translate descriptions to English when present.
- Use null for any field you cannot determine.
- Do NOT invent items that are not present.

Return ONLY valid JSON matching this schema (no markdown, no extra keys):
{
  "restaurant_name": "string | null",
  "detected_language": "string | null",
  "language_code": "string | null",
  "categories": [
    {
      "name": "string",
      "items": [
        {
          "name_original": "string | null",
          "name_english": "string | null",
          "description": "string | null",
          "price": number | null,
          "currency": "string | null",
          "tags": ["string", ...],
          "sizes": ["string", ...]
        }
      ]
    }
  ]
}
"""


def _build_text_messages(text: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here is the extracted text from a restaurant menu PDF. "
                "Please analyse it and return the structured JSON.\n\n"
                f"<menu_text>\n{text}\n</menu_text>"
            ),
        },
    ]


async def _extract_page_dict(img_b64: str, page_num: int, total: int) -> dict:
    """Call GPT-4o with a single menu page image; return raw parsed dict."""
    content_parts: list[dict] = [
        {
            "type": "text",
            "text": (
                f"This is page {page_num} of {total} from a restaurant menu PDF. "
                "Extract all menu items visible on this page and return structured JSON."
            ),
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}", "detail": "auto"},
        },
    ]
    messages = [{"role": "system", "content": _SYSTEM_PROMPT}, {"role": "user", "content": content_parts}]
    response = await _client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    usage = response.usage
    if usage:
        log.info("Page %d/%d: prompt_tokens=%d completion_tokens=%d",
                 page_num, total, usage.prompt_tokens, usage.completion_tokens)
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Page {page_num}: model returned invalid JSON: {exc}") from exc


def _merge_page_dicts(results: list[dict]) -> dict:
    """Merge multiple per-page MenuResponse dicts into one."""
    merged: dict = {
        "restaurant_name": next((r.get("restaurant_name") for r in results if r.get("restaurant_name")), None),
        "detected_language": next((r.get("detected_language") for r in results if r.get("detected_language")), None),
        "language_code": next((r.get("language_code") for r in results if r.get("language_code")), None),
        "categories": [],
    }
    cat_index: dict[str, dict] = {}
    for result in results:
        for cat in result.get("categories", []):
            key = cat.get("name", "").lower().strip()
            if key not in cat_index:
                cat_index[key] = {"name": cat["name"], "items": []}
                merged["categories"].append(cat_index[key])
            cat_index[key]["items"].extend(cat.get("items", []))
    return merged


async def extract_menu(content: dict) -> MenuResponse:
    images: list[str] = content.get("images", [])
    text: str = content.get("text", "")

    if images:
        total = len(images)
        log.info("Dispatching %d parallel page extraction(s) (model=%s, timeout=%ds)",
                 total, OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS)
        try:
            page_dicts = await asyncio.gather(
                *[_extract_page_dict(img, i + 1, total) for i, img in enumerate(images)]
            )
        except openai.APITimeoutError:
            log.error("OpenAI API timed out after %ds", OPENAI_TIMEOUT_SECONDS)
            raise
        except openai.APIStatusError as exc:
            log.error("OpenAI API error: status=%s message=%s", exc.status_code, exc.message)
            raise
        data = _merge_page_dicts(list(page_dicts))
    else:
        log.info("Building text messages: %d chars", len(text))
        messages = _build_text_messages(text)
        log.info("Sending request to OpenAI (model=%s, timeout=%ds)...", OPENAI_MODEL, OPENAI_TIMEOUT_SECONDS)
        try:
            response = await _client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )
        except openai.APITimeoutError:
            log.error("OpenAI API timed out after %ds", OPENAI_TIMEOUT_SECONDS)
            raise
        except openai.APIStatusError as exc:
            log.error("OpenAI API error: status=%s message=%s", exc.status_code, exc.message)
            raise

        usage = response.usage
        if usage:
            log.info("OpenAI response received: prompt_tokens=%d completion_tokens=%d total_tokens=%d",
                     usage.prompt_tokens, usage.completion_tokens, usage.total_tokens)

        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Model returned invalid JSON: {exc}") from exc

    # Coerce categories / items defensively
    categories: list[Category] = []
    for cat in data.get("categories", []):
        items: list[MenuItem] = []
        for item in cat.get("items", []):
            # Ensure price is float or None
            price = item.get("price")
            if price is not None:
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    price = None
            items.append(
                MenuItem(
                    name_original=item.get("name_original"),
                    name_english=item.get("name_english"),
                    description=item.get("description"),
                    price=price,
                    currency=item.get("currency"),
                    tags=[str(t) for t in item.get("tags", []) if t],
                    sizes=[str(s) for s in item.get("sizes", []) if s],
                )
            )
        categories.append(Category(name=cat.get("name", "Other"), items=items))

    return MenuResponse(
        restaurant_name=data.get("restaurant_name"),
        detected_language=data.get("detected_language"),
        language_code=data.get("language_code"),
        categories=categories,
    )
