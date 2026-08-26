# Development log

Newest first. One entry per branch of work.

## 2026-08-26 — Hokkaido survey + CSV output (`feat/hokkaido-2025`)

Asked to collect 北海道 for 2025 from
<https://www.gikai.pref.hokkaido.lg.jp/kaigiroku/>, and to store the records as
CSV. The CSV half is done; the Hokkaido half is blocked, and the survey is
written up rather than guessed around.

**Added**

- `storage.py` — `SpeechCsvWriter` (append-as-you-go, one file per prefecture,
  sibling of the JSONL) and `write_csv()` (whole corpus in one pass). One row per
  speech, meeting-level fields repeated on each row, utf-8-sig so Excel reads
  Japanese correctly. A meeting with no speeches still gets a row with blank
  speech columns — a sitting whose selectors produced nothing should be visible
  in the table, not absent from it.
- `cli.py` — `pt scrape --csv` writes both files as records arrive, so an
  interrupted run leaves them consistent; `pt export <jsonl>` rebuilds the CSV
  from the canonical JSONL (which is what a resumed run needs, since `--csv`
  appends only that run's meetings).
- `docs/hokkaido.md` — the site survey, with a draft TOML.
- `docs/hokkaido-inquiry.md` — a Japanese draft of the access request to
  議事課, since that was the route chosen over overriding robots.
- 5 tests covering row-per-speech, embedded newlines/commas, empty meetings,
  append-without-duplicate-header, and JSONL/CSV filename pairing.

**Hokkaido: why there is still no `sites/hokkaido.toml`**

The URL we were given is a portal, not a search system. It leads to two places:

- **会議録データベース** (`pref-hokkaido.gijiroku.com/voices/`) — the real corpus,
  本会議 back to 昭和46年, HTML. Navigation is plain GET, but every result list and
  transcript page is served from `/voices/cgi/voiweb.exe` inside an `<iframe>`,
  and that host's `robots.txt` has `User-agent: * / Disallow: /voices/cgi/`.
  `PoliteClient` refuses those URLs, and `GenericScraper` does not follow
  iframes in the first place.
- **会議録（速報）** (`/kaigiroku/kaigiroku_sokuhou/`) — PDF only, and by design
  temporary: it holds sittings whose official minutes have not landed in the
  database yet. It has no 2025 本会議 at all.

So 2025 本会議 is not reachable without either an access arrangement with the
assembly or a deliberate `PT_RESPECT_ROBOTS=0`, which is a research-owner
decision and contradicts the crawling convention in CLAUDE.md. Rather than ship
a config with invented selectors — the pages that would define them are exactly
the ones robots.txt puts off-limits, so nothing could be verified — the draft
sits in `docs/hokkaido.md` with the verified parts (start URL derived from the
令和7年 iframe, `KGTP`/`KTYP` parameters, the 和暦 date forms) filled in and the
two selector blocks marked TODO.

**Verified**

`ruff check`, `ruff format --check`, `mypy --strict` and `pytest` (34 passed)
clean. End-to-end: `pt scrape --csv` against a local fixture server produced
matching JSONL and CSV (2 meetings, 4 speech rows, 和暦 dates parsed, header
written once); `pt export` rebuilt the same 4 rows from the JSONL; a second run
resumed, fetched nothing new, and printed the note about `pt export`. Every
Hokkaido URL, query parameter and robots rule in the survey was checked against
the live site with single manual requests; nothing under `/voices/cgi/` was
fetched.

**Not done yet**

Hokkaido itself. The access route chosen is to ask the assembly first, so the
next step is sending `docs/hokkaido-inquiry.md` (fill in the `{ }` placeholders)
and waiting; the draft config stays out of `sites/` until the reply decides
whether we get a bulk export or a conditional crawl.

## 2026-08-26 — Scraping toolkit scaffold (`feat/scraping-setup`)

First code in the repo. Set up a uv-managed Python package and the scraping
infrastructure for collecting prefectural assembly minutes.

**Added**

- `pyproject.toml` / `uv.lock` — uv project, Python ≥3.11, `pt` console script.
  Runtime deps: httpx, beautifulsoup4, lxml, charset-normalizer, pydantic, typer.
  Dev: pytest, ruff, mypy (strict).
- `http.py` — `PoliteClient`: per-host rate limiting, robots.txt (incl.
  `Crawl-delay`), retries honouring `Retry-After`, and an on-disk response cache.
  Plus `sniff_encoding`, which prefers the `<meta charset>` over the HTTP header
  because these sites are commonly proxied with a wrong `charset=`.
- `dates.py` — 和暦 parsing (令和/平成/昭和/大正/明治, `元年`, `R7.6.10`) and western forms.
- `models.py` — `Speech` / `MeetingRef` / `Meeting` pydantic models.
- `storage.py` — JSONL corpus writer, one file per prefecture, with `seen_keys()`
  for resuming an interrupted run.
- `scrapers/` — `BaseScraper` (list/parse split so crawls can resume and be
  date-filtered) and `GenericScraper`, driven entirely by a TOML site config.
- `sites/_example.toml` — annotated template; adding a prefecture is a config
  file, not a new module.
- `cli.py` — `pt sites`, `pt scrape`, `pt inspect` (selector development),
  `pt stats`.
- 29 tests, all offline via a fake client and local HTML fixtures.

**Decisions**

- *Config-driven scrapers over per-prefecture Python.* Most assemblies use one of
  a few vendor 会議録検索システム products with the same page shape and different
  selectors, so the variation belongs in data.
- *No real site configs shipped.* Selectors have not been verified against any
  live assembly site, and guessing them would produce code that looks working and
  is not. `sites/` contains only the template.
- *Defaults are slow on purpose* — 2s between requests to a host, robots.txt
  respected, everything cached — because these are small public-sector servers.
- *JSONL over a database.* Downstream analysis wants to stream the corpus, and a
  partial run still leaves a valid file.

**Verified**

`ruff check`, `ruff format --check`, `mypy --strict` and `pytest` (29 passed) all
clean. End-to-end run against a local Shift_JIS fixture server: index paginated,
dates parsed from 和暦, speeches extracted with speaker/role, JSONL written and
read back by `pt stats`; a second run correctly resumed and made no new requests.

**Not done yet**

No real prefecture is configured. Next step is picking a target assembly, using
`pt inspect` to work out its selectors, and adding `sites/<name>.toml`.
