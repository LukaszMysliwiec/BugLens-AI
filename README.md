# BugLens AI – Automated Web QA Analyzer

> A clean, modular MVP that scans any public URL, runs automated QA checks, and uses AI to produce actionable insights and UX recommendations.

---

## Quick Start

```bash
# 1. Clone & set up environment
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure (optional – AI analysis works without a key, but falls back to static output)
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# 3. Run
uvicorn app.main:app --reload --port 8000
# Open http://localhost:8000
```

---

## Architecture

### 1. High-Level Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        Browser (User)                     │
│               static/index.html  (vanilla JS)            │
└─────────────────────┬────────────────────────────────────┘
                       │ POST /api/analyze
                       │ GET  /api/results/{id}
┌─────────────────────▼────────────────────────────────────┐
│                  FastAPI  (app/main.py)                   │
│                  app/api/routes.py                        │
└──────┬─────────────────────────────────────┬─────────────┘
       │                                     │
       ▼                                     ▼
app/services/                          app/utils/storage.py
analysis_service.py                    (in-memory result store)
       │
  ┌────┼──────────────────────────┐
  │    │                          │
  ▼    ▼                          ▼
app/scanner/          app/tests/          app/ai/
html_parser.py        test_runner.py      analyzer.py
element_extractor.py  checks/             prompt_builder.py
                       status_check.py
                       broken_links.py
                       meta_tags.py
                       alt_attributes.py
                       form_validation.py
```

### 2. Data Flow

```
User enters URL
      │
      ▼
POST /api/analyze  →  returns {id, status: "running"}  (HTTP 202)
      │
      └─► asyncio.create_task(run_analysis(...))
                │
                ├─ 1. fetch_and_parse(url)           [httpx / Playwright]
                ├─ 2. extract_elements(soup, url)    [BeautifulSoup4]
                ├─ 3. run_all_checks(elements)       [5 QA checks]
                ├─ 4. ai_analyze(elements, results)  [OpenAI GPT-4o-mini]
                ├─ 5. compute_score(results)
                └─ 6. storage.save(result)

