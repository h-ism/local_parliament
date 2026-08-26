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
  that mirror the TOML schema. Two escape hatches for markup CSS cannot express:
  `detail.speech_split` (regex on the 「○発言者」 convention, for transcripts with no
  per-speech elements) and `detail.patterns` (regex per field, for legacy tables
  that label cells by text).
- `dates.py` — 和暦 parsing (`令和7年6月10日`, `令和元年`, `R7.6.10`), western forms, and
  Domino's month-first `06/23/2025`.
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
- **Don't invent selectors or URLs.** A config goes into `sites/` only once its
  selectors have been checked against the real markup. Work them out with
  `uv run pt inspect <url> --selector <css>`, then confirm with
  `pt scrape <name> --limit 1`. Drafts for sites we may not crawl yet live in
  `docs/`, not in `sites/`, so `pt sites` never lists something that cannot run.
- Tests use `FakeClient` and inline HTML fixtures from `tests/conftest.py`; keep the
  suite offline.
- `data/` and `cache/` are gitignored — scraped output is data, not source.

## Where this stands (updated 2026-08-26)

Read `docs/prefecture-survey.md` first — it maps all 47 assemblies to their
minutes system, the `robots.txt` verdict, and whether the pages are scrapeable.
Per-site detail is in `docs/<prefecture>.md`; drafted letters are in
`docs/inquiries/` with a README index.

**Collectable today**

- **静岡** — `sites/shizuoka.toml`, the only working config. 2025 is collected.
  The full archive (平成11年 onwards) waits on a question about the site's
  `<meta name="robots" content="none">`; see `docs/shizuoka.md`.
- **三重・兵庫・愛媛** (`kensakusystem.jp`) — no robots.txt, server-rendered CGI,
  nothing written yet. The likeliest next config, and `speech_split` / `patterns`
  should carry over.

**Blocked, and why it is not a scraping problem**

24 assemblies forbid crawling in `robots.txt` (DB-Search's blanket `Disallow: /`,
gijiroku VOICES' CGI directory). No amount of selector work changes that; the way
through is `docs/inquiries/`. Don't set `PT_RESPECT_ROBOTS=0` to get around it —
that is the researcher's call, not ours, and it contradicts the politeness
convention above.

**The single highest-value open task**

18 prefectures sit on SSP (`ssp.kaigiroku.net`), whose robots.txt *allows*
`/tenant/`. They are unreachable only because the pages are a JavaScript app whose
data endpoint is defined in `/tenant/js/release/config.js` — one of the four
disallowed directories, so it has not been read. Getting that endpoint another way
(a browser's network tab, or asking the vendor) unlocks 18 assemblies through one
implementation. See `docs/inquiries/ssp-vendor.md`.

## Things that will bite again

Learned from 静岡; expect them on other sites rather than treating them as local
quirks.

- **Encoding lies, and fails silently.** Those pages declare `charset=utf-8` in a
  meta tag, send `Shift_JIS` in the header, and contain cp932. Base Shift_JIS
  cannot decode the NEC/IBM characters ordinary names use (河原﨑, 髙梨), and the
  failure surfaces as *plausible garbage*, not an exception — it was caught only
  because 8 documents parsed to zero speeches. `sniff_encoding` maps Shift_JIS to
  cp932 for this reason. When a parse comes back suspiciously empty, check the
  decoded text before touching the selectors.
- **One label is rarely enough.** 静岡 labels the date 質問日 on question
  documents and 発言日 on report documents; matching one left 60 of 113 records
  undated. Check a sample of *each document type*, not just the interesting one.
- **Structure can be coincidence.** 「○出　席　議　員（六十七名）」 is an attendance
  roster with the exact shape of a speech marker 「○知事（鈴木康友君）」. Requiring
  the 「君」 honorific separated them. Verify a split rule against a sample and
  count what it catches.
- **A date filter is not a crawl limit.** `--since/--until` are applied after a
  page is fetched, so on an index carrying no dates they save nothing. Narrow
  `--start-url` instead.
- **Check `robots.txt` before writing any config.** It is one request and it
  decides whether the rest of the work is worth doing.

## Working notes

`JOURNAL.md` (untracked, gitignored) holds the running diary: decisions, dead
ends, mistakes, and contacts not yet verified. `LOG.md` stays the tracked record,
newest first, one entry per branch.
