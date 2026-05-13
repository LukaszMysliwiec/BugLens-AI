# ARCHITECTURE.md — BugLens AI

> **Uwaga dla agentów AI:** Ten plik powinien być czytany przed każdą zmianą w kodzie.
> Opisuje decyzje architektoniczne, granice modułów i przepływ danych w projekcie.

---

## 1. Widok ogólny systemu

```
┌──────────────────────────────────────────────────────────────┐
│                   Przeglądarka (użytkownik)                   │
│              static/index.html  (vanilla JS/CSS)             │
└─────────────────────────┬────────────────────────────────────┘
                           │  POST /api/analyze
                           │  GET  /api/results/{id}
┌─────────────────────────▼────────────────────────────────────┐
│                   FastAPI  (app/main.py)                      │
│     CORS middleware, lifespan, static mount, router /api      │
└──────┬──────────────────────────────────────┬────────────────┘
       │                                      │
       ▼                                      ▼
app/api/routes.py                    app/utils/storage.py
(HTTP interface)                     (in-memory result store)
       │
       ▼
app/services/analysis_service.py
(pipeline orchestrator)
       │
   ┌───┴────────────────────────────┐
   │                                │
   ▼                                ▼
app/scanner/                   app/tests/
html_parser.py                 test_runner.py
element_extractor.py           checks/
                                    status_check.py
                                    meta_tags.py
                                    alt_attributes.py
                                    form_validation.py
                                    broken_links.py  (async)
                               │
                               ▼
                          app/ai/
                          analyzer.py
                          prompt_builder.py
                               │
                               ▼
                          app/services/scoring.py
```

---

## 2. Kluczowy przepływ danych (krok po kroku)

```
POST /api/analyze { url, use_browser }
    │
    ├─► start_analysis()  →  UUID + AnalysisResult(status=running) → storage.save()
    │                         HTTP 202 zwrócone natychmiast
    │
    └─► asyncio.create_task(run_analysis(id, url, use_browser))
              │
              │  1. fetch_and_parse(url, use_browser)
              │     ├─ validate_url(url)           ← SSRF guard (zawsze pierwsze!)
              │     ├─ [static]  httpx GET         → (BeautifulSoup, status_code)
              │     └─ [browser] Playwright chromium → (BeautifulSoup, status_code)
              │
              │  2. extract_elements(soup, base_url)
              │     └─ PageElements { title, meta_description, has_viewport_meta,
              │                       forms, inputs, buttons, links,
              │                       images_without_alt, heading_structure }
              │
              │  3. run_all_checks(elements, status_code)
              │     ├─ check_status_code(url, status_code)    [sync]
              │     ├─ check_meta_tags(elements)              [sync]
              │     ├─ check_alt_attributes(elements)         [sync]
              │     ├─ check_form_validation(elements)        [sync]
              │     └─ await check_broken_links(elements.links) [async, concurrent HEAD]
              │     └─ → list[TestResult]
              │
              │  4. await ai_analyze(elements, test_results)
              │     ├─ brak OPENAI_API_KEY → _fallback_analysis()
              │     ├─ build_user_prompt() → kompaktowy JSON (bez raw HTML)
              │     ├─ OpenAI chat.completions (gpt-4o-mini, temp=0.2, json_object)
              │     └─ → AIAnalysis { summary, insights, test_suggestions, ux_recs }
              │
              │  5. compute_score(test_results)
              │     └─ 100 - Σ(penalty per failed test) clamped [0,100]
              │         → QAScore { total, breakdown }
              │
              └─► storage.save(AnalysisResult(status=completed, ...))

GET /api/results/{id}   →  storage.get(id)  →  result.model_dump()
```

---

## 3. Moduły i ich odpowiedzialności

