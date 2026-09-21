# SSP / Discuss Net Premium — 17 assemblies

`https://ssp.kaigiroku.net/tenant/<tenant>/` — NTT アドバンステクノロジ's
会議録検索システム, used by 18 prefectural assemblies. **17 of them are configured
here. 大阪 is not**, and the reason is the first section.

Written 2026-09-18, when this moved out of `docs/collection-targets.md`'s Tier 2
("blocked; needs a letter, not a scraper").

---

## 1. What changed, and what did not

The operator was asked and **did not refuse**. 大阪 alone is still being
confirmed.

That is worth stating precisely, because it is not a permission:

> **明示的な拒否がないだけ。** There is no message saying yes. There is the absence
> of a no.

Collecting on that basis is the researcher's decision, taken 2026-09-18, together
with the rate it was taken with — **5 seconds per request, not the project's
default 2**. It is recorded in three places that a later reader cannot miss:

* every `sites/ssp_*.toml`, in a `[robots]` table that refuses to load without a
  reason and a date (`RobotsExemption`);
* every run log, because the client logs the exemption at WARNING the first time
  it fires, with the reason and the date in the line;
* `LOG.md`, under 2026-09-18.

**大阪 has no config in `sites/`.** That is deliberate and follows the project's
rule about `docs/` versus `sites/`: `pt sites` must never list something we have
decided not to run. Its reuse condition is also still open — 「このデータの権利は、
大阪府議会に帰属します」 — and that condition survives any answer about access.

### robots.txt, exactly

```
User-agent: *
Disallow: /
Allow: /tenant/
Disallow: /tenant/js/
Disallow: /tenant/css/
Disallow: /tenant/help/
Disallow: /tenant/stats/
```

Two different things are going on, and the exemptions are scoped to keep them
apart:

* **`/dnp/search/`** — the API, and the only place the text exists. Outside the
  `Allow:`, so `Disallow: /` covers it. *This is the part the decision covers.*
* **`/tenant/<tenant>/`** — the operator plainly allows this. It is exempted only
  because `urllib.robotparser` returns the first rule matching in file order, so
  the blanket `Disallow: /` above the `Allow:` denies it; RFC 9309 and Google
  resolve by longest match and would allow it. See CLAUDE.md, which flagged this
  before it mattered.
* **`/tenant/js/`, `/tenant/css/`, `/tenant/help/`, `/tenant/stats/`** — narrow,
  specific refusals, not vendor boilerplate. **Not exempted.** The client refuses
  them on its own, which is why the exemption is a list of prefixes rather than a
  switch. `config.js` was read by the researcher in a browser; nothing here
  fetches it.

---

## 2. The protocol

No page is server-rendered: `MinuteView.html` is an empty shell and
`<span id="council-title">` is empty in the served HTML. Three POSTs describe the
whole archive. Each takes JSON and returns JSON, `\u`-escaped, with no session,
no cookie and no login — `users/login` exists but nothing needs it.

```
POST /dnp/search/councils/index            {"tenant_id": 354}
  -> every 会議 the tenant publishes, all years, in one response (宮城: 1 MB)

POST /dnp/search/minutes/get_schedule_all  {"tenant_id": 354, "council_id": 4258}
  -> that 会議's sittings: schedule_id + a label like "06月17日－01号"

POST /dnp/search/minutes/get_minute        {"tenant_id": 354, "council_id": 4258,
                                            "schedule_id": 2}
  -> the sitting, as one block per utterance
```

`tenant_id` is published by the tenant itself at
`/tenant/<tenant>/js/tenant.js`, which contains one line
(`dnp.params.tenant_id = 354`). All 17 were checked against it on 2026-09-18.

`councils/index` **ignores `view_year`** and returns everything, so listing costs
one request per 会議 and nothing per year. `get_schedule_all` is used rather than
`get_schedule` because the latter repeats the whole roster for every sitting —
137 KB against 650 bytes for one 定例会 — and the roster arrives with the
transcript anyway.

Permalinks (`MinuteView.html?council_id=&schedule_id=`) are composed as a
record's identity and **never fetched**; they are short, stable and the site's
own link.

### The listing has two roots, and one of them is not proceedings

```
全会議 / 本会議 / 定例会
全会議 / 委員会 / 常任委員会 / 総務企画委員会
全会議 / 特別委員会                          <- 宮城 files 1,063 会議 here
資料   / 定例会資料                          <- not proceedings
資料   / 請願一覧表
資料   / 意見書・決議
```

**2,399 of the 17,309 会議 across the 17 tenants hang under 「資料」** and are
skipped. They are documents, not sittings: 山形's 「議第69号～議第93号」 is a list of
bill titles, and it reaches the corpus as a record with no date and no speaker if
nothing stops it. 熊本 would have contributed 728 of them, 福島 336.

