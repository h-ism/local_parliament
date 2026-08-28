# Where minutes can actually be collected

Written 2026-08-27, after re-opening the four leads left in yesterday's survey.
`docs/prefecture-survey.md` still maps all 47 assemblies; this document says what to
build, in what order, and what each thing costs.

**The headline:** two of the leads turned out to be better than the survey guessed,
and both are blocked by the *same* missing feature. One change to `GenericScraper` —
a second listing level — plus one small parsing addition, opens **four prefectures**
(和歌山・愛媛・三重・兵庫) with no permission question outstanding.

---

## Tier 1 — collectable now, nothing to ask anyone

**Collected on this product (2026-08-28):** 三重 819 sittings / 47,279 speeches /
1989-02-28 .. 2026-03-31, 兵庫 809 / 42,314 / **1986-02-22** .. 2026-06-11 — the
oldest material in the corpus — and 愛媛 666 / 39,624 / 1991-06-27 .. 2026-03-19.
Nothing is left uncollected on any of the three except the corpus window itself.
Detail in `docs/kensakusystem.md`.

### 1. 和歌山 — the best target found — **implemented 2026-08-27**

robots.txt 404, pages marked `index, follow`, UTF-8, no vendor system. One index
page lists ~150 sessions covering **平成2年 (1990) – 令和8年 (2026)**; each session
page lists its sittings; each sitting is a single HTML page with the full text.

Cost: 1 + ~150 + (number of sittings) requests for the entire 36-year archive.
Detail in `docs/wakayama.md`. `sites/wakayama.toml` now exists and is verified
against both the modern and the 平成-era generation; no full crawl has been run.

The one trap: members speak as bare `○濱口太史君` while office-holders use
`○知事（岸本周平君）`. 静岡's parenthesis-only split rule would silently discard the
majority of the corpus.

### 2. 愛媛・三重・兵庫 — three prefectures, three shapes — **implemented 2026-08-28**

`kensakusystem.jp`, robots.txt 404, pages marked `follow,index`. The survey left two
open questions and both resolved in our favour:

- **The tree navigates by GET.** `See.exe?Code=…&treedepth=…` accepts as a query
  string what the page submits as a POST. No POST support needed.
- **A whole sitting comes back in one request.** The page's own ダウンロード button
  posts to `GetPerson.exe`; it accepts GET, takes a repeated `downloadPos`, and
  returns the sitting as plain text. Two requests per sitting including the speaker
  index.

Coverage: 兵庫 **昭和61年 (1986)**, 三重 平成元年, 愛媛 平成3年. 兵庫 is the deepest
archive in the whole survey. `fileName=R080225A` encodes the date, so unlike 静岡 a
date filter here saves requests instead of arriving too late.

Detail, including the exact URL forms and the cp932 percent-encoding of `treedepth`,
in `docs/kensakusystem.md`.

### What "one config shape" cost

