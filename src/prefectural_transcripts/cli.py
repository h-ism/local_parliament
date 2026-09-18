"""Command line entry point (`uv run pt ...`)."""

from __future__ import annotations

import logging
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from prefectural_transcripts.config import Settings
from prefectural_transcripts.http import PoliteClient, current_time
from prefectural_transcripts.importers.dbsearch import DbSearchImporter, find_downloads
from prefectural_transcripts.scrapers import (
    GenericScraper,
    available_sites,
    load_scraper,
)
from prefectural_transcripts.storage import (
    SpeechCsvWriter,
    TranscriptStore,
    read_meetings,
    write_csv,
)

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Collect transcripts of Japanese prefectural assembly proceedings.",
)


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)-7s %(name)s: %(message)s",
    )


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise typer.BadParameter(f"expected YYYY-MM-DD, got {value!r}") from exc


@app.command("sites")
def list_sites() -> None:
    """List the configured assembly sites."""
    sites = available_sites()
    if not sites:
        typer.echo("No sites configured. Copy sites/_example.toml to get started.")
        raise typer.Exit(1)
    for name, path in sites.items():
        typer.echo(f"{name:<20} {path}")


@app.command()
def scrape(
    name: Annotated[str, typer.Argument(help="Site name, as shown by `pt sites`.")],
    since: Annotated[str | None, typer.Option(help="Only meetings on/after YYYY-MM-DD.")] = None,
    until: Annotated[str | None, typer.Option(help="Only meetings on/before YYYY-MM-DD.")] = None,
    limit: Annotated[int | None, typer.Option(help="Stop after N meetings.")] = None,
    start_url: Annotated[
        list[str] | None,
        typer.Option(
            "--start-url",
            help="Index page to crawl instead of the config's. Repeatable.",
        ),
    ] = None,
    out: Annotated[Path | None, typer.Option(help="Output directory. Default: ./data")] = None,
    delay: Annotated[float | None, typer.Option(help="Min seconds between requests.")] = None,
    resume: Annotated[bool, typer.Option(help="Skip meetings already in the output file.")] = True,
    csv_out: Annotated[
        bool,
        typer.Option("--csv", help="Also write data/<prefecture>.csv, one row per speech."),
    ] = False,
    no_cache: Annotated[bool, typer.Option("--no-cache", help="Bypass the HTTP cache.")] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Scrape one site into data/<prefecture>.jsonl."""
    _configure_logging(verbose)
    settings = Settings()
    if out:
        settings.data_dir = out
    if delay is not None:
        settings.min_interval = delay
    if no_cache:
        settings.use_cache = False

    scraper = load_scraper(name)
    # Said before anything is fetched, rather than as the first request's
    # refusal: a run started at the wrong hour should say so in one line.
    if (window := scraper.fetch_window) and not window.allows(current_time()):
        typer.echo(
            f"{name} may only be fetched {window.describe()} — "
            f"next window opens {window.next_open(current_time()):%Y-%m-%d %H:%M %Z}."
        )
        typer.echo(f"Reason ({window.decided_on}): {window.reason}")
        raise typer.Exit(1)
    if start_url:
        # Narrowing the entry points is the only way to scope a crawl on a site
        # whose index carries no dates: --since/--until can only filter after a
        # page has been fetched, which is too late to save the request.
        if not isinstance(scraper, GenericScraper):
            raise typer.BadParameter(
                f"--start-url applies to selector-driven sites; {name} walks its own tree. "
                "Scope it from the config instead."
            )
        scraper.config.start_urls = list(start_url)
        typer.echo(f"Crawling {len(start_url)} given start URL(s) instead of the configured ones.")
    written = 0
    with ExitStack() as stack:
        store = stack.enter_context(TranscriptStore(settings.data_dir, scraper.prefecture))
        # The CSV is a second view of the same records, written as they arrive so
        # an interrupted run still leaves both files consistent with each other.
        csv_writer = (
            stack.enter_context(SpeechCsvWriter(settings.data_dir, scraper.prefecture))
            if csv_out
            else None
        )
        skip = store.seen_keys() if resume else set()
        if skip:
            typer.echo(f"Resuming: {len(skip)} meetings already collected.")
            if csv_writer:
                typer.echo(
                    "Note: --csv only appends the new meetings; `pt export` rebuilds it all."
                )
        client = stack.enter_context(PoliteClient(settings, robots_exempt=scraper.robots_exempt))
        for meeting in scraper.scrape(
            client,
            since=_parse_date(since),
            until=_parse_date(until),
            limit=limit,
            skip=skip,
        ):
            store.write(meeting)
            if csv_writer:
                csv_writer.write(meeting)
            written += 1
            typer.echo(f"[{written}] {meeting.date} {meeting.title or meeting.url}")
    typer.echo(f"Wrote {written} meetings to {store.path}")
    for line in scraper.report():
        typer.echo(line)
    if csv_out:
        typer.echo(f"CSV written to {settings.data_dir / (store.path.stem + '.csv')}")


@app.command()
def inspect(
    url: Annotated[str, typer.Argument(help="Page to fetch.")],
    selector: Annotated[
        str | None, typer.Option(help="CSS selector to test against the page.")
    ] = None,
    chars: Annotated[int, typer.Option(help="How much of the page to print.")] = 3000,
    as_site: Annotated[
        str | None,
        typer.Option(
            "--as-site",
            help="Borrow this site's robots.txt exemption, if it has one.",
        ),
    ] = None,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Fetch one page (through the cache) to help work out selectors."""
    _configure_logging(verbose)
    # Working selectors out with `inspect` is the documented first step, so it
    # has to be able to reach the same URLs a run does — including the ones a
    # site config has an exemption for. Naming the site is how the exemption is
    # borrowed; there is deliberately no flag that switches robots off here.
    exemption = load_scraper(as_site).robots_exempt if as_site else None
    with PoliteClient(Settings(), robots_exempt=exemption) as client:
        page = client.get(url)

    typer.echo(f"status={page.status} encoding={page.encoding} cached={page.from_cache}")
    if selector is None:
        typer.echo(page.text[:chars])
        return

    from bs4 import BeautifulSoup

    matches = BeautifulSoup(page.text, "lxml").select(selector)
    typer.echo(f"{len(matches)} match(es) for {selector!r}")
    for i, node in enumerate(matches[:20]):
        typer.echo(f"--- [{i}] {node.get_text(' ', strip=True)[:300]}")


@app.command("import")
def import_downloads(
    source: Annotated[Path, typer.Argument(help="Directory of downloads, or one .txt file.")],
    prefecture: Annotated[str, typer.Option(help="e.g. 山梨県 — names the output file.")],
    data_dir: Annotated[Path, typer.Option(help="Where the corpus lives.")] = Path("data"),
    csv: Annotated[bool, typer.Option(help="Write a CSV alongside the JSONL.")] = False,
    dry_run: Annotated[bool, typer.Option(help="Parse and report, write nothing.")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Import transcripts downloaded by hand from a DB-Search system.

    For assemblies that have asked us not to fetch their search system
    automatically — 山梨 did, by telephone on 2026-09-17 — and pointed at the
    page's ダウンロード button instead. This makes no requests.
    """
    _configure_logging(verbose)
    paths = find_downloads(source)
    if not paths:
        typer.echo(f"No .txt files under {source}")
        raise typer.Exit(1)

    store = TranscriptStore(data_dir, prefecture)
    importer = DbSearchImporter(prefecture)
    outcome = importer.import_paths(paths, skip=store.seen_keys())

    if not dry_run:
        with ExitStack() as stack:
            stack.enter_context(store)
            csv_writer = stack.enter_context(SpeechCsvWriter(data_dir, prefecture)) if csv else None
            for meeting in outcome.meetings:
                store.write(meeting)
                if csv_writer:
                    csv_writer.write(meeting)

    typer.echo(f"read     : {len(paths)} files from {source}")
    for line in outcome.summary():
        typer.echo(line)
    typer.echo(f"{'would write' if dry_run else 'wrote'}   : {store.path}")


@app.command()
def export(
    path: Annotated[Path, typer.Argument(help="A data/<prefecture>.jsonl file.")],
    out: Annotated[Path | None, typer.Option(help="CSV to write. Default: alongside, .csv")] = None,
) -> None:
    """Rewrite a collected corpus as CSV, one row per speech."""
    meetings = read_meetings(path)
    target = out or path.with_suffix(".csv")
    rows = write_csv(meetings, target)
    typer.echo(f"Wrote {rows} speech rows from {len(meetings)} meetings to {target}")


@app.command()
def stats(
    path: Annotated[Path, typer.Argument(help="A data/<prefecture>.jsonl file.")],
) -> None:
    """Summarise a collected corpus."""
    meetings = read_meetings(path)
    if not meetings:
        typer.echo("empty corpus")
        raise typer.Exit(1)
    dates = sorted(m.date for m in meetings if m.date)
    speeches = sum(len(m.speeches) for m in meetings)
    chars = sum(len(s.text) for m in meetings for s in m.speeches)
    typer.echo(f"meetings : {len(meetings)}")
    typer.echo(f"speeches : {speeches}")
    typer.echo(f"chars    : {chars:,}")
    if dates:
        typer.echo(f"range    : {dates[0]} .. {dates[-1]}")
    empty = [m for m in meetings if not m.speeches]
    if empty:
        typer.echo(f"warning  : {len(empty)} meetings have no speeches")


if __name__ == "__main__":
    app()