Three more things the listing will not tell you unless you look:

* **`view_year` is not the year printed on the 会議.** 宮城 files
  「平成　１年　１２月　決算特別委員会」 under 1990. The year comes from the 会議's own
  name; the node is used only to catch a name that cannot be true (below).
* **The type path and the 会議 name disagree.** 宮城 files
  「平成３０年　３月　環境生活農林水産委員会」 under a node typed 環境生活委員会, and files
  1,063 委員会 under a node typed only 「特別委員会」 whose real names —
  大震災復興調査特別委員会 among them — exist nowhere but the 会議 name. The name
  wins; the disagreement is logged.
* **A bill number also ends in 号.** A sitting's label is 「06月17日－01号」 or
  「02月24日-一般質問及び質疑(代表)-02号」 (福島); 山形's materials are labelled
  「発議第12号」. A sitting label must *begin* with a date and *end* with 号 —
  requiring only the 号 collects bill lists, requiring only the date collects the
  目次.

---

## 3. What the vendor does for us

**It splits the speeches.** A sitting comes back as `tenant_minutes`, one block
per utterance:

| code | type | what it is |
| --- | --- | --- |
| 1 | 目次 | index |
| 2 | 名簿 | roster and front matter |
| 3 | △議題 | agenda heading |
| 4 | ○議長 | the chair speaking |
| 5 | ◆質問 | a question |
| 6 | ◎答弁 | an answer |
| 7, 8, 9 | 一覧, 文書, 資料 | documents |

(From `dnp.config.MINUTE_TYPE_CODE`, so these are read and not guessed.) 4, 5 and
6 are speeches; the rest are structure.

**Counted over all eleven finished tenants (2026-09-21): codes 7, 8 and 9 do not
occur at all.** 1,387,619 blocks, and every one of them is 名簿 (16,636), △議題
(90,567), ○議長 (517,021), ◆質問 (358,966) or ◎答弁 (404,429). That closes a
question this file left open — whether treating only 4/5/6 as speech silently
drops a 文書 block carrying text, the way 静岡's 答弁文書 would have. It does not,
on these tenants. Re-run the census on the remaining six. Each block's `title` **is** the speaker
line — 「知事（村井嘉浩君）」 — and its `body` is the words, inside a single `<pre>`.

This removes the failure mode that has cost this project more than any other.
Every other site here finds its boundaries by matching a 「○」 marker, and a marker
that stops matching hands one member's words to whoever spoke before them with
nothing to show for it — 静岡 lost 124 speeches that way, 兵庫 55. **Here there is
no marker to miss.** The body repeats it, and it is removed only when it matches
the title exactly.

### …except where it does not split them at all

**神奈川 puts a whole committee sitting in one 議題 block.** No per-speech blocks,
no 「○」, up to 128,001 characters in a single `minute_type_code: 3` — which this
scraper read as a heading and discarded. **2,177 sittings, 410,423 speeches,
110,002,781 characters**, every one of them warning
`no speeches extracted (46894 bytes)` into a log nobody read. Found on
2026-09-21 by exporting CSV: the row count did not match the speech count,
because a sitting with no speeches still gets a row.

The block's own title says which kind it is, and that is the discriminator:

| title | what it holds | what to do |
| --- | --- | --- |
| `《委員会記録-令和５年第１回定-…》` | the whole proceedings | parse it |
| `《本会議録-…-出席議員等・議事日程》` | attendance and the order paper | leave it |

The second is not duplicated in the speech blocks beside it — checked before the
parser was written — so `_from_committee_record` is consulted **only when the
ordinary blocks yielded nothing**, and a sitting the vendor did split is never
read twice.

Inside, the layout is the same from 2004 to 2023 and needs no marker:

```
５　同上質疑（両局所管事項も併せて）

永田(て)委員
　自民党の永田てるじです。企業庁関係で幾つか質問をいたします。
経営課長
　ただいま策定をしようとしております長期構想でございますが、
```

A speaker is a line that is **not** indented and **is** followed by one that is.
That single condition carries the front matter (委員会名, 開催日, 出席者氏名 — runs
of unindented lines) and the order of business (「５　同上質疑」 — begins with a
digit) out of the way on its own. A record with no indented lines yields nothing,
which is right: 547 of 神奈川's sittings are 「１　開　　会」 and a closing, and
zero speeches is what they are.

**Look for this on the remaining tenants.** The census in the table above counted
blocks, not their length; what matters is a code-3 block with a transcript in it.
山口 has 61 large ones and 奈良 3, and both are 《本会議録》 order papers in
documents that already have speeches — nothing lost there.

