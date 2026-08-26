# 47 都道府県議会 — where the minutes are, and whether we may crawl them

Surveyed 2026-08-26, after 北海道 and 青森 both turned out to be blocked. The point
of this pass was to stop discovering blockers one prefecture at a time: for all 47,
find the minutes system, read its `robots.txt`, and see what the pages actually are.

Every prefecture is accounted for. Each system was identified from the prefecture's
own assembly site or from search, and each `robots.txt` was fetched directly.

## Summary

| Class | Prefectures | Verdict |
| --- | ---: | --- |
| A. DB-Search (`*.dbsr.jp` + 東京) | 15 | **Blocked** — `Disallow: /` |
| B. gijiroku VOICES (`*.gijiroku.com` etc.) | 9 | **Blocked** — `Disallow: /…/cgi/`, except 千葉 (see below) |
| C. SSP (`ssp.kaigiroku.net`) | 18 | **Permitted by robots**, but a JavaScript app — needs an API client, not selectors |
| D. `kensakusystem.jp` | 3 | **Permitted** — no robots.txt at all, server-rendered HTML |
| E. Published on the prefecture's own site | 2 | **Permitted** — format not yet verified |

Nothing is collectable with `GenericScraper` as it stands today. The nearest
targets are D (三重・兵庫・愛媛) and 千葉; the largest prize is C, 18 prefectures on
one platform, which needs one new scraper rather than 18 configs.

## A. DB-Search — blocked (15)

Hosts `https://www.pref.<name>.dbsr.jp/`, plus 東京 on its own domain. Every one
serves the same robots.txt:

```
User-agent: *
Disallow: /
Allow: /$
Allow: /index.php$
Allow: /index.php/$
```

`$`-anchored, so only the landing page is allowed; every list, search result and
transcript is disallowed. Verified per host, not assumed.

青森, 茨城, 東京[^tokyo], 富山, 山梨, 愛知, 京都, 鳥取, 島根, 広島, 香川, 福井, 福岡, 佐賀, 鹿児島

[^tokyo]: 東京都議会 is at `https://www.record.gikai.metro.tokyo.lg.jp/` — a
different domain, byte-identical robots.txt.

See `docs/aomori.md` for the detail on this platform.

## B. gijiroku VOICES — blocked, with one gap (9)

The ASP product behind 北海道. Result lists and transcripts are served from a CGI
inside an `<iframe>`; the vendor's boilerplate robots.txt disallows the CGI
directory. Verified per host.

| Prefecture | Host | Product path | Verdict |
| --- | --- | --- | --- |
| 北海道 | `pref-hokkaido.gijiroku.com` | `/voices/` | blocked |
| 岩手 | `iwatekengikai.gijiroku.com` | root-level `*.asp` | blocked (CGI path not re-checked) |
| 栃木 | `pref-tochigi.gijiroku.com` | `/voices/` | blocked |
| 群馬 | `www07.gijiroku.com` | `/voices/` | blocked |
| 石川 | `pref-ishikawa.gijiroku.com` | `/voices/` | blocked |
| 長野 | `nagano.gijiroku.com` | `/voices/` | blocked |
| 滋賀 | `www.shigaken-gikai.jp` | `/voices/` | blocked |
| 宮崎 | `pref-miyazaki.gijiroku.com` | `/voices/` | blocked |
| **千葉** | `pref-chiba.gijiroku.com` | **`/kaigiroku/`** | **not disallowed — see below** |

### 千葉 — permitted by the letter of robots.txt

Chiba's robots.txt carries the same boilerplate list:

```
Disallow: /voices/cgi/
Disallow: /voices2/cgi/
Disallow: /gikai/cgi/
Disallow: /gikai/voices/cgi/
Disallow: /gikai/voices2/cgi/
```

but Chiba's install lives at `/kaigiroku/`, and its result iframe resolves to
`https://pref-chiba.gijiroku.com/kaigiroku/cgi/voiweb.exe?ACT=100&…` — a path none
of those rules match. So robots.txt permits it.

Treat that as an oversight, not an invitation: every other tenant of this product
closes the equivalent path, so the operator's intent is not in doubt. It is
technically crawlable and I would still ask 千葉県議会事務局 政策調査課
(043-223-2523) before running anything against it. Flagging it because it is a
real difference, not because it is a loophole worth taking.

長崎 and 奈良 also answer on `pref-nagasaki` / `pref-nara.gijiroku.com`, but both
have SSP tenants too; which system is current was not established, so they are
counted under C.

## C. SSP — permitted by robots, blocked by architecture (18)

All on one host, `https://ssp.kaigiroku.net/tenant/<tenant>/`, whose robots.txt is
the friendliest thing in this survey:

```
User-agent: *
Disallow: /
Allow: /tenant/
Disallow: /tenant/js/
Disallow: /tenant/css/
Disallow: /tenant/help/
Disallow: /tenant/stats/
```

