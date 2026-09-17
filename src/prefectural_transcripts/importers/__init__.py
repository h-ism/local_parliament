"""Importers for transcripts that arrive as files rather than over the network.

An importer exists where the assembly has told us not to crawl but has pointed
at a download button instead. Nothing here touches `PoliteClient`: the fetching
was done by a person, and the code's whole job is to turn what they saved into
the same `Meeting` records a scraper would have produced.
"""

from __future__ import annotations

from prefectural_transcripts.importers.dbsearch import (
    DbSearchImporter,
    DocumentResult,
    ImportOutcome,
    parse_document,
)

__all__ = ["DbSearchImporter", "DocumentResult", "ImportOutcome", "parse_document"]
