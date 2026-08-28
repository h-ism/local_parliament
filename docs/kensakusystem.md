# `kensakusystem.jp` — 三重・兵庫・愛媛

Verified against 愛媛 on 2026-08-27, and against 三重 and 兵庫 on 2026-08-28.
**Collectable.** The whole flow works over plain GET, and the site's own download
button hands back a full sitting in one or two requests.

**"The same install" was wrong, and it was wrong in the two places that decide
whether a config collects anything.** The three tenants share a host, a
`cgi-bin3`, a charset and a tree shape, and differ in: the markup that carries a
tree node, the route that returns a transcript, and the form of a speech marker.
A config copied across without checking yields **zero speeches** on 三重 and
**zero nodes** on 兵庫 — both of which look, from the run log, like a site that
simply has nothing to give.

| | 愛媛 | 三重 | 兵庫 |
| --- | --- | --- | --- |
| tree node | `onClick=…treedepth.value='…'` | same | `data-depth="…"` |
| transcript | `GetPerson.exe` + offsets | same | `GetText3.exe?FUNC=PRINT_ALL` |
| requests per sitting | 2–3 | 2–3 | **1** |
| body | plain text | plain text | HTML (`<BR>`) |
| marker | `○（三宅浩正議長）` | `○知事（一見勝之）` | `○議長（浜田知昭）` / `○（北野　実議員）` |
| name vs office | inseparable | **separate** | **separate** |

## Access

- `https://www.kensakusystem.jp/robots.txt` → **404**. Nothing disallowed.
- Every page carries `<meta name="robots" CONTENT="follow,index">` — an explicit
  invitation, in contrast to 静岡's `content="none"`.
- Shift_JIS declared as `charset=x-sjis`; `sniff_encoding` resolves it to cp932,
  which is what these pages actually are. Already handled.

## Tenants

| Pref | Path | `Code=` | Coverage |
| --- | --- | --- | --- |
| 三重 | `/mie/` | `4t2ncj9qufw8kewil1` | 本会議 平成元年〜; 委員会 令和5年〜 |
| 兵庫 | `/hyogopref/` | `rpo2cq1zucjm5gwgk4` | 本会議・予算特別委員会・決算特別委員会 **昭和61年第197回定例会**〜; 常任委員会 平成17年6月〜 |
| 愛媛 | `/ehime/` | `e7c7rvxas7fwx1belp` | 本会議 平成3年第229回定例会〜; 委員会 平成19年5月〜 |

Year nodes counted on 2026-08-28: 三重 **39** (平成元年–令和8年), 兵庫 **42**
(昭和61年–令和8年). Both walk as two phases — tabs, then the years they group.

兵庫 is the deepest archive found anywhere in this survey — back to 1986.

The `Code=` is a session token baked into the static `index.html`. It did not change
across two days of fetches, but a config should still read it out of `index.html`
rather than hard-code it, so a rotation fails loudly instead of silently.

## The flow — all GET

The survey recorded that the browse tree "navigates by POST". It does in a browser
(`<form name="viewtree" method="POST">`, driven by
`javascript:document.viewtree.submit()`), **but `See.exe` accepts the same fields as
a GET query string**, so no POST support is needed.

1. **Tree, year level**
   `See.exe?Code=<code>&treedepth=<年>`
   `treedepth` is the node label, percent-encoded **in cp932**, e.g. `令和 8年` →
   `%97%DF%98a%208%94N`. Note the single ASCII space inside the label.
   Returns the sessions and committees of that year.

2. **Tree, session level**
   `See.exe?Code=<code>&treedepth=<年> <会議名> ` — note the **trailing space**,
   which is part of the label. Returns the sittings as
   `ResultFrame.exe?Code=<code>&fileName=R080225A&startPos=0`.

   **`fileName` encodes the date**: `R080225A` = 令和08年02月25日. Unlike 静岡, this
   listing is date-filterable before anything is fetched, so `--since/--until` can
   actually save requests here.

3. **Per-speech index**
   `r_Speakers.exe?<code>/<fileName>/0/0//10/1/1073741823:2097151/0/1//0/0/0`
   One row per speech: the speaker's name as the link text (`福羅浩一議長`), the
   page number, and a character offset as
   `<input type="checkbox" name="downloadPos" value="3199">`.
   The frameset also carries an id (`3078` for the sample) in the second-to-last
   slot; **`0` works there**, so the `ResultFrame.exe` hop can be skipped.

