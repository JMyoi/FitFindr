"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

MODEL = "llama-3.3-70b-versatile"


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()
    keywords = [kw.strip().lower() for kw in description.split() if kw.strip()]

    results = []
    for item in listings:
        # Price filter
        if max_price is not None and item["price"] > max_price:
            continue

        # Size filter — case-insensitive substring match
        if size is not None:
            if size.lower() not in item["size"].lower():
                continue

        # Score by keyword hits across title (2pts), style_tags (2pts), description (1pt)
        score = 0
        title_lower = item["title"].lower()
        desc_lower = item["description"].lower()
        tags_lower = [t.lower() for t in item["style_tags"]]

        for kw in keywords:
            if kw in title_lower:
                score += 2
            if any(kw in tag for tag in tags_lower):
                score += 2
            if kw in desc_lower:
                score += 1

        if score > 0:
            results.append((score, item))

    results.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in results]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions. If the wardrobe is empty,
        returns general styling advice for the item rather than raising an
        exception or returning an empty string.
    """
    item_summary = (
        f"Item: {new_item['title']}\n"
        f"Category: {new_item['category']}\n"
        f"Style tags: {', '.join(new_item['style_tags'])}\n"
        f"Colors: {', '.join(new_item['colors'])}\n"
        f"Condition: {new_item['condition']}\n"
        f"Price: ${new_item['price']}"
    )

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        prompt = (
            f"A thrift shopper is considering buying this item:\n{item_summary}\n\n"
            "They haven't described their wardrobe yet. Give them 1–2 sentences of "
            "general styling advice — what kinds of basics pair well with this piece, "
            "what vibe or occasion it suits, and how they might wear it. "
            "Be specific and practical, not generic."
        )
    else:
        wardrobe_lines = "\n".join(
            f"- {w['name']} ({w['category']}, {', '.join(w['colors'])})"
            for w in wardrobe_items
        )
        prompt = (
            f"A thrift shopper is considering buying this item:\n{item_summary}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_lines}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and specific "
            "pieces from their wardrobe. Name the wardrobe pieces by name. "
            "Keep it to 2–3 sentences, conversational and practical."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "This item would look great styled with neutral basics like straight-leg jeans and white sneakers."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message
        string — does NOT raise an exception.
    """
    if not outfit or not outfit.strip():
        return "Could not generate a fit card: no outfit description was provided."

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"Thrifted item: {new_item['title']} — ${new_item['price']} from {new_item['platform']}\n"
        f"Outfit context: {outfit}\n\n"
        "Rules:\n"
        "- Sound like a real person posting their OOTD, not a brand or product description\n"
        "- Mention the item name, price, and platform naturally (each once)\n"
        "- Capture the vibe of the outfit in specific terms\n"
        "- Keep it casual, lowercase is fine, one emoji max\n"
        "- 2–4 sentences only, no hashtags"
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=1.2,
            max_tokens=150,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Could not generate a fit card at this time."
