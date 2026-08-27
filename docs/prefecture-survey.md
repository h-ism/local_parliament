# 47 都道府県議会 — where the minutes are, and whether we may crawl them

> **Superseded in part, 2026-08-27.** Classes D and E were re-opened and both are
> better than described here: the `kensakusystem.jp` browse tree navigates by GET,
> not only POST, and 和歌山 publishes per-sitting full text as plain UTF-8 HTML.
> The claim below that "nothing is collectable with `GenericScraper` as it stands"
> is still true, but the gap is one missing feature rather than four unknowns.
> Read `docs/collection-targets.md` for the current picture, then
> `docs/kensakusystem.md` and `docs/wakayama.md`.

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
| C. SSP (`ssp.kaigiroku.net`) | 18 | **Blocked** — the shell pages are allowed, but the data API under `/dnp/search/` is not |
| D. `kensakusystem.jp` | 3 | **Permitted** — no robots.txt at all, server-rendered HTML |
| E. Published on the prefecture's own site | 2 | **Permitted** — format not yet verified |

Nothing is collectable with `GenericScraper` as it stands today. The nearest
targets are D (三重・兵庫・愛媛) and 千葉. C was recorded as the largest prize until
2026-08-27, when the API path turned out to sit outside the one `Allow:` rule; it
now needs permission rather than code.

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

## C. SSP — the pages are allowed, the data is not (18)

All on one host, `https://ssp.kaigiroku.net/tenant/<tenant>/`. Its robots.txt reads
as the friendliest in this survey, and for two days it was recorded that way. It is
not — see the verdict at the end of this section:

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
`SpTop.html` (note: *not* `pg/SpTop.html`), which loads jQuery, Handlebars and
`../js/release/{app,config}.js` and renders everything client-side. There are no
server-rendered result links to select. The data must come from an API, and the
endpoint is defined in `/tenant/js/release/config.js`. The per-tenant `js/option.js`
(allowed, checked) holds only UI options.

### The verdict, corrected 2026-08-27

`config.js` was read in a browser by the researcher — a person loading a page is not
the crawler, and robots.txt binds the crawler. It says:

```js
dnp.config.SERVER = { API_ROOT: "/dnp/search/", PROTOCOL: "http://" }
```

There is no host constant, so the base is `https://ssp.kaigiroku.net/dnp/search/`.

**`/dnp/search/` is not under `/tenant/`.** It matches `Disallow: /` and no `Allow:`
rule reaches it. Checked against `urllib.robotparser`, the same parser `PoliteClient`
uses: every `/dnp/search/*` path returns DENY.

So the platform's *pages* are crawlable and its *data* is not. The earlier verdict
— "permitted, blocked only by architecture" — was wrong, and the error was
structural: the one path that mattered was the one path nobody had seen. **A
robots.txt verdict is not final until the URL that actually carries the data is
known.**

SSP therefore belongs with A and B: it needs permission, not code. What changes is
only the letter's purpose — from "how do I fetch this" to "may I, or will you
supply it". Drafts: `inquiries/ssp-vendor.md`, `inquiries/ssp-assembly.md`.

### Two things worth carrying elsewhere

**The robots.txt predates the app.** `Last-Modified: 2024-01-10`; the `config.js`
build is `2026-05-22`. Whether `/dnp/` is unlisted by intent or by neglect cannot be
told from outside — the same ambiguity as 千葉, in the opposite direction, and the
same answer: ask, do not decide it for them.

**`urllib.robotparser` denies `/tenant/` too.** It returns the first rule that
matches in file order, so `Disallow: /` settles every path before `Allow: /tenant/`
is reached; RFC 9309 and Google resolve by longest match and would allow it. Moot
here — the API is DENY under both readings — but `PoliteClient` will refuse any site
that writes `Disallow: /` above a narrower `Allow:`. That is a client-wide question,
not an SSP one.

### For reference, if permission is granted

The browse endpoints map onto this project's index → session → sitting shape:
`councils/index`, `councils/get_view_years`, `councils/view`,
`minutes/get_schedule`, `minutes/get_minute`, `minute_searches/search`,
`tenants/index`. `config.js` also defines `users/login`, `post_its/*`,
`search_settings/*` and `statistics/*`, so an authenticated tier exists; which
endpoints the public view actually uses was not determined, and determining it means
watching the network, which was not done.

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

1. ~~**Get the SSP API path.**~~ — done 2026-08-27, and it settled the question the
   other way: the API is `/dnp/search/`, which robots.txt disallows. SSP moves to
   step 3.
2. **Build 愛媛 (or 三重/兵庫) against `kensakusystem.jp`** — the only platform where
   today's scraper could work almost as-is. Proves the pipeline end to end.
3. **Ask, for the blocked ones.** Drafts for every one of them are in
   `docs/inquiries/` — see its README for who gets which letter.
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
No URL under any `Disallow` rule was fetched by the crawler. On 2026-08-27 the
researcher opened `/tenant/js/release/config.js` in a browser; robots.txt governs
automated fetching, so that is not a breach, but this sentence used to claim the
file had never been read and it is corrected here rather than left standing. The
crawler's rule is unchanged: it does not fetch disallowed paths.
