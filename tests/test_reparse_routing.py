"""One corpus file holds more than one site, and re-parsing must know which.

`data/静岡県.jsonl` is 14,030 本会議 documents under `ggiji.nsf` and 18,245 委員会
documents under `comgiji.nsf`. Re-parsing all of them with the 本会議 scraper does
not raise: that rule requires a 「君」 no committee marker carries, so it would
rewrite every committee document to zero speeches, print the loss as a diff, and
leave the corpus destroyed with only a `.bak` between it and the archive.

So records are routed by URL, and anything unclaimed stops the run.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from reparse import _prefixes  # noqa: E402

from prefectural_transcripts.scrapers import load_scraper  # noqa: E402


def test_the_two_shizuoka_sites_do_not_claim_each_others_documents() -> None:
    honkaigi = _prefixes(load_scraper("shizuoka"))
    committee = _prefixes(load_scraper("shizuoka_committee"))

    assert honkaigi == ["https://www2.pref.shizuoka.jp/all/ggiji.nsf/"]
    assert committee == ["https://www2.pref.shizuoka.jp/all/comgiji.nsf/"]

    doc = "https://www2.pref.shizuoka.jp/all/ggiji.nsf/ffb2b708/3f18a9a2?OpenDocument"
    com = "https://www2.pref.shizuoka.jp/all/comgiji.nsf/ffb2b708/3f18a9a2?OpenDocument"

    assert doc.startswith(honkaigi[0]) and not doc.startswith(committee[0])
    assert com.startswith(committee[0]) and not com.startswith(honkaigi[0])


def test_a_prefix_is_a_directory_not_a_listing_url() -> None:
    """The listing carries a query string and the documents do not.

    Keeping the whole start URL would match nothing, and matching nothing is what
    the unclaimed-records check exists to catch — but it is cheaper to be right.
    """
    for prefix in _prefixes(load_scraper("shizuoka")):
        assert prefix.endswith("/")
        assert "?" not in prefix
