"""Does 茨城's listing accept the search form's 本文 filter as a plain GET?

The 年別の会議録閲覧 links are GETs (`Template=list&QueryType=new&Cabinet=…`),
and each lists 議事日程, 名簿 and 本文 for every sitting, 10 to a page. The
search form carries `Part[]` = 3 (本文). If the same links accept it, the
listing is a quarter the size and every result is a transcript.

The control is already cached: 議会運営委員会 2024 without the filter, 63 件.
So this costs **one request**, and a second only if the first is ignored
(`Part=3` unrecognised, then the form's own spelling `Part[]=3`).

Then one more: `&Page=2` on the same GET. The form pages by POSTing `Page=N`
to a session URL with a CSRF token; if the GET takes it too, the whole
listing is stateless. Judged by page 2 holding documents page 1 does not.
At most three requests in all.

Runs under 茨城's own terms from `recon_sites.py` — the exemption, the
20:00-07:00 window, 共同研究者B in the User-Agent, 5 s — and refuses to start
while the nightly survey is still on the same host.

    uv run python scripts/probe_ibaraki_part.py
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent))
from recon_sites import SITES, settings  # noqa: E402

from prefectural_transcripts.http import Page, PoliteClient  # noqa: E402

BASE = (
    "https://www.pref.ibaraki.dbsr.jp/100000?Template=list&QueryType=new"
    "&Cabinet=35&TermStart=2024-01-01&TermEnd=2024-12-31"
)
TRIES = [BASE + "&Part=3", BASE + "&Part%5B%5D=3"]


def ids(page: Page) -> set[str]:
    return set(re.findall(r"Template=document&(?:amp;)?Id=(\d+)", page.text))


def summary(page: Page) -> tuple[str, list[str]]:
    soup = BeautifulSoup(page.text, "lxml")
    m = re.search(r"(\d+)\s*件", soup.get_text(" ", strip=True))
    kinds = [
        a.get_text(" ", strip=True).split()[-1]
        for a in soup.find_all("a", href=True)
        if "Template=document" in str(a["href"])
    ]
    return (m.group(0) if m else "?"), kinds


def recon_running() -> bool:
    out = subprocess.run(
        ["systemctl", "--user", "is-active", "pt-voices-recon.service"],
        capture_output=True,
        text=True,
    )
    return out.stdout.strip() in ("active", "activating")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")
    out = Path("data/logs/ibaraki") / f"probe-part-{datetime.now():%Y%m%d-%H%M}.txt"
    lines: list[str] = []

    # One host, one process: wait out the nightly survey, at most an hour.
    for _ in range(60):
        if not recon_running():
            break
        time.sleep(60)
    else:
        lines.append("survey still running after an hour; nothing fetched")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1

    site = SITES["ibaraki"]
    with PoliteClient(settings(site), robots_exempt=site.exemption, fetch_window=site.window) as c:
        control = c.get(BASE)
        count, kinds = summary(control)
        lines.append(f"control (cached={control.from_cache}): {count}, first page {kinds}")
        chosen = BASE
        for url in TRIES:
            page = c.get(url)
            count, kinds = summary(page)
            lines.append(f"{url}\n  cached={page.from_cache} {count}, first page {kinds}")
            if kinds and all(k == "本文" for k in kinds):
                lines.append("  -> the filter works: every result is 本文")
                chosen = url
                break
            lines.append("  -> not filtered")

        first = c.get(chosen)
        second = c.get(chosen + "&Page=2")
        new = ids(second) - ids(first)
        lines.append(
            f"{chosen}&Page=2\n  cached={second.from_cache} page1 {sorted(ids(first))}"
            f"\n  page2 {sorted(ids(second))}"
        )
        lines.append(
            "  -> GET paging works" if new else "  -> Page=2 ignored: paging needs the form's POST"
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
