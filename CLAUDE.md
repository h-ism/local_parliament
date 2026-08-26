# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Collects transcripts of Japanese prefectural assembly (都道府県議会) proceedings into a
JSONL corpus for research.

## Workflow

- Never write code directly on `main`. Create a branch for any code change before committing.
- Record each branch of work in `LOG.md` (newest first): what changed, why, and what was verified.

## Commands

The project is uv-managed; everything runs through `uv run`.

```bash
uv sync                       # create .venv and install
uv run pytest                 # full suite (offline — no test touches the network)
uv run pytest tests/test_dates.py::test_parses_known_forms   # single test
uv run ruff check . && uv run ruff format .
uv run mypy                   # strict; must stay clean
uv run pt --help              # the CLI
uv run pt export data/<pref>.jsonl   # JSONL corpus -> CSV (one row per speech)
```

## Architecture

The central idea: **a prefecture is a TOML config, not a Python module.** Most
assemblies publish through one of a few vendor 会議録検索システム products that share
the same page shape — a paginated result list linking to per-sitting detail pages —
and differ only in CSS selectors. So `GenericScraper` is driven entirely by a
`SiteConfig`, and adding a prefecture means adding `sites/<name>.toml`. Reach for a
new `BaseScraper` subclass only when a site genuinely cannot be expressed as selectors.

Flow: `sites/*.toml` → `SiteConfig` → `GenericScraper` → `PoliteClient` (fetch) →
`Meeting` models → `TranscriptStore` (JSONL).

Modules under `src/prefectural_transcripts/`:

- `http.py` — `PoliteClient`. Per-host rate limiting, robots.txt + `Crawl-delay`,
  retries honouring `Retry-After`, and a disk cache of every response body.
  Also `sniff_encoding`: many of these pages are Shift_JIS/EUC-JP and declare it
  only in a `<meta>` tag, or are proxied with a wrong HTTP `charset=` — so the meta
  tag is trusted over the header, with charset-normalizer as the fallback.
- `scrapers/base.py` — `BaseScraper` splits listing (`list_meetings` → cheap
  `MeetingRef`s) from fetching (`parse_meeting`). That split is what makes crawls
  resumable, date-filterable, and cappable without the listing logic knowing about
  transcripts. `scrape()` applies the date filter twice: once on the listing date,
  again after parsing when the real date is known.
- `scrapers/generic.py` — the config-driven scraper and the `SiteConfig` dataclasses
  that mirror the TOML schema.
- `dates.py` — 和暦 parsing (`令和7年6月10日`, `令和元年`, `R7.6.10`) plus western forms.
  Assembly pages almost never use ISO dates; always parse through here.
- `models.py` — `Speech` / `MeetingRef` / `Meeting`. Note `datetime` is imported as
  `dt` because both models have a field named `date`, which would otherwise shadow
  the type inside the class body and break pydantic's annotation evaluation.
- `storage.py` — JSONL writer, one file per prefecture; `seen_keys()` drives resume.
  `SpeechCsvWriter` / `write_csv` render the same records as a flat CSV (one row
  per speech) for analysis; JSONL stays canonical.

## Conventions

- **Crawl politely.** Defaults (2s per host, robots respected, everything cached)
  are a deliberate choice about small public-sector servers, not a placeholder.
  Don't lower them to make a run faster.
- **Don't invent selectors or URLs.** `sites/` ships only `_example.toml`; no real
  assembly site has been verified yet. Work them out against live markup with
  `uv run pt inspect <url> --selector <css>`, then confirm with `pt scrape <name> --limit 1`.
- Tests use `FakeClient` and inline HTML fixtures from `tests/conftest.py`; keep the
  suite offline.
- `data/` and `cache/` are gitignored — scraped output is data, not source.
