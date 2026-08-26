# 北海道議会 — site survey (2026-08-26)

Findings from working out how to collect 北海道 (Hokkaido) for 2025 / 令和7年,
starting from the URL we were given:
<https://www.gikai.pref.hokkaido.lg.jp/kaigiroku/>.

**Outcome: no `sites/hokkaido.toml` is shipped yet.** The transcripts exist, but
neither publication route can be collected by `GenericScraper` as things stand —
one is disallowed by `robots.txt`, the other is PDF-only. Details below, along
with a draft config that becomes runnable the moment the first blocker is lifted.

## What the given URL actually is

`/kaigiroku/` is a portal page, not a search system. It links out to two
different publications:

| Route | Coverage | Format |
| --- | --- | --- |
| A. 会議録データベース — <https://pref-hokkaido.gijiroku.com/voices/> | 本会議 昭和46年〜, 予算特別委員会 昭和46年〜, 決算特別委員会 昭和45年〜, 常任・特別・議会運営委員会 平成24年〜 | HTML (Shift_JIS) |
| B. 会議録（速報）— `/kaigiroku/kaigiroku_sokuhou/` | only sittings whose official minutes are not yet published | PDF |

Route B is explicitly temporary: the 速報 text is only up "until the official
minutes are compiled and loaded into 会議録データベース". As of today it lists 本会議
for 令和8年 only, so no 2025 本会議 — but 予算特別委員会 still has 令和7年第1〜4回 and
決算特別委員会 has 令和7年, i.e. some 2025 committee sittings are there. All of it
is PDF (`/fs/1/3/…/Taro-A09-24.pdf` and similar), and all of it will disappear
from route B once route A catches up.

## Route A — 会議録データベース (the one we want)

A DiscussVision-style ASP system. Navigation is plain GET and works fine:

- `/voices/index.asp` — entry point
- `/voices/g08v_viewh.asp` — 本会議, year picker
- `/voices/g08v_views.asp` — committees
- `/voices/g07v_search.asp` — full-text search
- `/voices/g08v_viewh.asp?Sflg=11&FYY=2025&TYY=2025` — **令和7年 本会議**

But those pages contain no result list. Each one embeds the results in an
`<iframe>` served by a CGI executable:

```html
<iframe src="cgi/voiweb.exe?ACT=100&KTYP=0,1,2,3&SORT=0&FYY=2025&FMM=&FDD=&TYY=2025&TMM=&TDD=&KGTP=1,2" name="BOTTOM">
```

and `https://pref-hokkaido.gijiroku.com/robots.txt` says:

```
User-agent: *
Disallow: /voices/cgi/
Disallow: /voices2/cgi/
Disallow: /gikai/cgi/
```

So the result list, the per-sitting transcript view and the download endpoint —
everything under `/voices/cgi/voiweb.exe` — is off-limits to us. `PoliteClient`
honours robots.txt, so it will raise `RobotsDisallowed` on those URLs, and the
list/detail selectors below could not be verified because verifying them would
have meant fetching exactly those pages.

Two further things worth knowing before anyone picks this up:

- `GenericScraper` follows `<a href>`, not `<iframe src>`. Even with robots
  respect switched off, the start URL has to be the `voiweb.exe?ACT=100…` URL
  itself; the `g08v_*.asp` pages are useless to the scraper.
- The smartphone variant (`/voices2/`) is gone — 404 — and there is no sitemap.

### Draft config (unverified — do not drop into `sites/` as-is)

Kept here rather than in `sites/` because the two selector blocks are guesses:
the pages they describe have never been fetched. The `start_urls` entry is not a
guess — it is the iframe `src` read off the 令和7年 page, resolved.

```toml
prefecture = "北海道"
name = "hokkaido"

# 本会議, 令和7年 (2025). KGTP=1,2 = 定例会・臨時会; KTYP=0,1,2,3 = all sitting types.
start_urls = [
    "https://pref-hokkaido.gijiroku.com/voices/cgi/voiweb.exe?ACT=100&KTYP=0,1,2,3&SORT=0&FYY=2025&FMM=&FDD=&TYY=2025&TMM=&TDD=&KGTP=1,2",
]

[list]
row          = "TODO"   # one result row
meeting_link = "TODO"   # link into the transcript view
date         = "TODO"   # 和暦 date cell — dates.py handles 令和7年6月10日 etc.
next_page    = "TODO"   # pagination, if the result list has any
max_pages    = 50

[detail]
container = "TODO"
speech    = "TODO"
speaker   = "TODO"
role      = "TODO"
text      = "TODO"
date      = "TODO"
session   = "TODO"
title     = "TODO"
```

Committees would be a second `start_urls` entry with `KGTP` set from the
`g08v_views.asp` iframe; 予算特別委員会 and 決算特別委員会 are separate 会議種別
in the same system.

## Ways forward

1. **Ask the assembly.** 北海道議会事務局議事課 (011-204-5685,
   `/inquiry/?group=290`) publishes these records for public use; a research
   request for bulk access, or for permission to crawl `/voices/cgi/` slowly, is
   the clean route. The サイトポリシー forbids only 「運営を妨げる行為」 and says
   nothing about crawling — and it covers the CMS host anyway, not the vendor
   host the database lives on. robots.txt is the only signal we have there, and
   it is a blanket rule aimed at bots generally rather than at us.
2. **Override robots deliberately.** `PT_RESPECT_ROBOTS=0` exists, and this is a
   decision for whoever owns the research, not something to default into. It
   contradicts the convention in CLAUDE.md, so if it is taken, take it explicitly
   and keep `PT_MIN_INTERVAL` high.
3. **Teach the toolkit PDFs and use route B.** Real work — a text-extraction
   dependency plus a non-HTML path through `BaseScraper` — and it buys only what
   route B happens to be holding: today that is 令和8年 本会議 plus 令和7年
   予算・決算特別委員会, i.e. part of 2025 but no 2025 本会議, shrinking every time
   route A catches up. Worth doing for freshness later; it is not a way around
   this blocker.

## Verified against the live site

Every URL, parameter and robots rule above was checked on 2026-08-26 with single
manual requests. Nothing under `/voices/cgi/`, `/voices2/cgi/` or `/gikai/cgi/`
was fetched.
