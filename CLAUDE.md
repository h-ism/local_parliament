# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Collects transcripts of Japanese prefectural assembly (都道府県議会) proceedings into a
JSONL corpus for research.

## Workflow

- Never write code directly on `main`. Create a branch for any code change before committing.
- Record each branch of work in `LOG.md` (newest first): what changed, why, and what was verified.

## Commands

The project is uv-managed; everything runs through `uv run`.

```bash
uv sync                       # create .venv and install
uv run pytest                 # full suite (offline — no test touches the network)
uv run pytest tests/test_dates.py::test_parses_known_forms   # single test
uv run ruff check . && uv run ruff format .
uv run mypy                   # strict; must stay clean
uv run pt --help              # the CLI
uv run pt export data/<pref>.jsonl   # JSONL corpus -> CSV (one row per speech)
```

## Architecture

The central idea: **a prefecture is a TOML config, not a Python module.** Most
assemblies publish through one of a few vendor 会議録検索システム products that share
the same page shape — a paginated result list linking to per-sitting detail pages —
and differ only in CSS selectors. So `GenericScraper` is driven entirely by a
`SiteConfig`, and adding a prefecture means adding `sites/<name>.toml`. Reach for a
new `BaseScraper` subclass only when a site genuinely cannot be expressed as selectors.

Flow: `sites/*.toml` → `SiteConfig` → `GenericScraper` → `PoliteClient` (fetch) →
`Meeting` models → `TranscriptStore` (JSONL).

A config may name `scraper = "..."` to select something other than `GenericScraper`;
`kensakusystem` is the one case so far, and `docs/kensakusystem.md` records the
three independent reasons it earned the exception.

Modules under `src/prefectural_transcripts/`:

- `http.py` — `PoliteClient`. Per-host rate limiting, robots.txt + `Crawl-delay`,
  retries honouring `Retry-After`, and a disk cache of every response body.
  Also `sniff_encoding`: many of these pages are Shift_JIS/EUC-JP and declare it
  only in a `<meta>` tag, or are proxied with a wrong HTTP `charset=` — so the meta
  tag is trusted over the header, with charset-normalizer as the fallback.
- `scrapers/base.py` — `BaseScraper` splits listing (`list_meetings` → cheap
  `MeetingRef`s) from fetching (`parse_meeting`). That split is what makes crawls
  resumable, date-filterable, and cappable without the listing logic knowing about
  transcripts. `scrape()` applies the date filter twice: once on the listing date,
  again after parsing when the real date is known.
- `scrapers/generic.py` — the config-driven scraper and the `SiteConfig` dataclasses
  that mirror the TOML schema. Two escape hatches for markup CSS cannot express:
  `detail.speech_split` (regex on the 「○発言者」 convention, for transcripts with no
  per-speech elements) and `detail.patterns` (regex per field, for legacy tables
  that label cells by text).
- `dates.py` — 和暦 parsing (`令和7年6月10日`, `令和元年`, `R7.6.10`), western forms, and
  Domino's month-first `06/23/2025`.
  Assembly pages almost never use ISO dates; always parse through here.
- `models.py` — `Speech` / `MeetingRef` / `Meeting`. Note `datetime` is imported as
  `dt` because both models have a field named `date`, which would otherwise shadow
  the type inside the class body and break pydantic's annotation evaluation.
- `storage.py` — JSONL writer, one file per prefecture; `seen_keys()` drives resume.
  `SpeechCsvWriter` / `write_csv` render the same records as a flat CSV (one row
  per speech) for analysis; JSONL stays canonical.

## Conventions

- **Crawl politely.** Defaults (2s per host, robots respected, everything cached)
  are a deliberate choice about small public-sector servers, not a placeholder.
  Don't lower them to make a run faster.
- **Don't invent selectors or URLs.** A config goes into `sites/` only once its
  selectors have been checked against the real markup. Work them out with
  `uv run pt inspect <url> --selector <css>`, then confirm with
  `pt scrape <name> --limit 1`. Drafts for sites we may not crawl yet live in
  `docs/`, not in `sites/`, so `pt sites` never lists something that cannot run.
- Tests use `FakeClient` and inline HTML fixtures from `tests/conftest.py`; keep the
  suite offline.
