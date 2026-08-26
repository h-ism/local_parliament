# 青森県議会 — site survey (2026-08-26)

Findings from working out how to collect 青森県 (Aomori). Same shape of outcome
as `hokkaido.md`, for a different reason: the minutes exist in one HTML system
with good coverage, and its `robots.txt` allows exactly one page of it.

## Where the minutes are

The prefectural site (`www.pref.aomori.lg.jp/kensei/gikai/`, and the assembly's
own page at `/soshiki/gikai/home.html`) publishes no transcripts itself. Both
link out to a single external system:

**青森県議会会議録検索システム — <https://www.pref.aomori.dbsr.jp/index.php/>**

A DB-Search (`dbsr.jp`) tenant, Laravel-backed, UTF-8, session cookies on every
response. Navigation is GET and the URL scheme is regular:

```
/index.php/100000?Template=list&Cabinet=1      # 定例会
/index.php/100000?Template=list&Cabinet=21     # 予算特別委員会
/index.php/100000?Template=search-detail       # 検索フォーム
/index.php/100000?Template=search-library      # 会議録一覧
```

Coverage is the reason this one is worth wanting — read off the landing page:

| 会議 | Cabinet | 登録範囲 |
| --- | --- | --- |
| 定例会 | 1 | 昭和58年度以降 |
| 臨時会 | 2 | 昭和58年度以降 |
| 議員発議（意見書・決議等） | 3,4 | 昭和22年度以降 |
| 常任委員会（名称変更で分割、計 5–20） | 5–20 | 平成12年度以降 |
| 予算特別委員会 | 21 | 平成9年度以降 |
| 決算特別委員会 | 22 | 昭和58年度以降 |
| 特別委員会（予算・決算を除く） | 23–31 | 平成19年度以降 |
| 全員協議会 | 32 | 昭和58年度以降 |
| 議員説明会 | 33 | 平成20年度以降 |

Committees are split across many `Cabinet` ids because the committee names
themselves changed over the years (総務企画 → 総務企画危機管理 → 総務政策こども,
and so on). A full committee crawl means enumerating all of them, not one id.

## The blocker

<https://www.pref.aomori.dbsr.jp/robots.txt>:

```
User-agent: *
Disallow: /
Allow: /$
Allow: /index.php$
Allow: /index.php/$
```

Everything is disallowed except the bare landing page. The three `Allow` rules
are `$`-anchored, so they match only `/`, `/index.php` and `/index.php/` exactly
— `/index.php/100000?Template=list&Cabinet=1` is not covered by any of them and
falls under `Disallow: /`. Every list, every search result and every transcript
page is off-limits.

This is stricter than Hokkaido, where at least the navigation pages were
crawlable and only `/voices/cgi/` was closed. Here the crawlable surface is one
page that contains no minutes.

So, as with Hokkaido: no `sites/aomori.toml`. Nothing about the list or detail
markup could be verified, because verifying it means fetching pages we have been
asked not to fetch. `pt inspect` on the landing page is the only request this
survey made against the system.

## Ways forward

1. **Ask 青森県議会事務局.** 議事課 017-734-9794 (会議録), 調査課 017-734-9797
   (the system is linked from a 調査課 page), FAX 017-734-8235,
   〒030-8570 青森市長島一丁目1番1号. Draft: `docs/aomori-inquiry.md`. Worth
   asking in the same breath whether the data can be had from the vendor.
2. **Override robots deliberately** — `PT_RESPECT_ROBOTS=0`. A research-owner
   decision, contradicts the convention in CLAUDE.md, and here it means ignoring
   a blanket `Disallow: /` rather than one directory, which is a bigger step than
   it was for Hokkaido.
3. **Drop Aomori for now** and spend the effort on a prefecture whose system is
   open. That is a survey worth doing before committing to either 1 or 2 — see
   "Next" below.

## Next

Two prefectures surveyed, two blocked by robots.txt, for unrelated reasons and
on unrelated vendor platforms. Before writing more site configs it is worth
running the cheap check — fetch just `robots.txt` for each prefecture's minutes
system — so target selection starts from what is actually collectable instead of
discovering the blocker one prefecture at a time.

## Verified against the live site

Checked on 2026-08-26 with single manual requests: the two prefectural pages
that link to the system, the system's landing page, and its `robots.txt`.
Nothing under a disallowed path was fetched. (Probes for `dbsr.jp` tenants of
other prefectures — iwate, akita, chiba, gunma — did not resolve, so nothing is
claimed here about whether this robots.txt is a vendor default or Aomori's own.)
