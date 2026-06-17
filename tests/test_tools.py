"""
Tests for each tool's happy path and failure modes.
Run with: pytest tests/
"""

import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    # Impossible combo — no results expected
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=30)
    assert all(item["price"] <= 30 for item in results)

def test_search_size_filter():
    results = search_listings("jeans", size="M", max_price=None)
    # Every returned item's size field must contain "m" (case-insensitive)
    assert all("m" in item["size"].lower() for item in results)

def test_search_returns_list_on_no_price_no_size():
    results = search_listings("flannel", size=None, max_price=None)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_best_match_first():
    results = search_listings("vintage denim", size=None, max_price=None)
    assert len(results) > 1
    # First result should have "vintage" or "denim" prominently in title or tags
    first = results[0]
    combined = (first["title"] + " ".join(first["style_tags"])).lower()
    assert "vintage" in combined or "denim" in combined


# ── suggest_outfit ────────────────────────────────────────────────────────────

def _get_sample_item():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert results, "Need at least one search result for outfit tests"
    return results[0]

def test_suggest_outfit_with_wardrobe():
    item = _get_sample_item()
    result = suggest_outfit(item, get_example_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe():
    item = _get_sample_item()
    result = suggest_outfit(item, get_empty_wardrobe())
    assert isinstance(result, str)
    assert len(result) > 0  # must not return empty string


# ── create_fit_card ───────────────────────────────────────────────────────────

def test_create_fit_card_returns_string():
    item = _get_sample_item()
    outfit = "Pair with straight-leg jeans and white sneakers for a clean look."
    result = create_fit_card(outfit, item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_empty_outfit():
    item = _get_sample_item()
    result = create_fit_card("", item)
    assert result == "Could not generate a fit card: no outfit description was provided."

def test_create_fit_card_whitespace_outfit():
    item = _get_sample_item()
    result = create_fit_card("   ", item)
    assert result == "Could not generate a fit card: no outfit description was provided."

def test_create_fit_card_varies():
    # Run twice on the same inputs — outputs should differ due to temperature=1.2
    item = _get_sample_item()
    outfit = "Pair with straight-leg jeans and chunky sneakers."
    result_a = create_fit_card(outfit, item)
    result_b = create_fit_card(outfit, item)
    assert result_a != result_b, "Fit card output should vary between runs"