- `data/` and `cache/` are gitignored — scraped output is data, not source.

## Where this stands (updated 2026-08-28)

Read `docs/collection-targets.md` first — it is the ranked answer to "where can we
collect", with the cost of each target. `docs/prefecture-survey.md` still maps all
47 assemblies but two of its verdicts are now superseded. Per-site detail is in
`docs/<prefecture>.md`; drafted letters are in `docs/inquiries/`.

**Collectable today** (figures 2026-09-04; `committee` separates the two in each file)

| | 本会議 | 委員会 | Range |
| --- | --- | --- | --- |
| **和歌山** | 916 / 47,377 | 163 / 7,814 | 本会議 1989-02-27〜, 委員会 2023-05-19〜 |
| **三重** | 1,059 / 62,940 | 426 / 39,530 | 本会議 1989-02-28〜, 委員会 2023-01-18〜 |
| **愛媛** | 909 / 53,631 | 2,214 / 154,702 | 本会議 1991-06-27〜, 委員会 2007-05-11〜 |
| **兵庫** | 1,020 / 55,035 | 4,378 / 219,787 | both from **1986** |
| **静岡** | 113 / 1,395 | — | 2025 only |

**11,198 sittings, 642,211 speeches, 290,961,845 characters.** Sittings/speeches
per cell. Configs: `sites/{wakayama,wakayama_committee,mie,ehime,hyogo,shizuoka}.toml`.

- The **corpus window (2011-04 .. 2019-03) is collected** on 三重・愛媛・兵庫, both
  本会議 and 委員会, decided 2026-09-04: whether the 地方議会会議録コーパス includes
  committee minutes is unverified, and its letter is still unsent. **和歌山 still
  has the window open on its 本会議 side** — 252 documents, its config not re-run.
- 静岡's full archive and its 委員会 (`comgiji.nsf`, surveyed 2026-09-04, paginated
  30 rows at a time) both wait on the `meta robots` question; see `docs/shizuoka.md`.
- Each tenant's listing reconciles item by item against its corpus. 和歌山 carries
  one undated sitting because the site prints 「平成八年七年十日（水曜日）」.

**"The same product" is not the same site**

三重 and 兵庫 were recorded for a day as "a config away" from 愛媛 because they
share a host, a `cgi-bin3`, a charset and a tree shape. They differ in the three
places that decide whether a config collects anything, and every difference fails
*quietly*:

- **兵庫's tree is newer markup** — `data-depth="令和 7年 …"`, not
  `onClick="…treedepth.value='…'"`. The old regex found no nodes, and a tree with
  no nodes reads exactly like a year that does not exist.
- **兵庫 has no ダウンロード button.** No `downloadPos` checkboxes at all, so the
  愛媛 route dead-ends. Its 全文表示 (`GetText3.exe?…&FUNC=PRINT_ALL`) returns the
  whole sitting as HTML in **one** request — cheaper than either of the others.
- **三重's marker is 静岡's shape, not 愛媛's** — 「○知事（一見勝之）」 against
  「○（三宅浩正議長）」. 愛媛's rule matches **zero** lines on every 三重 document.

The rule that took 三重 and 兵庫 needs one guard: 「○議事日程（第３号）」 has a
marker's exact shape, and only the space after the bracket separates a heading
from someone still talking.

See `docs/kensakusystem.md`.

**Blocked, and why it is not a scraping problem**