---

## 4. What is still hard: the speaker

The `title` gives the speaker, but how it gives it differs by tenant, and this is
the one place where SSP needs judgement.

| shape | example | tenants |
| --- | --- | --- |
| brackets | 「知事（村井嘉浩君）」, 「二十三番（天下みゆき君）」 | 宮城, 山形, 福島, 岐阜, 奈良, 岡山, 徳島, 神奈川… on 本会議 |
| office in its own brackets | 「番外［知事］（千葉三郎君）」 | 宮城, 昭和22年 |
| name + office, run together | 「高橋宗也委員長」, 「梅澤佳一委員長」 | 委員会 everywhere; 大分 on 本会議 too |
| surname + office | 「冨岡委員長」 (名簿 says 冨岡孝介) | 長崎 |
| office alone, no name | 「委員長」, 「健康福祉部長」 | 秋田's 委員会 |

`split_title` reads the answer off the document, three ways, and refuses to guess
a fourth:

1. **Brackets.** The name is the final bracket pair. Exact.
2. **A name from the sitting's own 名簿.** Where the title starts with a name the
   document lists, the rest is the office.
3. **An office from the 名簿, corroborated by a name from it.** 「冨岡委員長」 splits
   because 委員長 is on that roster *and* 「冨岡」 begins 「冨岡孝介」.

Anything else is kept whole, with `role = None`, and counted as
`speakers unsplit` in the run report.

### Why not an office vocabulary

Because 大分 writes 「渡邊直二公安委員長」. A plausible list of offices containing
委員長 splits that into speaker 「渡邊直二公安」 — **a speaker made of an office**,
which is the 兵庫 failure verbatim, and nothing warns. 公安委員長 is not on that
sitting's roster and 渡邊直二 is not one of its members, so the title stays as
printed. An office list was written, measured and removed for this reason.

### What it costs, measured on two documents per tenant

`speakers unsplit`, against total speeches:

| tenant | unsplit / speeches | why |
| --- | --- | --- |
| 宮城, 山形, 福島, 岐阜, 奈良, 岡山, 徳島 | 0 | brackets, or a roster that parses |
| 大分 | 3 / 234 | roster parses; the 公安委員長 above is one of the three |
| 神奈川 | 1 / 30 | |
| 山口 | 3 / 40 | |
| 熊本 | 15 / 48 | titles that are a bare name with no office |
| 長崎 | 77 / 209 | 分科会長 and officials, absent from the 委員 roster |
| 秋田 | 160 / 165 | **the source prints no names** on 委員会 — office only |
| 高知 | 152 / 152 | no machine-readable roster in the document |
| 新潟 | 143 / 143 | " |
| 沖縄 | 293 / 293 | " |
| 埼玉 | 750 / 750 | its 名簿 block is the session header; the 委員出欠表 is a **scanned image** |

**The known limitation, stated plainly:** on 埼玉・沖縄・新潟・高知 (and 秋田, where
the source itself has no names) a committee speaker is stored as printed —
「梅澤佳一委員長」 — so the same person is a different speaker in 本会議, where the
brackets give 「梅澤佳一」. This is the 愛媛 duplicate-speaker problem, and it is
open on those tenants.

**The way to close it was a pass over the finished corpus, not a rule in the
scraper** — `scripts/split_titles.py`, run 2026-09-21 over the eleven finished
tenants.

It takes the offices from *every* corpus in `data/` (2,478 distinct roles, each
of which reached a `role` field from a title that was already unambiguous) and
the names from each prefecture's own bracketed titles, and splits a title only
when a known office ends it. Three strengths of claim, counted apart:

1. **the residual is a name this prefecture states elsewhere** — 「赤嶺昇議長」
   beside 「議長（赤嶺昇）」;
2. **the residual is the unique start of one** — 長崎's 「冨岡委員長」 against a
   roster reading 「冨岡孝介」; where several names start that way, the office
   decides if exactly one of them has ever held it (「黒岩知事」), and otherwise
   the title stands;
3. **office only** — a committee member who never spoke in 本会議 has no
   bracketed title anywhere, so nothing states their name. The longest office in
   the vocabulary is still evidence, and the residual is rejected if it ends in
   an office itself.

That last guard is what makes this safe where the scraper's own list was not:
「渡邊直二公安委員長」 splits on 公安委員長 — which is in the vocabulary because
other assemblies print it separately — and so cannot become 「渡邊直二公安」.

**Measured, 2026-09-21:**

| | before | after |
| --- | ---: | ---: |
| speeches with no role | 848,000 (66%) | **190,510 (15%)** |
| distinct speakers | 14,085 | **12,099** |
| speeches given a role | — | **461,787** |
| speakers invented ending in an office | — | **0** |
| speech text changed | — | **none — byte-identical** |