Tenants (`pref<name>`, with two exceptions):

宮城 `prefmiyagi`, 秋田 `prefakita`, 山形 `prefyamagata`, 福島 `fukushima`,
埼玉 `prefsaitama`, 神奈川 `prefkanagawa`, 新潟 `prefniigata`, 岐阜 `prefgifu`,
大阪 `prefosaka`, 奈良 `prefnara`, 岡山 `prefokayama`, 山口 `prefyamaguchi`,
徳島 `tokushimapref`, 高知 `prefkochi`, 長崎 `prefnagasaki`, 熊本 `prefkumamoto`,
大分 `prefoita`, 沖縄 `prefokinawa`

The catch: the tenant pages are a shell. `pg/index.html` is a meta-refresh to
`SpTop.html`, which loads jQuery, Handlebars and `../js/release/{app,config}.js`
and renders everything client-side. There are no server-rendered result links to
select. The data must come from an API, and the endpoint is defined in
`/tenant/js/release/config.js` — which is one of the four disallowed directories,
so it was not fetched. The per-tenant `js/option.js` (allowed, checked) holds only
UI options.

So: crawling this platform is *allowed*, and it would cover 18 prefectures with one
implementation. What is needed is the API path, obtained without reading a
disallowed script — either by driving a real browser once and watching the network
tab, or by asking the vendor or any of the 18 assemblies. That is the single
highest-value next step in this project.

## D. `kensakusystem.jp` — permitted, server-rendered (3)

三重 `/mie/`, 兵庫 `/hyogopref/`, 愛媛 `/ehime/`.

`https://www.kensakusystem.jp/robots.txt` returns **404** — nothing is disallowed.
Pages are server-rendered Shift_JIS HTML from a CGI (`See.exe`, `Search2.exe`),
which is exactly the shape `GenericScraper` handles, and `sniff_encoding` already
covers the Shift_JIS-in-a-meta-tag problem.

Two wrinkles, both surmountable:

- Every URL carries a `Code=` session token (`Code=e7c7rvxas7fwx1belp` for 愛媛).
  It is baked into the static `index.html` and did not change between fetches, so a
  config can hold it — better, the scraper should read it from `index.html` first
  so a rotation does not silently break the crawl.
- The browse tree navigates by POST (`See.exe` with a `treedepth` field), and the
  search form is POST too. A GET to `Search2.exe` is accepted and returns the page,
  but the parameter set that produces a result list was not pinned down in this
  pass — an indexed GET result URL exists for 兵庫, so it is reachable; it just
  needs one session of trial. Failing that, POST support in `BaseScraper` is a
  small addition.

Coverage, from 愛媛's landing page: 本会議 from 平成3年第229回定例会, 委員会 from
平成19年5月.

**This is the recommended first real target.**

## E. Own site (2)

| Prefecture | Where | robots.txt |
| --- | --- | --- |
| 静岡 | `www.pref.shizuoka.jp/kensei/kengikai/` | present; disallows unrelated paths only |
| 和歌山 | `www.pref.wakayama.lg.jp/gijiroku/` | 404 — nothing disallowed |

Both publish through the prefecture's CMS rather than a search vendor. Neither
page tree was opened far enough to see whether the transcripts are HTML or PDF —
on the evidence of 北海道's 速報 pages, expect PDF. 岩手 also has a second,
prefecture-hosted system at `www3.pref.iwate.jp/gikai/user/www/Kensaku/`
(robots.txt 404) which may be an alternative to its blocked gijiroku install.

## What to do next

1. **Get the SSP API path.** 18 prefectures, one implementation, robots already on
   our side. Load a tenant in a browser once and read the network tab, or ask.
2. **Build 愛媛 (or 三重/兵庫) against `kensakusystem.jp`** — the only platform where
   today's scraper could work almost as-is. Proves the pipeline end to end.
3. **Ask, for the blocked ones.** `docs/hokkaido-inquiry.md` and
   `docs/aomori-inquiry.md` are reusable templates; 15 + 8 prefectures are
   reachable only this way.
4. **Look at existing corpora before re-collecting anything.** The
   地方議会会議録コーパスプロジェクト (<http://local-politics.jp/>) already publishes a
   都道府県議会 corpus for 2011–2014 and 2015–2019, and `yonalog`
   (<https://chiholog.net/yonalog>) offers cross-prefecture search. If either
   covers the research window, much of this crawl may be unnecessary.

## Method and courtesy

Discovery used pattern probes against vendor hosts plus web search; identification
and every robots.txt came from a direct fetch. Requests were spaced ~2–3s and
serialised per service. One early pass probed `dbsr.jp` hosts in parallel and drew
`429 Too Many Requests` — that was my error, and the pass was redone sequentially.
No URL under any `Disallow` rule was fetched, including
`/tenant/js/release/config.js`, which is why the SSP API path is still unknown.
