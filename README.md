# FitFindr

A multi-tool AI agent that helps users find secondhand clothing and figure out how to wear it. Given a natural language query, FitFindr searches mock thrift listings, suggests outfit combinations based on the user's wardrobe, and generates a shareable caption for the final look.

## Setup

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file in the project root:
```
GROQ_API_KEY=your_key_here
```

Run the app:
```powershell
python app.py
```
Open the URL shown in your terminal (usually `http://localhost:7860`).

---

## Tool Inventory

### `search_listings(description, size, max_price)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords describing the item (e.g., `"vintage graphic tee"`) |
| `size` | `str \| None` | Size to filter by (case-insensitive substring match). `None` skips size filtering. |
| `max_price` | `float \| None` | Maximum price in dollars (inclusive). `None` skips price filtering. |

**Returns:** `list[dict]` — matching listing dicts sorted by relevance score (highest first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns `[]` if nothing matches.

**Purpose:** Scores each listing by keyword hits across title (2 pts), style_tags (2 pts), and description (1 pt), filters by size and price, and returns the top matches.

---

### `suggest_outfit(new_item, wardrobe)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A listing dict — the thrifted item the user is considering |
| `wardrobe` | `dict` | Wardrobe dict with an `"items"` key containing a list of wardrobe item dicts |

**Returns:** `str` — 2–3 sentences of outfit suggestions. References specific wardrobe pieces by name when the wardrobe is populated. Falls back to general styling advice when the wardrobe is empty. Never returns an empty string.

**Purpose:** Calls the Groq LLM (llama-3.3-70b-versatile) with the item details and wardrobe contents to generate practical outfit combinations.

---

### `create_fit_card(outfit, new_item)`

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit` |
| `new_item` | `dict` | The listing dict — used to pull title, price, and platform into the caption |

**Returns:** `str` — a 2–4 sentence Instagram/TikTok-style caption mentioning the item name, price, and platform. Returns a descriptive error message string (not an exception) if `outfit` is empty.

**Purpose:** Calls the Groq LLM at `temperature=1.2` so output varies across runs. The caption is meant to sound like a real OOTD post, not a product description.

---

## How the Planning Loop Works

The planning loop lives in `run_agent()` in `agent.py`. It is not a fixed sequence — it branches based on what each step returns.

**Step 1 — Parse the query.** The raw natural language query is sent to the Groq LLM, which extracts three structured fields: `description` (str), `size` (str or null), `max_price` (float or null). This lets the agent handle queries like "vintage tee under thirty dollars, size M" without the user needing to fill out a form. The parsed result is stored in `session["parsed"]`.

**Step 2 — Search.** `search_listings` is called with the parsed parameters. This is the only decision point in the loop:
- If the result is an **empty list**: the agent sets `session["error"]` with an actionable message (what was searched, what the user can try differently) and returns immediately. `suggest_outfit` and `create_fit_card` are never called. This is intentional — calling an outfit tool with no item would produce meaningless output.
- If the result is **non-empty**: the top result is stored as `session["selected_item"]` and the loop continues.

**Step 3 — Suggest outfit.** `suggest_outfit` is always called if we reach this step (it handles the empty-wardrobe case internally). The result goes into `session["outfit_suggestion"]`.

**Step 4 — Create fit card.** `create_fit_card` receives `session["outfit_suggestion"]` and `session["selected_item"]`. The result goes into `session["fit_card"]`.

**Step 5 — Return.** The completed session dict is returned. `handle_query()` in `app.py` reads from it to populate the three UI panels.

The agent's behavior is conditional: a query that returns no search results produces a different response path than one that does. It does not call all three tools unconditionally.

---

## State Management

A single `session` dict is created at the start of each `run_agent()` call and passed through every step. No tool receives the session dict — each tool takes only its own inputs. `run_agent()` extracts values from the session and passes them as arguments, then writes the results back.

| Session key | Set after | Consumed by |
|-------------|-----------|-------------|
| `query` | Initialization | Reference only |
| `wardrobe` | Initialization | `suggest_outfit` |
| `parsed` | LLM parse step | `search_listings` |
| `search_results` | `search_listings` | Reference only |
| `selected_item` | `search_listings` | `suggest_outfit`, `create_fit_card` |
| `outfit_suggestion` | `suggest_outfit` | `create_fit_card` |
| `fit_card` | `create_fit_card` | UI output |
| `error` | If search returns `[]` | UI output |

This design keeps each tool independently testable. A tool only knows about its own inputs — not the session structure around it.

---

## Interaction Walkthrough

**User query:** `"looking for a vintage graphic tee under $30"`

**Step 1 — Parse query (LLM):**
- Tool: Groq LLM (internal parse step, not a named tool)
- Input: the raw query string
- Why: extract structured parameters from natural language without requiring form fields
- Output: `{"description": "vintage graphic tee", "size": null, "max_price": 30.0}`

**Step 2 — Search listings:**
- Tool: `search_listings`
- Input: `description="vintage graphic tee"`, `size=None`, `max_price=30.0`
- Why: first step in every interaction — find a real item before doing anything else
- Output: `[{"id": "lst_002", "title": "Y2K Baby Tee — Butterfly Print", "price": 18.0, "platform": "depop", ...}, ...]`
- Decision: results non-empty → store `results[0]` as `selected_item`, continue

**Step 3 — Suggest outfit:**
- Tool: `suggest_outfit`
- Input: `new_item=session["selected_item"]`, `wardrobe=get_example_wardrobe()`
- Why: user has an item now — generate outfit combinations using their actual wardrobe pieces
- Output: `"Pair this Y2K butterfly tee with your baggy straight-leg jeans and chunky white sneakers for a classic early-2000s look. Tuck the front slightly and add your black crossbody bag to keep it intentional."`

**Step 4 — Create fit card:**
- Tool: `create_fit_card`
- Input: `outfit=session["outfit_suggestion"]`, `new_item=session["selected_item"]`
- Why: user has an item and an outfit — generate a shareable caption to close the loop
- Output: `"snagged this y2k butterfly tee off depop for $18 and my baggy jeans have never been happier 🦋 full fit incoming"`

**Final output to user:** Three panels populate in the Gradio UI — the listing details, the outfit suggestion, and the fit card caption.

---

## Error Handling and Fail Points

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listings match the query | Sets `session["error"]` = `"No listings found for '[description]'[size/price context]. Try a broader description, a higher price, or leave the size out."` Returns session immediately — `suggest_outfit` and `create_fit_card` are never called. User sees the error in the listing panel; other panels show `—`. |
| `suggest_outfit` | Wardrobe is empty (`items = []`) | Prompts the LLM for general styling advice about the item on its own instead of wardrobe-specific combinations. Always returns a non-empty string. Tested with: `suggest_outfit(item, get_empty_wardrobe())` — returns e.g. `"This Y2K tee pairs well with high-waisted jeans and platform sneakers for a casual throwback look."` |
| `create_fit_card` | `outfit` argument is empty or whitespace | Returns `"Could not generate a fit card: no outfit description was provided."` immediately, without calling the LLM. Tested with: `create_fit_card("", item)` — confirmed exact error string, no exception. |

---

## Spec Reflection

**One way planning.md helped during implementation:**

Writing out the session state table before touching any code made it easy to implement `run_agent()` correctly on the first try. Because I had already listed every key, its type, when it gets set, and what reads it, the function body was almost mechanical to write — each step knew exactly where to read from and write to. Without that table I likely would have passed the session dict into the tools directly, which would have made them harder to test in isolation.

**One divergence from the spec, and why:**

The spec described the planning loop as having a single early-exit at step 3 (empty search results). In practice, `suggest_outfit` also needed its own internal branch for the empty-wardrobe case, which I initially planned to handle at the planning loop level. I moved that logic inside the tool instead, because it made the tool independently testable — calling `suggest_outfit` with an empty wardrobe should always return something useful regardless of who calls it. The planning loop stayed simpler as a result.

---

## AI Usage

**Instance 1 — Implementing `search_listings`:**

I gave Claude the Tool 1 spec block from `planning.md` (inputs with types, the scoring logic — title/tags 2pts, description 1pt — return value shape, and the empty-list failure mode) along with the `load_listings()` signature from `utils/data_loader.py`. I asked it to implement the function in `tools.py` without changing the signature. The generated code was correct but initially filtered by size *after* scoring instead of before, which would have returned off-size items with high scores. I moved the size and price filters ahead of the scoring loop to match the spec, then tested with three queries (one with results, one returning nothing, one with a price ceiling).

**Instance 2 — Implementing `run_agent()` and the planning loop:**

I gave Claude the full Mermaid architecture diagram from `planning.md` and the Planning Loop and State Management sections (including the session key table). I asked it to implement `run_agent()` in `agent.py`. The generated code was structurally correct — it branched on empty results and stored values in the session dict by the right key names. One thing I changed: the original generated code used a bare `except Exception: pass` in the query parse fallback, which would have silently swallowed any error including a missing API key. I replaced it with a fallback that still returns a usable `parsed` dict so the loop can continue, and moved API key errors to surface at the Groq client initialization level instead.