The 15% that remain are three things and only the first is a defect: an office
this project has never seen stated separately (大分's
「石川商工労働観光部長事務取扱」), a title that is only an office with no name at
all (山口 prints many), and a title that is only a name (熊本's 「岩中伸司」,
where the source itself gives no office). `data/backup-pre-split/` holds the
corpora as they were.

## 5. Dates

**The listing's label wins, and the document's printed date is the check** —
which is the opposite of what this project concludes everywhere else. 徳島 is why:

```
徳島県告示第三百三号
令和八年六月徳島県議会定例会を次のとおり招集する。
  令和八年六月八日            <- the notice: the first date in the document
  一 期日 令和八年六月十五日   <- the sitting
```

The first date in the front matter is a week before the sitting. The schedule
label 「06月15日-01号」 is the vendor's own index of the sitting and agreed with the
printed 期日 on every tenant checked.

So a date is the 会議's year plus the label's month and day, with two guards:

* **A 会議 named in December can sit in January.** The year rolls rather than
  filing the sitting twelve months early.
* **A printed year can be impossible.** 熊本 names one 会議
  「平成５７年　６月　定例会」 — 平成 ended at 31 — and files it under 1982, which is
  昭和57年. Read literally that sitting lands in **2045**. The name is checked
  against its node: they disagree by a year legitimately and often, and by more
  than that only when the name is wrong.

`date disagreed` counts every case where the document's first date is not the
label's. **Read over the eleven finished tenants (2026-09-21), it says the
reversal was right.** 埼玉 has 190 of them in 1,598 documents, and every one is
the 招集告示 printed above the sitting — 165 at exactly seven days early, the
notice's usual week:

> 埼玉県議会令和８年２月定例会を２月１９日に招集する。　　令和８年２月１２日

Two of the 190 are not that, and both are worth knowing:

* **one document is misprinted.** 「昭和五十八年定例県議会を二月十六日招集する。
  昭和五十七年二月九日」 — the notice carries the wrong era year, 372 days out.
  The listing is right and nothing needs doing.
* **one label is wrong**, which is the counter-example to this whole section:
  the schedule reads 「10月03日-06号」 while the document reads
  「九月定例会第十九日（十月十三日）」. One in 1,598, against 190 the other way.
  The rule stands; the exception is recorded here rather than coded around.

`impossible years` behaved the same way: 熊本's seven are the seven sittings of
one mis-typed 会議 (`council_id=185`, 「平成５７年　６月　定例会」), all correctly
filed under 1982. Their `session` still reads 平成57年, because that is what the
site says and only the date was in question.

---

## 6. Cost

Per tenant: 1 (`councils/index`) + 1 per 会議 (`get_schedule_all`) + 1 per sitting
(`get_minute`).

* 14,910 会議 across the 17 tenants → **14,927 listing requests**
* sittings are not known until each 会議 is listed; 宮城's 定例会 carry ~6 and
  committees ~1, which puts the whole set near **33,000 documents**

**≈ 48,000 requests at 5 s ≈ 66 hours of wall clock.** All 17 tenants are one
host, so they must run **sequentially in one process** — the rate limiter is
per-process, and two `pt scrape` runs at once would halve the interval that the
decision above was made with.

Everything is cached, so a re-parse, an audit or a resumed run costs nothing.

---

## 7. After collecting, check these

The project's standing checks, plus the two this product adds:

1. `speakers unsplit`, per tenant, against the table in §4.
2. Distinct speakers sorted by length, and grepped for digits — the standing
   check for plausible garbage.
3. Speakers appearing both with and without an office suffix (the 愛媛 problem
   this scraper leaves open on five tenants).
4. `committee` values sorted by length, and the count of records with none — the
   静岡 check. Here the value comes from the listing, not a regex on the body, so
   a value beginning mid-sentence is impossible; an *empty* one is still worth
   counting.
5. `date disagreed` and `impossible years` from the run report.
6. The listing against the corpus, per sitting — `scripts/audit.py` works on
   this scraper as it stands, because a `MeetingRef` walk over a filled cache
   needs no requests. **All eleven finished tenants reconcile exactly**
   (2026-09-21): 16,636 sittings offered, 16,636 collected, 0 listed but not
   collected, on every one.

   The audit now sets `Settings.offline`, so a cache miss is an error rather
   than a request. That matters beyond tidiness: 滋賀 and 石川 may only be
   fetched on weekend evenings, and a check that quietly filled a gap in its own
   input would break that promise from the one script whose entire purpose is to
   read what we already have.