4. **Full text, one request**
   `GetPerson.exe?Code=<code>&fileName=<f>&downloadPos=81&downloadPos=3199&…`
   This is the page's own ダウンロード button (`<form ACTION="GetPerson.exe"
   METHOD="POST">`), and **it accepts GET with a repeated `downloadPos`**. It
   returns the selected speeches concatenated as **plain text** — not HTML — with
   the conventional markers:

   ```
   ○（福羅浩一議長）　ただいまから第395回愛媛県議会定例会を開会いたします。
   ○（中村時広知事）　…
   <PAGE="2">
   ```

   So a whole sitting costs **two requests** (speaker index + download), not one per
   speech. Compare the alternatives, both of which are worse: `GetText3.exe` returns
   one speech (~3 KB) and `GetPage.exe` one printed page (~4 KB).

## 兵庫's route: 全文表示, one request

兵庫's speaker index carries **no `downloadPos` checkboxes at all** — the download
form the other two tenants use is simply not on the page, so `GetPerson.exe` has
nothing to assemble and the 愛媛 flow dead-ends. What 兵庫 has instead is the
navigation frame's 全文表示 button:

```
GetText3.exe?Code=<code>&fileName=R070225A&startPos=0&keyMode=10&searchMode=1&FUNC=PRINT_ALL
```

`FUNC=PRINT_ALL` is the whole difference. Without it the same endpoint returns one
speech (~8 KB); with it, the entire sitting (~170 KB) comes back in **one GET** —
cheaper than 愛媛 and 三重, which need the speaker index first. `startPos` is
ignored under `PRINT_ALL` (0 and 272 return the same bytes), so the URL is
composable at listing time and is short enough to be the record's identity.

The body is HTML rather than plain text — one `<BR>` per line — so it is reduced
with `BeautifulSoup(...).get_text("\n", strip=True)` before the split rule runs.
The markers survive that unchanged, including the full-width space that separates
a speaker from their words.

## Not every document in the tree is a sitting

兵庫 lists 決議案・請願・意見書 beside its minutes, at both the year and the session
level, as `fileName=R07060004KETS.html`. 三重 lists a table of contents as
`fileName=R080119MOKU`. The old `fileName=([A-Za-z0-9]+)` pattern took the first
kind **with the `.html` cut off**, which then 404s one request later, and took the
second kind as a sitting with a real-looking date.

A sitting's name is `[RHS]YYMMDD` plus a serial letter, and `_SITTING` now requires
exactly that. A dotted name is a known kind and is dropped quietly; **any other
shape is logged as a warning**, because a silently dropped sitting is the failure
this project keeps paying for.

## One marker rule, and what each bound cost

All three tenants now use the same `speech_split`, and every part of it was paid
for by a document that broke an earlier version:

```
(?m)^○(?P<role>[^（(\n]{0,24})[（(](?P<speaker>[^）\n]{1,40}?)(?:議員)?[）)](?=[ 　（(])
```

- **`role` outside the brackets.** 三重, 兵庫, and 愛媛's 平成 archive all write
  「○知事（一見勝之）」 / 「○47番（岡田己宜君）」. Only 愛媛's modern documents write
  「○（三宅浩正議長）」 with everything inside, and there `role` is simply empty.
- **The lookahead, not a trailing space.** 「○議事日程（第３号）」 has a marker's exact
  shape and ends its line; a speaker is followed by their words. But 愛媛 平成3年
  opens speeches with applause — 「○47番（岡田己宜君）（拍手）統一地方選挙後…」 — so
  an opening bracket has to count too. Requiring a space dropped three of those.
- **40 characters, not 24.** 「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別
  委員長」 is 29 characters and is a real speaker. A 24-character cap silently
  dropped two speeches from the 愛媛 corpus — the same names this document cites
  as the reason 愛媛's name and office cannot be split.
- **`)` allowed inside the name.** 「○（大北秀特命担当部長(会計管理者)）」 exists.
  Excluding the ASCII bracket cut the speaker at the inner one and left the speech
  itself starting with 「）」 — wrong under the old rule too, and only visible
  because the corpus was re-parsed and diffed rather than eyeballed.

The rule change was checked by re-parsing all three corpora from cache and
diffing: 三重 unchanged, 兵庫 **+4** (the applause openings), 愛媛 unchanged at
11,548 with the long committee-chair names intact.

## 愛媛 has two generations too

The config that collected 2019 onwards would have collected **nothing** before
2011: 平成3年 uses 三重's marker shape, and a rule requiring 「○（」 matches zero
lines of every 平成 document. Since a zero-speech sitting does warn, this would
have been noisy rather than silent — but it would have been an entire archive of
warnings, discovered after the crawl rather than before it.

## Parsing notes

- Marker form is `○（名前役職）` — name and office run together inside one pair of
  parentheses, unlike 静岡's `○知事（鈴木康友君）` and 和歌山's two-form mix. No 「君」
  honorific, so 静岡's roster-vs-speech trick does not transfer; here the roster
  lines start `〇出席議員` with the *other* circle (U+3007 vs U+25CB) — verify that
  before relying on it.
- The response is `text/plain`-ish, so `detail.container` (a CSS selector) has
  nothing to select. This is the one real gap: the detail step assumes HTML.
- `<PAGE="n">` markers separate printed pages and should be stripped.

## Implemented

`KensakuSystemScraper` (`scrapers/kensakusystem.py`) plus `sites/ehime.toml`. This
is the first site that earned a `BaseScraper` subclass rather than selectors, for
three independent reasons: the tree is navigated through an `onClick` attribute
carrying a **cp932-encoded label**, a sitting must be assembled from a list of
character offsets, and the transcript is plain text with no markup to select.

`BaseScraper` gained one hook, `fetch_meeting`, for the general case of *a
transcript that is not at a URL the index can hand you*. Listing therefore costs
nothing per document, and because `fileName=R070303A` carries the date,
`--since/--until` prunes before **either** request — the one site so far where a
date filter genuinely saves work.

### Collected — 三重 and 兵庫 (2026-08-28)

```
三重  819 sittings  47,279 speeches  40,771,120 chars  1989-02-28 .. 2026-03-31
兵庫  809 sittings  42,314 speeches  34,968,714 chars  1986-02-22 .. 2026-06-11
愛媛  666 sittings  39,624 speeches  23,354,176 chars  1991-06-27 .. 2026-03-19
```

兵庫 is now the oldest material in the corpus by three years. Both were collected
in two passes — 2019-04 onwards first, then everything before 2011-04 — because
`fileName` carries the date and `--since/--until` prunes before either request.

Nothing undated, no duplicate URL, no digit or punctuation in any speaker name,
and — counted against the listing, per session — **every uncollected sitting is
inside the corpus window**: 240 of 1,059 on 三重, 210 of 1,019 on 兵庫, and nothing
else unaccounted for. 三重 has 515 speakers and 269 roles; 兵庫 has 621 and 75.

One 三重 sitting has no speeches: 平成2年9月20日, which reads
「〔本日は、開議に至らなかった〕」. The sitting never opened, so the warning is
right and the record is right.

**The honorific bug this collection surfaced** is in `CLAUDE.md`'s list, and it is
not local to this vendor: `_clean_speaker` stripped 「君」 only, so 「太田栄子さん」
and 「太田栄子」 counted as two speakers, as did 「酒井隆明氏」 and 「酒井隆明」. Ten
names for seven people, all of the splits on the non-「君」 side. Both corpora were
re-parsed from cache — no requests — once all three suffixes were stripped.

Two artefacts worth knowing, neither of them ours:

- 三重 prints 「○教育長（福永和伸教育長）」 in one 令和6年 sitting — the office twice,
  inside the brackets and out. One occurrence.
- 兵庫 occasionally runs a member's name into a committee title inside the
  brackets (「松本隆弘議会運営委員会委員長」), the 愛媛 problem in miniature. The
  ordinary member form (「北野　実議員」) splits cleanly and is by far the majority.

The archive before 2011-04 is a separate run; 2011-04 .. 2019-03 is left to the
地方議会会議録コーパス, as on 和歌山 and 愛媛.

### Collected — 愛媛, the whole archive (2026-08-28)

666 sittings, 39,624 speeches, 1991-06-27 .. 2026-03-19 — 平成3年第229回定例会 is
where the site's coverage starts, and the collected range begins exactly there.
243 sittings are uncollected and all 243 are inside the corpus window. No
honorific splits, nothing undated, no sitting without speeches.

Both marker generations are present and the 平成 documents populate `role` for
11,214 of their 27,734 speeches — the site changed forms partway through the
archive rather than at a clean boundary, which is why one rule has to take both.

### Collected — 愛媛, 2019-05 onwards (superseded by the line above)

```
meetings : 201          speeches : 11,194
chars    : 6,123,840    range    : 2019-05-15 .. 2026-03-09
```

33 sessions, 266 speakers, nothing undated, no sitting without speeches, no
duplicate, no mojibake. Scoped to the gap the 地方議会会議録コーパス leaves after
2019-03; 平成3年–2011年 is still uncollected and is the obvious next run.

**Corrected 2026-08-28: it was 201, and three sittings were missing.** The
listing offered 212; 8 of the 11 absences were `--since` doing its job and three
were fetch failures against the URL length limit below. Recovered, so the figure
is now **204 sittings, 11,548 speeches**.

### Three more faults, found on 三重 and 兵庫 (2026-08-28)

1. **`GetPerson.exe` 404s on a long URL, and that 404 is a length limit.** 2,102
   characters fetched; 2,119 returned **404**, identically on 三重 and 愛媛. A
   一般質問 day has ~115 speeches, which is just past it. `scrape()` catches
   `FetchError`, logs it and continues, so the sitting is simply not in the corpus
   afterwards — **three 愛媛 sittings were lost this way**, all 3月 days, and the
   only trace was three error lines in a run log nobody re-read. `fetch_meeting`
   now splits the offsets across as many URLs as it takes (`MAX_URL = 1800`) and
   concatenates the responses, dropping the `開催日：`/`会議名：` header the CGI
   repeats on every one. The three were recovered on 2026-08-28.

   The 愛媛 note that a download URL "runs past pydantic's 2,083-character limit"
   was recorded as a *modelling* problem and fixed as one. It was also a live
   fetch failure, and nothing connected the two for a day.

2. **兵庫's tree is a different generation of markup.** `data-depth="令和 7年 …"`
   on an `<A class="js-tree-submit">`, instead of `onClick="…treedepth.value='…'"`.
   The regex found nothing, and a tree with no nodes is indistinguishable from a
   year that does not exist. Both forms are read now.

3. **三重's speech marker is 静岡's, not 愛媛's.** 「○知事（一見勝之）」 — office
   outside the brackets, name inside — where 愛媛 writes 「○（三宅浩正議長）」. The
   愛媛 rule requires 「○（」 and matches **0 lines of every 三重 document**. The
   same rule shape works for both 三重 and 兵庫 and, unlike 愛媛, it separates name
   from office because the site does.

   It needs one guard: 「○議事日程（第３号）」 is a heading with the exact shape of a
   marker. Requiring a space after the closing bracket separates them — a heading
   ends its line, a speaker keeps talking. Counted across 8 sample sittings from
   昭和61年 to 令和7年: every real speech taken, only the 議事日程 line left.

### Four faults, each silent, each found only by running it

1. **Pydantic caps a URL at 2,083 characters.** The download URL for a 一般質問 day
   runs past that, so it cannot be a record's identity. A ref now points at the
   *speaker index* (~100 characters) and the download URL is composed inside
   `fetch_meeting`. This turned out better than the original design: listing no
   longer fetches anything per document.
2. **A `years` list can name unreachable nodes.** Opening a *tab* reveals the
   years it groups; a year's sessions appear only when that year is opened. Naming
   令和 2年 or 平成31年 — which are not tabs — reached nothing, and five of the eight
   years asked for were skipped **without a word**. The walk is now two-phase, and
   a year the tree does not have is reported.
3. **The charset is not detectable.** `GetPerson.exe` returns plain text with no
   meta tag and no `charset` on the response, so `sniff_encoding` has only
   charset-normalizer — and it guessed **utf-8** for 5 of 63 sittings, which
   decoded to mojibake. Those five parsed to zero speeches and warned; on a
   different document the same miss produces plausible garbage instead. The
   config now states `encoding = "cp932"` rather than detecting it.
4. **「令和元年」 is a year node and 元 is not a digit.** `dates.py` has handled that
   form since 静岡, but the new `_YEAR_NODE` pattern used `\d{1,2}` and skipped the
   node entirely — walked, matched nothing, said nothing. Caught only because the
   collected range started at 2020 instead of 2019.

### Speaker and office are not separable

The marker is 「○（三宅浩正議長）」 — name and office in one run with no delimiter.
There is no lexical rule that splits them: 「三宅浩正議長」 breaks wrongly under both
greedy and lazy matching, and the corpus contains
「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長」. So the whole string is
stored as `speaker` and `role` is left empty, rather than guessing.

Splitting it properly means reading the 出席理事者 roster in each document, where
office and name *are* separated by whitespace
(「　保健福祉部長　　　　　　岡　部　　　直」). That is real machinery and is
deliberately deferred — but it is the right way, and it would also give 三重 and
兵庫 the same treatment.

## Still to do

- 平成3年–2011年 for 愛媛 (`years = []` walks the whole archive).
- 委員会会議録: the same tree carries them; `sessions` selects 本会議 today.
- 愛媛's name/office split, which needs the 出席理事者 roster. 三重 and 兵庫 do not
  need it — they print the two separately.