| Moduł | Plik | Odpowiedzialność | Nie robi |
|---|---|---|---|
| **API** | `app/api/routes.py` | Waliduje żądanie HTTP, zwraca 202 natychmiast, odpala background task | Nie wykonuje pipeline'u |
| **Orchestrator** | `app/services/analysis_service.py` | Łączy wszystkie kroki pipeline'u, obsługuje błędy bez crashu taska | Nie zawiera logiki żadnego kroku |
| **Scanner – fetch** | `app/scanner/html_parser.py` | Pobiera HTML (httpx lub Playwright), zawsze przez `validate_url` | Nie parsuje treści |
| **Scanner – extract** | `app/scanner/element_extractor.py` | Transformuje BS4 tree → `PageElements` (bez raw HTML) | Nie ocenia jakości |
| **Test runner** | `app/tests/test_runner.py` | Uruchamia wszystkie checki, zbiera wyniki; sync + async | Nie definiuje logiki checków |
| **Checki** | `app/tests/checks/*.py` | Pure functions `(wejście) → TestResult`; po jednej per plik | Żadnych side effects, klas |
| **AI** | `app/ai/analyzer.py` | Wywołuje OpenAI; parsuje JSON; fallback na każdy błąd | Nie buduje prompta |
| **Prompt builder** | `app/ai/prompt_builder.py` | Serializuje `PageElements` + `list[TestResult]` → kompaktowy JSON | Nie wywołuje API |
| **Scoring** | `app/services/scoring.py` | Deterministyczny algorytm 100 – Σ penalties; tylko `failed` liczy | Nie interpretuje wyników |
| **Storage** | `app/utils/storage.py` | In-memory dict chroniony `asyncio.Lock` | Brak persystencji po restarcie |
| **HTTP client** | `app/utils/http_client.py` | Singleton `httpx.AsyncClient` z connection pooling; zamykany w lifespan | Nie waliduje URL |
| **SSRF guard** | `app/utils/url_validator.py` | Blokuje prywatne IP, loopback, nieprawidłowe schematy | Nie buduje nowego URL |
| **Settings** | `app/utils/settings.py` | `pydantic-settings` + `.env`; jeden obiekt `settings` globalnie | |
| **Schematy** | `app/models/schemas.py` | Jedyne źródło prawdy dla wszystkich kształtów danych (Pydantic v2) | |
| **Frontend** | `static/index.html` | Vanilla JS; polling co 2s; zero zależności | |

---

## 4. Modele danych (schemas.py — jedyne źródło prawdy)

```
AnalyzeRequest          ─►  url: AnyHttpUrl, use_browser: bool
AnalyzeResponse         ─►  id, status: AnalysisStatus, message

PageElements            ─►  url, title, meta_description, meta_keywords,
                             has_viewport_meta, forms: [FormInfo],
                             inputs: [FormField], buttons: [str],
                             links: [LinkInfo],
                             images_without_alt: [str],
                             heading_structure: [str]

FormInfo                ─►  action, method, fields: [FormField]
FormField               ─►  name, input_type, required, placeholder
LinkInfo                ─►  href, text, is_external: bool

TestResult              ─►  check_name, status: TestStatus,
                             severity: Severity, description, details: dict

AIInsight               ─►  category, severity, issue, recommendation, affected_element
AIAnalysis              ─►  summary, insights: [AIInsight],
                             test_suggestions: [str], ux_recommendations: [str],
                             ai_model_used, fallback_used: bool

QAScore                 ─►  total: int [0-100], breakdown: dict[str, int]

AnalysisResult          ─►  id, url, status: AnalysisStatus,
                             page_elements, test_results, ai_analysis,
                             score, error, created_at, completed_at
```

**Enumy:**
```
Severity:       critical | high | medium | low | info
TestStatus:     passed | failed | skipped
AnalysisStatus: pending | running | completed | failed
```

---

## 5. Wzorzec dodawania nowego checku

Każdy check musi spełniać ten kontrakt (przykład: `app/tests/checks/alt_attributes.py`):

```python
# 1. Pure function — żadnych side effects, żadnych klas
def check_alt_attributes(elements: PageElements) -> TestResult:
    missing = elements.images_without_alt
    if not missing:
        return TestResult(
            check_name="Image Alt Attributes",
            status=TestStatus.passed,
            severity=Severity.info,
            description="All images have alt attributes.",
            details={"images_without_alt": []},  # details = strukturalny dict
        )
    severity = Severity.high if len(missing) > 3 else Severity.medium
    return TestResult(
        check_name="Image Alt Attributes",
        status=TestStatus.failed,
        severity=severity,
        description=f"{len(missing)} image(s) are missing alt attributes.",
        details={"images_without_alt": missing[:20]},
    )
```

Po stworzeniu pliku checku **obowiązkowo** dopisz go do `run_all_checks(...)` w `app/tests/test_runner.py`:

```python
# Sync:
results.append(check_moj_nowy_check(elements))
# Async (jeśli robi I/O):
results.append(await check_moj_nowy_async_check(elements.links))
```

---

## 6. Scoring — algorytm

```
score = 100
for result in test_results:
    if result.status == TestStatus.failed:
        score -= PENALTY[result.severity]

PENALTY = { critical: 30, high: 20, medium: 10, low: 5, info: 0 }
score = clamp(score, 0, 100)
breakdown = { check_name: -penalty }  # tylko failed z penalty > 0
```

`skipped` i `passed` → zero kary.

---

## 7. AI — kontrakt promptu

`prompt_builder.py` serializuje dane do **kompaktowego JSON** (nigdy raw HTML):

```json
{
  "page_elements": {
    "url": "...", "title": "...", "meta_description": null,
    "has_viewport_meta": false,
    "form_count": 1, "forms": [...],
    "button_count": 2, "buttons": [...],
    "link_count": 5, "external_link_count": 2,
    "images_without_alt_count": 3, "images_without_alt_sample": [...],
    "heading_structure": [...]
  },
  "test_results": [
    { "check": "Meta Tags", "status": "failed", "severity": "medium",
      "description": "...", "details": {...} }
  ]
}
```