That heading was half wrong and the correction is the most useful thing this page
records. The three tenants share a host, a `cgi-bin3`, a charset and a tree shape.
They differ in the markup of a tree node (兵庫: `data-depth=`), the route to a
transcript (兵庫: `GetText3.exe?FUNC=PRINT_ALL`, one request, HTML) and the form
of a speech marker (三重: `○知事（一見勝之）`, which 愛媛's rule never matches).

Each difference fails silently — no nodes, or no speeches — so all three were
found by running the thing, not by reading it. Full account in
`docs/kensakusystem.md`. 三重 and 兵庫 both separate name from office, which 愛媛
does not, so their `role` fields are populated.

---

## Tier 2 — SSP, 18 prefectures — **blocked; corrected 2026-08-27**

The missing fact arrived and reversed the verdict. `config.js` declares

```js
dnp.config.SERVER = { API_ROOT: "/dnp/search/", PROTOCOL: "http://" }
```

and `/dnp/search/` is not under `/tenant/`, so `Disallow: /` covers it with no
`Allow:` in reach — DENY under `urllib.robotparser`, and under RFC 9309's
longest-match reading too. **The shell pages are crawlable; the data is not.**

That puts these 18 with the blocked assemblies below: the way through is a letter,
not a scraper. Everything in the rest of this section still holds and is what makes
the letter concrete — keep it.

**Done:** every tenant's numeric id, read from `/tenant/<tenant>/js/<…>.js`, which is
**not** under any `Disallow` rule (`Disallow: /tenant/js/` matches only the shared
directory, not `/tenant/prefosaka/js/`).

| | | | |
| --- | --- | --- | --- |
| 宮城 `prefmiyagi` 354 | 秋田 `prefakita` 408 | 山形 `prefyamagata` 466 | 福島 `fukushima` 69 |
| 埼玉 `prefsaitama` 350 | 神奈川 `prefkanagawa` 369 | 新潟 `prefniigata` 333 | 岐阜 `prefgifu` 352 |
| 大阪 `prefosaka` 315 | 奈良 `prefnara` 332 | 岡山 `prefokayama` 455 | 山口 `prefyamaguchi` 599 |
| 徳島 `tokushimapref` 266 | 高知 `prefkochi` 494 | 長崎 `prefnagasaki` 460 | 熊本 `prefkumamoto` 516 |
| 大分 `prefoita` 499 | 沖縄 `prefokinawa` 632 | | |

**Also established:** the permalink form is
`…/tenant/<t>/MinuteView.html?council_id=<n>&schedule_id=<m>`, and those pages are a
pure client-side shell — `<span id="council-title">` is empty in the served HTML.
So there is no server-rendered route; the API is genuinely required.

**The endpoint** is `/dnp/search/`, read from `/tenant/js/release/config.js` — a
disallowed path, opened by the researcher in a browser rather than by the crawler.
Browse endpoints, for whenever permission exists: `councils/index`,
`councils/get_view_years`, `councils/view`, `minutes/get_schedule`,
`minutes/get_minute`, `minute_searches/search`.

**The vendor is NTT Advanced Technology Co., Ltd.**, from the copyright header of
`config.js`. The earlier note that the page carries "a DNP logo" was a misreading:
the product is **Discuss Net Premium**, its namespace is `dnp.*`, and DNP is that
name — not 大日本印刷. The draft letter is `docs/inquiries/ssp-vendor.md`.

**A second question, independent of robots.** 大阪's own page states:

> このデータの権利は、大阪府議会に帰属します。転用、その他の用途への利用については、
> 大阪府議会事務局までお問い合わせください。

That is a reuse condition, not an access rule, and it would apply even if the API
were known tomorrow. It belongs in the inquiry letters for these 18.

---

## Tier 3 — waiting on a person, not on code

- **静岡, full archive** — 平成11年 onwards, pending 議事課 on the `meta robots`
  question. 2025 is already collected. `docs/inquiries/shizuoka.md`.
- **千葉** — permitted by the letter of its robots.txt because its install sits at
  `/kaigiroku/` while the vendor boilerplate closes `/voices/cgi/`. Still an
  oversight rather than an invitation; ask first. `docs/inquiries/chiba.md`.
- **24 assemblies** on DB-Search and gijiroku VOICES — `Disallow: /`. Letters drafted
  in `docs/inquiries/`.

---

## Before collecting anything: ask for what already exists

**Scope is settled (2026-08-27): every period we can obtain, no research window.**

The 地方議会会議録コーパスプロジェクト (<http://local-politics.jp/>) publishes a
都道府県議会 corpus covering **all 47 assemblies** for **2011-04 .. 2019-03** —
fiscal years, so the boundaries are not where you would guess. Reported as 423
bodies, ~134M sentences, ~80 GB. Its search systems are public; the bulk data
appears to be by arrangement with the project rather than a download.

With no window, that range is not something to route around. It is a large piece of
exactly what we want, already assembled, and the question is no longer "do I need to
crawl this?" but "you already have this — may I have it rather than re-crawling 47
assemblies?"

Two consequences are already on the books:

- **和歌山 and 愛媛 were both scoped to leave 2011-04 .. 2019-03 empty**, on the
  assumption that it comes from this project. Those holes stay open by design until
  the letter is answered — and 和歌山's 673 documents from 1989–2011 sit on the far
  side of one of them.
- **2019-04 .. 2019-12 falls between that corpus and any collection that starts at a
  calendar year.** 和歌山 was scoped with that edge in mind; do the same for the next
  prefecture.

**Ask before starting any large crawl.** The letter is drafted and unsent:
`docs/inquiries/local-politics.md`. It also asks whether their collection continues
past 2019-04 — the answer most likely to change what we do next, and one nothing on
our side can establish.

---

## Recommended order

1. **Send `docs/inquiries/local-politics.md`.** Drafted 2026-08-27, not yet sent;
   the addressee is still 要確認. One email, and it decides whether 2011-04 ..
   2019-03 has to be crawled for 47 assemblies at all.
2. ~~Add the intermediate listing level to `GenericScraper`.~~ — done.
3. ~~`sites/wakayama.toml`~~ — done, and the archive is collected: 907 sittings,
   46,839 speeches, 1989-02-27 .. 2025-12-19. Only 2011-04 .. 2019-03 is missing,
   and item 1 decides whether we crawl it. 委員会会議録 (`/gijiroku2/`) untouched.
4. ~~`sites/ehime.toml`, `sites/mie.toml`, `sites/hyogo.toml`~~ — done. The three
   needed a scraper change each, not a config each; 兵庫 reaches 昭和61年 (1986).
   Still uncollected on this product: every 委員会. The 本会議 archives are done.
5. Send the SSP letters. Now a permission request, not a how-to: the API is
   disallowed. Address the vendor as NTT Advanced Technology, and put 大阪 first —
   it is the only one of the 18 that names a destination on its own page.
6. ~~Set `PT_CONTACT`.~~ — set 2026-08-28 to a 京都大学 address, as an `export` in
   the researcher's `~/.bashrc`. There is no `.env` support: `Settings.contact`
   reads the environment at import, so it has to be exported before `uv run`.
   **Provisional (仮おき) — confirm the address before a letter goes out or a large
   crawl starts.** It is what site operators see in the User-Agent and what every
   letter in `docs/inquiries/` promises.
