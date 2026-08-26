"""Command line entry point (`uv run pt ...`)."""

from __future__ import annotations

import logging
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from prefectural_transcripts.config import Settings
from prefectural_transcripts.http import PoliteClient
from prefectural_transcripts.scrapers import available_sites, load_scraper
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
        client = stack.enter_context(PoliteClient(settings))
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
    if csv_out:
        typer.echo(f"CSV written to {settings.data_dir / (store.path.stem + '.csv')}")


@app.command()
def inspect(
    url: Annotated[str, typer.Argument(help="Page to fetch.")],
    selector: Annotated[
        str | None, typer.Option(help="CSS selector to test against the page.")
    ] = None,
    chars: Annotated[int, typer.Option(help="How much of the page to print.")] = 3000,
    verbose: Annotated[bool, typer.Option("-v", "--verbose")] = False,
) -> None:
    """Fetch one page (through the cache) to help work out selectors."""
    _configure_logging(verbose)
    with PoliteClient(Settings()) as client:
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