24 assemblies forbid crawling in `robots.txt` (DB-Search's blanket `Disallow: /`,
gijiroku VOICES' CGI directory). No amount of selector work changes that; the way
through is `docs/inquiries/`. Don't set `PT_RESPECT_ROBOTS=0` to get around it —
that is the researcher's call, not ours, and it contradicts the politeness
convention above.

**SSP — 18 prefectures, blocked (corrected 2026-08-27)**

This was recorded for two days as "allowed, blocked only by architecture". It is
not. `config.js` declares `API_ROOT: "/dnp/search/"`, and `/dnp/search/` is outside
the one `Allow: /tenant/` rule, so `Disallow: /` covers it — DENY under
`urllib.robotparser` and under longest-match too. **The shell pages are crawlable;
the data is not.** SSP belongs with the 24 blocked assemblies: it needs a letter,
not a scraper.

The lesson generalises: **a robots.txt verdict is not final until you know the URL
that actually carries the data.** A client-side app can be allowed everywhere you
can see and disallowed everywhere it matters.

Vendor: **NTT Advanced Technology** (copyright header). "DNP" is the product,
Discuss Net Premium — not 大日本印刷; an earlier note misread the logo. Tenant ids
and browse endpoints are in `docs/collection-targets.md`. 大阪 gets the first
letter: it is the only one of the 18 naming a destination on its own page, and its
reuse condition (data rights belong to the assembly) survives any robots answer.
See `docs/inquiries/ssp-assembly.md`.

**Before any large crawl**

**Scope is settled: every period we can obtain, no research window.** That makes the
地方議会会議録コーパスプロジェクト (<http://local-politics.jp/>) more relevant, not
less: it already covers all 47 assemblies for **2011-04 to 2019-03** — fiscal years,
so the boundaries are not where you would guess — which is not a range to route
around but a large piece of exactly what we want, already assembled. Ask for it
rather than re-crawling it; the letter is drafted and unsent
(`docs/inquiries/local-politics.md`, addressee 要確認). Note the gap it leaves:
**2019-04 .. 2019-12** falls between that corpus and any collection that starts at a
calendar year.

**Superseded 2026-09-04 for 三重・愛媛・兵庫**, which were re-run without
`--since/--until` and now hold the window itself, 本会議 and 委員会 alike. The
reason is in the letter: it *asks* whether that corpus includes 委員会 at all, so
routing around the window assumed an answer nobody has. 和歌山's 本会議 window —
252 documents — is the one hole left, and closing it is a decision, not an
oversight.

## Things that will bite again

Learned from 静岡; expect them on other sites rather than treating them as local
quirks.

- **Encoding lies, and fails silently.** Those pages declare `charset=utf-8` in a
  meta tag, send `Shift_JIS` in the header, and contain cp932. Base Shift_JIS
  cannot decode the NEC/IBM characters ordinary names use (河原﨑, 髙梨), and the
  failure surfaces as *plausible garbage*, not an exception — it was caught only
  because 8 documents parsed to zero speeches. `sniff_encoding` maps Shift_JIS to
  cp932 for this reason. When a parse comes back suspiciously empty, check the
  decoded text before touching the selectors.
- **One label is rarely enough.** 静岡 labels the date 質問日 on question
  documents and 発言日 on report documents; matching one left 60 of 113 records
  undated. Check a sample of *each document type*, not just the interesting one.
- **Speech markers come in more than one form on the same page.** 和歌山 writes
  office-holders as 「○知事（岸本周平君）」 but members as bare 「○濱口太史君」, with no
  parentheses at all; 愛媛 runs name and office together as 「○（福羅浩一議長）」.
  A split rule copied from another prefecture will match the minority form and drop
  the rest silently. Count what a rule catches against a sample before trusting it.
- **Nonsense output is a third failure mode, and nothing warns about it.** A
  sitting that parses to zero speeches warns; an index that yields nothing does
  not; and a rule that yields *plausible garbage* does not either. 和歌山's greedy
  speaker group produced 21-character "speakers" made of speech text, and 〇-as-a-
  numeral produced four more. Found only by sorting the speaker list by length and
  grepping it for digits and punctuation. **Do that on every corpus before
  trusting it.**
- **A bound in a rule is a claim about the data, and it will be wrong.** The
  unified `speech_split` for 愛媛・三重・兵庫 capped a speaker at 24 characters,
  which is generous until 「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長」
  turns up — 29 characters, a real speaker, and one of the very names this project
  already cites elsewhere. It also excluded `)` from a name, until
  「○（大北秀特命担当部長(会計管理者)）」 turned up. Both losses were three speeches in
  a 11,548-speech corpus and neither warned. **Re-parse and diff before and after
  a rule change** — it costs nothing from cache and it is the only thing that sees
  a loss this small.
- **Judge a candidate rule by what it loses, not only by what it fixes.** Three
  fixes for the same four false positives lost 7, 15 and 0 real speeches
  respectively; all three looked reasonable written down. Re-parsing the whole
  corpus to compare costs zero requests because every response is cached — which
  is what the cache is for.
- **A URL length limit can wear a 404.** `GetPerson.exe` serves 2,102 characters
  of URL and returns **404** at 2,119 — on two different tenants, identically. A
  一般質問 day carries just enough offsets to cross it, `scrape()` logs the
  FetchError and moves on, and the sitting is then absent from the corpus with
  nothing but one line in a run log to say so. It cost 愛媛 three sittings, found
  a day later by counting the listing against the corpus. **When a fetch fails on
  the busiest documents only, suspect the length of the request, not the server.**
- **A node that is walked but matches nothing is the quietest failure of all.**
  愛媛's tree has a 「令和元年」 node, and 元 is not `\d`; the year was visited,
  matched no sessions, and nothing warned. Likewise a `years` entry naming a node
  the tree does not have. **Check the edges of the collected range after every
  run** — that is what caught both.
- **A listing-level miss has no smoke test.** 和歌山 labels the whole-sitting link
  「◎第３号全文」 in most sessions and 「◎第１号本文」 in others; filtering on 全文
  dropped three entire sessions in silence. A detail page that parses to zero
  speeches at least warns — an index page that yields no links looks exactly like
  one that was never asked for. After a scoped run, **count what you got against
  what the index lists**, per session, rather than trusting the total.
- **Indexes are hand-maintained and they break.** 和歌山's 令和7年6月 page links its
  第6号 with a truncated label and an href pointing into the previous year, so a
  real sitting is unreachable from the site's own navigation. `list.extra_meeting_urls`
  exists for this; verify the URL against the live page before adding it.
- **The 「○」 is not always the same character.** 和歌山 marks most sittings with
  ○ (U+25CB) but one with 〇 (U+3007, IDEOGRAPHIC NUMBER ZERO), and 〇 is *also* the
  numeral in 「二〇〇三年度」. Match both circles and require the 「君」 suffix; the
  suffix rejects the numerals and the roster in one rule. This one surfaced only
  as a sitting that parsed to zero speeches — the same signature as the 静岡
  encoding bug, and worth treating as the standard smoke test.
- **Honorifics are not uniform across prefectures, and this one bit.** 和歌山 marks
  every member 「君」 regardless of gender, but its 議長 says 「６番森礼子さん」 aloud.
  A 「君」-only rule would drop women's speeches wholesale on any site that marks
  them 「さん」. Verify per site — it is a corpus-bias problem, not a parsing detail.

  **What it actually did on 三重 and 兵庫** was quieter than dropping anything:
  `_clean_speaker` stripped 「君」 and left 「さん」 and 「氏」, so 「太田栄子さん」 and
  「太田栄子」 were two speakers, 「酒井隆明氏」 and 「酒井隆明」 two more. Ten names for
  seven people, every one of the splits on the non-「君」 side — which is to say the
  women and the outside witnesses. Nothing warned; the corpus simply counted them
  twice. All three honorifics are stripped now. **Check for a name that appears
  both with and without a suffix after every collection.**
- **Structure can be coincidence.** 「○出　席　議　員（六十七名）」 is an attendance
  roster with the exact shape of a speech marker 「○知事（鈴木康友君）」. Requiring
  the 「君」 honorific separated them. Verify a split rule against a sample and
  count what it catches.
- **A date filter is not a crawl limit.** `--since/--until` are applied after a
  page is fetched, so on an index carrying no dates they save nothing. Narrow
  `--start-url` instead.
- **Count the listing against the corpus after every run.** Not the total — the
  per-item difference. 愛媛 reported 201 sittings and looked complete; the listing
  offered 212, and of the 11 missing, 8 were correctly filtered by `--since` and
  **3 were fetch failures nobody had noticed**. Re-listing costs nothing because
  every page is cached, and it is the only check that catches a document the
  crawler asked for and failed to get.
- **Naming the nodes you want is a way of losing them.** `sessions = '定例会|臨時会'`
  read as a scope decision and worked as a filter on the site's typing: 兵庫's tree
  carries 「昭和61年 第198回定 」, a label truncated mid-word, and the node was never
  opened — the sitting of 1986-06-05 was simply absent, with nothing in any log.
  All three kensakusystem configs now say `sessions = '.'`. **A node that is never
  opened cannot warn**, which is the listing-level version of the same lesson.
- **委員会 are not 本会議 in a different room.** On the same tenant, with the same
  fetch route, the marker moves: 兵庫 leaves it alone on its line and starts the
  speech on the next one, 三重 drops the brackets entirely (「○小島委員長　　…」),
  and 和歌山 does not publish a transcript at all — its committees are 要点筆記 with
  「●委員長」 and 「Ｑ／Ａ」 markers. Sample a committee document from every
  prefecture before assuming its 本会議 rule carries over; all three cases took
  **zero speeches** under the rule that collected 本会議.
- **On committees, zero speeches is often correct.** A 「質疑　なし」 day is a real
  record of a few hundred characters. That breaks the project's oldest smoke test,
  so the warning now carries the document size: 1,570 bytes is a procedural
  sitting, 60,000 is a rule that has stopped matching.
- **Full-width and ASCII digits split a name in two.** 和歌山's committees type
  their own headers, and the three sittings of 令和8年2月 write it 「令和８年２月」,
  「令和8年2月」 and 「令和８年2月」 — one session under three names, the speaker-split
  failure one field over. The 本会議 side does not do this (131 sessions, each
  written one way). Check a metadata field for digit-width variants the same way
  you check speakers for honorifics.
- **A bracket class is a claim about two different kinds of bracket.** 兵庫 writes
  「○まちづくり部参事(園芸・公園担当)兼公園緑地課長（北村智顕）」: the marker's own
  brackets are full-width and the *office* contains half-width ones. A role class
  that stopped at any opening bracket cut the office at 「参事」 and let the name
  group swallow 「園芸・公園担当)兼公園緑地課長（北村智顕」 — **a speaker made of an
  office, 124 speeches of it, and nothing warned.** Check which bracket a site
  uses for the marker itself before excluding the other.
- **A length bound on a role is the same claim as one on a name.** 「○高校教育課学校
  支援推進官兼義務教育課学校支援推進官（辻　登志雄）」 is a 26-character office, and a
  24-character cap matched *nothing* on that line — so the speech was swallowed
  into the speaker before it, 9 of them in one committee sitting. The corpus was
  short 55 speeches on that bound alone.
- **Excluding digits is usually wrong.** Two false positives — a numbered heading
  「○３　閉会中の継続調査事件」 and a speech opening 「（１）（２）（３）とあるんですが」 —
  invite a no-digits rule for speakers. It costs **33 real speeches**, because
  兵庫 puts name and office in one pair of brackets and offices are numbered:
  「○（陰山　地域整備第１局長）」. The guard that works is narrower: a speaker may not
  be *only* digits, and may not *begin* with one.

- **Check `robots.txt` before writing any config.** It is one request and it
  decides whether the rest of the work is worth doing. But it decides it only for
  the URLs you know about: SSP's `/tenant/` is allowed and its `/dnp/search/` API
  is not, so the verdict flipped the day the data URL was found. **On a client-side
  app, read the verdict as provisional until you know where the data comes from.**
- **`urllib.robotparser` ignores `Allow:` precedence.** It returns the first rule
  matching in file order, so `Disallow: /` above `Allow: /tenant/` denies
  everything; RFC 9309 and Google resolve by longest match and would allow
  `/tenant/`. `PoliteClient` uses the stdlib parser, so it will refuse sites whose
  operators plainly meant to permit them. Not yet a problem — SSP is denied under
  both readings — but check this before concluding that a site with a broad
  `Disallow` plus a narrow `Allow` is closed.
- **State the charset when the response cannot carry one.** `GetPerson.exe` returns
  plain text with no meta tag and no `charset`, so detection is a guess — and it
  guessed utf-8 for 5 of 63 sittings. Where the vendor's charset is known, say it
  in the config instead of sniffing.
- **`HttpUrl` caps a URL at 2,083 characters.** A URL built from per-speech offsets
  will exceed it on a busy sitting. Do not use a composed URL as a record's
  identity; point at something short and stable and compose in `fetch_meeting`.

## Working notes

`JOURNAL.md` (untracked, gitignored) holds the running diary: decisions, dead
ends, mistakes, and contacts not yet verified. `LOG.md` stays the tracked record,
newest first, one entry per branch.