Parametry OpenAI: `model="gpt-4o-mini"`, `temperature=0.2`, `max_tokens=800`, `response_format={"type":"json_object"}`.

Fallback na każdy wyjątek → `AIAnalysis(fallback_used=True)`.

---

## 8. Bezpieczeństwo — SSRF guard

`validate_url(url)` w `app/utils/url_validator.py` jest **obowiązkowym wywołaniem przed każdym outbound requestem** z user input:

- Blokuje schematy inne niż `http`/`https`
- Blokuje `localhost`, `0.0.0.0`, IPv6 loopback
- Rozwiązuje hostname przez DNS i blokuje adresy prywatne (RFC-1918), link-local, multicast, reserved

```python
# Wzorzec obowiązkowy przy każdym nowym żądaniu sieciowym:
safe_url = validate_url(url)
client = get_client()
response = await client.get(safe_url)
```

---

## 9. Konfiguracja (.env)

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `OPENAI_API_KEY` | `""` | Bez klucza → fallback AI bez błędu |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model OpenAI |
| `OPENAI_MAX_TOKENS` | `800` | Limit tokenów odpowiedzi |
| `HTTP_TIMEOUT` | `15.0` | Timeout httpx [s] |
| `BROWSER_TIMEOUT_MS` | `20000` | Timeout Playwright [ms] |
| `MAX_LINKS_TO_CHECK` | `20` | Limit linków w broken_links check |

---

## 10. Testy

```
app/tests/
├── test_api.py        – integracyjne (FastAPI TestClient + storage mock)
├── test_checks.py     – unit testy każdego checku z _base_elements() helper
├── test_scanner.py    – unit testy extract_elements() z inline HTML
├── test_scoring.py    – unit testy compute_score()
└── test_url_validator.py – unit testy SSRF guard
conftest.py           – fixture: TestClient (synchroniczny)
```

Fixture `_base_elements(**kwargs)` w `test_checks.py` — pattern do tworzenia `PageElements` z nadpisanymi polami:
```python
def _base_elements(**kwargs) -> PageElements:
    defaults = dict(url="https://example.com", title="Example", ...)
    defaults.update(kwargs)
    return PageElements(**defaults)
```

Uruchomienie:
```bash
pytest -v                          # wszystkie testy
pytest app/tests/test_checks.py -v # tylko checki
```

---

## 11. Stack technologiczny

| Warstwa | Technologia |
|---|---|
| Backend API | FastAPI 0.115 + Uvicorn 0.34 |
| HTTP klient | httpx 0.28 (async, singleton) |
| Browser mode | Playwright 1.52 (headless Chromium) |
| HTML parser | BeautifulSoup4 4.12 + lxml 6.1 |
| AI | OpenAI 1.82 (gpt-4o-mini) |
| Modele | Pydantic v2 2.11 |
| Storage | In-memory dict + asyncio.Lock |
| Config | pydantic-settings 2.9 + python-dotenv |
| Testy | pytest 8.3 + pytest-asyncio 0.26 + pytest-httpx 0.35 |
| Frontend | Vanilla HTML/CSS/JS (brak frameworka) |

---

## 12. ⚠️ Jakość kodu i testy — zasady bezwzględne

> Poniższe zasady obowiązują każdego agenta AI i każdego dewelopera. Nie można ich pominąć.

### Testy są obowiązkowe
- **Nowy check** → test jednostkowy w `app/tests/test_checks.py` (wzorzec: `_base_elements(**kwargs)` + asercje na `status`, `severity`, `details`).
- **Nowa funkcja utility / helper** → test jednostkowy w odpowiednim pliku testowym.
- **Nowy endpoint** → test integracyjny w `app/tests/test_api.py` z `TestClient`.
- **Zmiana modelu w `schemas.py`** → aktualizacja testów, które korzystają z danego modelu.
- Po każdej zmianie uruchom `pytest -v` i upewnij się, że wynik to **`N passed, 0 failed`**.

### Nie wolno
- ❌ Pomijać `validate_url(url)` przed jakimkolwiek requestem sieciowym z user input.
- ❌ Usuwać ani komentować istniejących testów, by "naprawić" failing build.
- ❌ Zwracać surowego HTML lub dużych bloków tekstu w `details` pola `TestResult` — tylko strukturalne dykty.
- ❌ Rejestrować checku w pliku bez dopisania go jawnie do `run_all_checks(...)` w `test_runner.py`.
- ❌ Zmieniać interfejsu enuma `Severity` / `TestStatus` / `AnalysisStatus` bez aktualizacji scoringu i testów.

### Dbałość o kod
- Każda nowa funkcja i moduł musi mieć docstring opisujący cel (wzorzec: istniejące moduły).
- Nazwy zmiennych muszą wyrażać intencję (`missing_tags`, nie `lst`).
- Brak martwego kodu — nie zostawiaj zakomentowanych bloków ani nieużywanych importów.

