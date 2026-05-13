# AGENTS.md

## ⚠️ Zawsze czytaj przed zmianami w kodzie
- **`ARCHITECTURE.md`** — pełna mapa architektury systemu: moduły, przepływ danych, modele, SSRF guard, scoring, AI prompt, testy.  
  Musisz go przeczytać zanim wprowadzisz jakąkolwiek zmianę w kodzie.

## ⚠️ Jakość kodu i testy są obowiązkowe — nie można ich pominąć
- **Każda zmiana w logice musi być pokryta testem.** Nowy check → test w `app/tests/test_checks.py`. Nowa funkcja utility → test jednostkowy. Nowy endpoint → test w `app/tests/test_api.py`.
- **Po każdej zmianie uruchom testy lokalnie** (`pytest -v`) i upewnij się, że wynik to `N passed, 0 failed`. Nie zgłaszaj zmiany jako gotowej, jeśli testy nie przechodzą.
- **Nie usuwaj ani nie pomijaj istniejących testów** — każdy test dokumentuje oczekiwane zachowanie systemu. Jeśli test "przeszkadza", to sygnał, że zmiana narusza kontrakt.
- **Dbaj o czytelność kodu:** docstringi przy nowych funkcjach/modułach, nazwy zmiennych mówiące o intencji, brak martwego kodu.
- **Nie łam istniejących kontraktów** — `TestResult`, `PageElements`, `AnalysisResult` są używane we wszystkich warstwach i w testach. Zmiana pola w modelu wymaga aktualizacji testów, serializacji AI prompt i wszystkich wywołań.

---

## Cel projektu i architektura
- `BugLens-AI` to asynchroniczny pipeline QA stron WWW: skanowanie HTML -> checki -> analiza AI -> scoring -> zapis wyniku.
- Wejscie HTTP jest w `app/api/routes.py` (`POST /api/analyze`, `GET /api/results/{id}`), aplikacja i statyczny frontend w `app/main.py`.
- Orkiestracja calego przeplywu jest skupiona w `app/services/analysis_service.py` (`start_analysis`, `run_analysis`).
- Granica odpowiedzialnosci jest czytelna: `scanner/` zbiera dane, `tests/checks/` ocenia, `ai/` tworzy insighty, `services/scoring.py` liczy wynik.
- Dane miedzy modulami sa przekazywane przez modele Pydantic z `app/models/schemas.py` (to jedyne zrodlo ksztaltu payloadow).

## Kluczowy przeplyw danych
- `POST /api/analyze` zapisuje rekord ze statusem `running` i odpala `asyncio.create_task(run_analysis(...))`.
- `run_analysis(...)` wykonuje kroki w tej kolejnosci: `fetch_and_parse` -> `extract_elements` -> `run_all_checks` -> `ai.analyze` -> `compute_score` -> `storage.save`.
- Wyniki sa pollowane przez `GET /api/results/{id}`; endpoint zwraca `AnalysisResult.model_dump()`.
- Storage jest in-memory (`app/utils/storage.py`) z `asyncio.Lock`; testy i runtime zakladaja brak trwalosci po restarcie.

## Wzorce i konwencje specyficzne dla repo
- Kazdy check w `app/tests/checks/*.py` zwraca `TestResult` i jest funkcja (bez klas, bez side effects).
- `run_all_checks` w `app/tests/test_runner.py` uruchamia checki sync od razu, a I/O check (`broken_links`) async.
- `details` w `TestResult` jest strukturalnym slownikiem (listy/liczniki), nie dlugim tekstem.
- Severity/Status sa enumami (`Severity`, `TestStatus`, `AnalysisStatus`) i na nich opiera sie logika scoringu.
- Scoring jest deterministyczny: tylko `failed` odejmuje punkty; mapowanie kar jest w `app/services/scoring.py`.

## Integracje i punkty zewnetrzne
- HTTP klient wspoldzielony (`app/utils/http_client.py`), zamykany w lifespan FastAPI (`close_client` w `app/main.py`).
- Skaner ma tryb statyczny i browserowy (`app/scanner/html_parser.py`); browser mode moze fallbackowac do trybu static.
- AI (`app/ai/analyzer.py`) korzysta z OpenAI tylko gdy `OPENAI_API_KEY` jest ustawiony; inaczej zwraca kontrolowany fallback.
- Prompt AI budowany jest w `app/ai/prompt_builder.py` z kompaktowego JSON (bez raw HTML), co ogranicza halucynacje i rozmiar tokenow.
- Kazdy outbound URL przechodzi przez SSRF guard `validate_url` (`app/utils/url_validator.py`).

## Workflow developerski (sprawdzone na kodzie)
- Konfiguracja zaleznosci: `pip install -r requirements.txt` (brak pakietow blokuje importy, np. `pydantic_settings`).
- Uruchomienie API lokalnie: `uvicorn app.main:app --reload --port 8000`.
- Uruchomienie przez Docker: `docker compose up --build` (aplikacja dostępna na `http://localhost:8000`).
- Pelny zestaw testow: `pytest -v`.
- Szybkie uruchomienie wybranego modulu: `pytest app/tests/test_api.py -v`.

## Co zmieniac ostroznie
- Nie omijaj `validate_url(...)` przy nowych requestach sieciowych (to kluczowe zabezpieczenie SSRF).
- Przy dodawaniu nowych checkow utrzymuj kontrakt `TestResult` + dopisz je jawnie do `run_all_checks(...)`.
- Przy zmianach modeli aktualizuj jednoczesnie serializacje promptu AI i testy, bo sa silnie sprzezone przez `schemas.py`.
- Pamietaj, ze background task i in-memory storage oznaczaja eventual consistency: wynik moze byc chwilowo tylko `running`.

