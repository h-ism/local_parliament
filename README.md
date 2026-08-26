# local parliament

Tooling to collect transcripts of Japanese prefectural assembly (都道府県議会) proceedings
into a corpus for research.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Usage

```bash
uv run pt sites                       # list configured assembly sites
uv run pt scrape tokyo --limit 5      # collect into data/<prefecture>.jsonl
uv run pt stats data/東京都.jsonl      # summarise a collected corpus
```

### Adding a prefecture

Sites are configuration, not code. Copy the template and fill in the selectors:

```bash
cp src/prefectural_transcripts/sites/_example.toml \
   src/prefectural_transcripts/sites/tokyo.toml
```

`pt inspect` fetches a page (through the cache) so you can work out selectors
against the real markup:

```bash
uv run pt inspect 'https://…/search?year=2025'
uv run pt inspect 'https://…/search?year=2025' --selector 'table.result tr'
```

Then check the result on a single meeting before running the full crawl:

```bash
uv run pt scrape tokyo --limit 1
```

## Output

One JSONL file per prefecture, one meeting per line — see `Meeting` in
`src/prefectural_transcripts/models.py`. Re-running a scrape resumes: meetings
already in the file are skipped, and every fetched page is cached under `cache/`,
so tuning selectors costs no extra requests.

## Crawling politely

These are small public-sector servers publishing public records. Defaults are
deliberately conservative — 2 seconds between requests to a host, `robots.txt`
and `Crawl-delay` respected, all responses cached. Set a real contact address so
site operators can reach you:

```bash
export PT_CONTACT="you@university.example.ac.jp"
```

Other knobs: `PT_MIN_INTERVAL`, `PT_TIMEOUT`, `PT_MAX_RETRIES`, `PT_DATA_ROOT`.

## Development

```bash
uv run pytest          # tests (all offline)
uv run ruff check .
uv run ruff format .
uv run mypy
```
