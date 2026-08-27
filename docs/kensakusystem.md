# `kensakusystem.jp` — 三重・兵庫・愛媛

Verified against 愛媛 on 2026-08-27; 三重 and 兵庫 confirmed to be the same install.
**Collectable.** The whole flow works over plain GET, and the site's own download
button hands back a full sitting in one request.

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
| 兵庫 | `/hyogopref/` | `rpo2cq1zucjm5gwgk4` | 本会議・予算特別委員会・決算特別委員会 **昭和61年第197回定例会**〜 |
| 愛媛 | `/ehime/` | `e7c7rvxas7fwx1belp` | 本会議 平成3年第229回定例会〜; 委員会 平成19年5月〜 |

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

## Parsing notes

- Marker form is `○（名前役職）` — name and office run together inside one pair of
  parentheses, unlike 静岡's `○知事（鈴木康友君）` and 和歌山's two-form mix. No 「君」
  honorific, so 静岡's roster-vs-speech trick does not transfer; here the roster
  lines start `〇出席議員` with the *other* circle (U+3007 vs U+25CB) — verify that
  before relying on it.
- The response is `text/plain`-ish, so `detail.container` (a CSS selector) has
  nothing to select. This is the one real gap: the detail step assumes HTML.
- `<PAGE="n">` markers separate printed pages and should be stripped.

## What the scraper still needs

1. **Two-level listing** — year → session → sitting. Same gap as 和歌山.
2. **A non-HTML detail mode** — apply `speech_split` to the raw body when there is
   no markup to select.
3. **A listing step that reads `downloadPos` values and composes the next URL**,
   which is more than "follow a link". This is the one place a small
   `BaseScraper` subclass may be cheaper than stretching the config schema.