User polls GET /api/results/{id}  →  full JSON report
```

---

## Project Structure

```
BugLens-AI/
├── app/
│   ├── main.py                   # FastAPI app, lifespan, CORS, static mount
│   ├── api/
│   │   └── routes.py             # POST /analyze  GET /results/{id}
│   ├── services/
│   │   ├── analysis_service.py   # Pipeline orchestrator
│   │   └── scoring.py            # QA score calculation
│   ├── scanner/
│   │   ├── html_parser.py        # HTTP + Playwright page fetch
│   │   └── element_extractor.py  # DOM → PageElements struct
│   ├── tests/
│   │   ├── test_runner.py        # Runs all checks, collects results
│   │   ├── checks/
│   │   │   ├── status_check.py
│   │   │   ├── broken_links.py
│   │   │   ├── meta_tags.py
│   │   │   ├── alt_attributes.py
│   │   │   └── form_validation.py
│   │   ├── test_checks.py        # pytest – check unit tests
│   │   ├── test_scanner.py       # pytest – scanner unit tests
│   │   ├── test_scoring.py       # pytest – scoring unit tests
│   │   └── test_api.py           # pytest – API integration tests
│   ├── ai/
│   │   ├── analyzer.py           # OpenAI call + fallback
│   │   └── prompt_builder.py     # Prompt engineering + serialisation
│   ├── models/
│   │   └── schemas.py            # All Pydantic models
│   └── utils/
│       ├── http_client.py        # Shared httpx async client
│       ├── settings.py           # pydantic-settings config
│       └── storage.py            # In-memory async result store
├── static/
│   └── index.html                # Minimal dark-themed frontend
├── conftest.py                   # pytest shared fixtures
├── requirements.txt
├── .env.example
└── .gitignore
```

**Module responsibilities:**

| Module | Responsibility |
|--------|---------------|
| `api/routes.py` | HTTP interface – validates input, returns 202 immediately, delegates to service |
| `services/analysis_service.py` | Orchestrates the pipeline; handles errors without crashing the task |
| `services/scoring.py` | Converts failed test severities into a 0–100 score |
| `scanner/html_parser.py` | Fetches pages via httpx (static) or Playwright (browser mode) |
| `scanner/element_extractor.py` | Walks the BS4 tree; extracts forms, links, images, headings |
| `tests/test_runner.py` | Calls every check, collects `TestResult` list |
| `tests/checks/*` | One file per check – Strategy pattern, pure functions |
| `ai/prompt_builder.py` | Serialises data to compact JSON; constructs system + user prompts |
| `ai/analyzer.py` | Calls OpenAI; parses response; graceful fallback on failure |
| `models/schemas.py` | Single source of truth for all data shapes (Pydantic v2) |
| `utils/storage.py` | Async-safe in-memory store (swap for Redis in production) |

---

## API Design

### `POST /api/analyze`

Accepts a URL and returns an analysis ID immediately (non-blocking).

**Request:**
```json
{
  "url": "https://example.com",
  "use_browser": false
}
```

**Response (HTTP 202):**
```json
{
  "id": "43a1a838-c288-40f4-a358-4b6d8fb7c73",
  "status": "running",
  "message": "Analysis started. Poll GET /results/{id} for results."
}
```

### `GET /api/results/{id}`

Poll until `status` is `"completed"` or `"failed"`.

**Response (completed):**
```json
{
  "id": "43a1a838-c288-40f4-a358-4b6d8fb7c73",
  "url": "https://example.com",
  "status": "completed",
  "score": { "total": 75, "breakdown": { "Image Alt Attributes": -10, "Meta Tags": -10, "Broken Links": -5 } },
  "page_elements": {
    "url": "https://example.com",
    "title": "Example Domain",
    "meta_description": null,
    "has_viewport_meta": false,
    "forms": [],
    "inputs": [],
    "buttons": [],
    "links": [{ "href": "https://www.iana.org/domains/reserved", "text": "More information...", "is_external": true }],
    "images_without_alt": [],
    "heading_structure": ["h1: Example Domain"]
  },
  "test_results": [
    { "check_name": "HTTP Status Code", "status": "passed", "severity": "info", "description": "Page returned HTTP 200 – OK.", "details": {} },
    { "check_name": "Meta Tags", "status": "failed", "severity": "medium", "description": "2 required meta element(s) missing.", "details": { "missing": ["meta[name=\"description\"]", "meta[name=\"viewport\"]"] } },
    { "check_name": "Image Alt Attributes", "status": "passed", "severity": "info", "description": "All images have alt attributes.", "details": {} },
    { "check_name": "Form Validation", "status": "skipped", "severity": "info", "description": "No forms detected on the page.", "details": {} },
    { "check_name": "Broken Links", "status": "passed", "severity": "info", "description": "All 1 sampled links returned valid responses.", "details": {} }
  ],
  "ai_analysis": {
    "summary": "The page is reachable and structurally minimal. Key SEO and mobile-friendliness meta tags are missing, which will reduce search ranking and hurt mobile UX.",
    "insights": [
      {
        "category": "seo",
        "severity": "medium",
        "issue": "meta[name='description'] is absent. Search engines will generate their own snippet, which is typically lower quality.",
        "recommendation": "Add a concise 150-160 character meta description that accurately summarises the page content.",
        "affected_element": "head > meta[name='description']"
      },
      {
        "category": "ux",
        "severity": "medium",
        "issue": "meta[name='viewport'] is missing. The page will not scale correctly on mobile devices.",
        "recommendation": "Add <meta name='viewport' content='width=device-width, initial-scale=1'> inside <head>.",
        "affected_element": "head > meta[name='viewport']"
      }
    ],
    "test_suggestions": [
      "Write a Playwright test that checks page rendering on a 375px-wide viewport.",
      "Add a test that validates the Open Graph tags (og:title, og:description) are present."
    ],
    "ux_recommendations": [
      "Provide a descriptive page title that includes the brand name.",
      "Ensure all interactive elements are keyboard-focusable."
    ],
    "ai_model_used": "gpt-4o-mini",
    "fallback_used": false
  },
  "created_at": "2026-05-13T12:00:00Z",
  "completed_at": "2026-05-13T12:00:04Z"
}
```

---

## Scanner Module

`html_parser.py` supports two strategies:

- **Static** (default): `httpx` async GET with connection pooling and a realistic User-Agent.  Fast, handles most server-rendered pages.
- **Browser** (`use_browser=true`): Playwright headless Chromium, waits for `networkidle`.  Use when the page requires JavaScript to render content.

`element_extractor.py` walks the BS4 tree and populates a `PageElements` struct:

| Extracted data | How |
|---|---|
| Title, meta description, viewport meta | `soup.find("title")` / `soup.find("meta", attrs={...})` |
| Forms | All `<form>` elements; input fields classified by type; submit/hidden/button inputs excluded |
| Standalone inputs | `<input>` / `<select>` / `<textarea>` outside any `<form>` |
| Buttons | `<button>` text + `<input type=submit/button>` values |
| Links | All `<a href>` excluding `#`, `javascript:`, `mailto:`, `tel:`; resolved to absolute URLs; `is_external` flag set |
| Images without alt | `<img>` missing `alt` or with empty `alt` |
| Heading structure | `h1`–`h6` text, capped at first 80 chars |

---

## Testing Engine

Each check in `app/tests/checks/` follows the **Strategy pattern**: a single function accepts the minimum required inputs and returns a `TestResult`.

| Check | Input | What it tests |
|---|---|---|
| `status_check` | `url`, `status_code` | 2xx = pass; 3xx/4xx = high; 5xx = critical |
| `broken_links` | `links: list[LinkInfo]` | Concurrent HEAD requests for up to 20 links |
| `meta_tags` | `PageElements` | Presence of `<title>`, `meta description`, `meta viewport` |
| `alt_attributes` | `PageElements` | Images missing `alt`; ≤3 = medium, >3 = high |
| `form_validation` | `PageElements` | Empty forms; nameless fields; password over HTTP |

`TestResult` fields:
- `check_name` – human-readable identifier
- `status` – `passed` / `failed` / `skipped`
- `severity` – `critical` / `high` / `medium` / `low` / `info`
- `description` – one-line summary
- `details` – structured dict (never a wall of text)

---

## AI Module

### Input to AI

The prompt builder serialises `PageElements` and `list[TestResult]` to a **compact JSON payload** (never raw HTML):

```json
{
  "page_elements": {
    "url": "...", "title": "...", "meta_description": null,
    "form_count": 1, "forms": [...], "images_without_alt_count": 3, ...
  },
  "test_results": [
    { "check": "Meta Tags", "status": "failed", "severity": "medium", "description": "...", "details": {...} }
  ]
}
```

### Prompt Engineering Strategy

**System prompt** (constant, high quality):
- Sets the persona as "senior QA engineer and web accessibility specialist"
- Defines a strict JSON output schema
- Instructs the model: *"Base every insight ONLY on the data provided"*
- Caps lists (max 8 insights, 5 suggestions, 5 UX recommendations)

**User prompt**: structured JSON payload built from real test data.

**Anti-hallucination measures:**
- `temperature=0.2` for near-deterministic output
- `response_format={"type": "json_object"}` forces valid JSON
- Every insight must reference a data point from the input
- Fallback to static output on any failure

### Fallback Strategy

If `OPENAI_API_KEY` is not set, or any API error occurs:
1. Log the error
2. Return a `AIAnalysis` with `fallback_used=True`
3. The `summary` directs users to the automated test results
4. The rest of the pipeline continues unaffected

---

## Scoring System

Starting score: **100**

Deductions applied for each `TestStatus.failed` result:

| Severity | Penalty |
|---|---|
| critical | -30 |
| high | -20 |
| medium | -10 |
| low | -5 |
| info | 0 |

Score is clamped to `[0, 100]`.  `skipped` results carry no penalty.

---

## Execution Flow

```
1. User enters URL → clicks Analyze
2. POST /api/analyze → HTTP 202 + analysis ID
3. asyncio background task:
   a. fetch_and_parse(url) → BeautifulSoup tree + status_code
   b. extract_elements(soup) → PageElements struct
   c. run_all_checks(elements, status_code):
      - status_check (sync)
      - meta_tags (sync)
      - alt_attributes (sync)
      - form_validation (sync)
      - broken_links (async, concurrent HEAD requests)
   d. ai_analyze(elements, test_results) → AIAnalysis
   e. compute_score(test_results) → QAScore
   f. storage.save(completed_result)
4. Frontend polls GET /api/results/{id} every 2s
5. On status=completed → render score, tests, insights, UX recs
```

---

## AI Best Practices

| Practice | Implementation |
|---|---|
| **Grounding** | AI only sees structured test data, not raw HTML; every insight must reference a concrete finding |
| **Avoiding generic output** | System prompt explicitly says *"Do NOT repeat the same recommendation"*; input is URL-specific |
| **Explainability** | Each insight has `category`, `severity`, `affected_element` fields |
| **Token efficiency** | Compact JSON payload; list caps in prompt; `max_tokens=800` |
| **Determinism** | `temperature=0.2`; `response_format=json_object` |
| **Fallback** | Full graceful degradation – app works without an API key |

---

## Running Tests

```bash
pytest -v
# 43 tests across: checks, scanner, scoring, API integration
```

---

## Technology Stack

| Component | Technology |
|---|---|
| Backend API | FastAPI + Uvicorn |
| Page fetching | httpx (static), Playwright (browser mode) |
| HTML parsing | BeautifulSoup4 + lxml |
| AI analysis | OpenAI GPT-4o-mini (configurable) |
| Data models | Pydantic v2 |
| Result storage | In-memory dict (async-safe) |
| Frontend | Vanilla HTML/CSS/JS (no framework) |
| Tests | pytest + pytest-asyncio |
