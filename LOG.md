# Development log

Newest first. One entry per branch of work.

## 2026-08-28 — the 千葉 letter, rewritten for the person who opens it (`docs/chiba-plain-language`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Documentation only. The 千葉 draft was too technical, and the fix is not to trim it
but to split it.

**Who reads this.** 議会事務局 staff, not the person who maintains the server. The
old body led with `/voices/cgi/`, `/gikai/cgi/`, `/kaigiroku/cgi/` and the word
`Disallow`, and asked them to judge whether their own robots.txt was an oversight.
None of that is information they can act on — it is a request to make a decision in
a vocabulary that belongs to someone else, and it reads as pressure rather than as
courtesy.

**What changed.** The body now explains the situation in plain Japanese — websites
carry a robots.txt saying "please don't read this part automatically"; other
prefectures on the same product have their minutes inside that range; yours sits in
a slightly different place and so falls outside it; we cannot tell whether that is
deliberate. Every path name moved to a 【技術的な補足】 at the end, addressed to
whoever maintains the system, so the office can forward that section alone. The
substance is unchanged and nothing was softened away: the letter still discloses
that the setting currently permits access, and still says we will not collect if
that was not the intent.

**Also reordered.** The old letter opened with the robots question and asked for the
data second. That put the awkward part first and made the whole thing read as an
argument about configuration. The request comes first now; the question follows.

**One line of house style.** `inquiries/README.md` gains the rule, because 30 other
drafts share the old shape and will be sent by someone reading that index — 千葉 is
now the worked example, and the others are explicitly marked as not yet converted.

**Files**

`docs/inquiries/chiba.md`, `docs/inquiries/README.md`.

### 日本語

ドキュメントのみ。千葉の文面が専門的すぎるという指摘への対応。削るのではなく
**分ける**ことで解いた。

**誰が読むか。** 受け取るのは議会事務局の職員であって、サーバを管理している人とは
限らない。旧文は `/voices/cgi/`・`/gikai/cgi/`・`/kaigiroku/cgi/` と `Disallow` を
本文の前面に置き、「自分たちの robots.txt が記載漏れかどうか」を判断してくれと
求めていた。これは相手が動ける情報ではなく、**他人の語彙で決断を迫る形**であり、
礼儀というより圧力として読まれる。

**変えたこと。** 本文は平易な日本語で事情を述べるだけにした — ウェブサイトには
「ここは自動で読み取らないでほしい」と伝える robots.txt という設定があり、同じ
仕組みの他県では会議録がその範囲に入っているが、貴議会は設置場所がわずかに違う
ためその範囲に入っていない、意図的かどうかはこちらでは分からない、という説明。
パス名はすべて末尾の【技術的な補足】に移し、システム担当・事業者向けの宛書きを
付けた（事務局はその部分だけを転送すればよい）。**内容は薄めていない。** 現状の
設定では取得可能であると明かしている点も、意図と異なるなら取得しないと述べている
点もそのまま。

**順序も入れ替えた。** 旧文は robots の話から始まり、データのお願いが後だった。
気まずい話が先頭に来ることで、全体が「設定についての議論」に見えていた。いまは
お願いが先、確認が後。

**書き方を README に1行。** 他に30本の下書きが同じ旧い形のままで、送る人はあの索引
を見て送る。千葉を見本として示し、**他は未改訂であると明記した。**

**ファイル**

`docs/inquiries/chiba.md`, `docs/inquiries/README.md`.

## 2026-08-28 — the scope rewrite that PR #10 was holding up (`docs/scope-no-window`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Documentation only, and the debt named at the end of yesterday's entry: `CLAUDE.md`
and `docs/collection-targets.md` both still described the corpus in terms of a
research window, and both were left alone on `docs/local-politics-inquiry` because
PR #10 was editing them heavily and doing it there would have manufactured
conflicts. #10 landed; this is the follow-through.

**What was actually stale.** Not the facts — the framing. `collection-targets.md`
said "if the research window falls inside 2011–2019, most of this crawl is
redundant" and called **2020 onwards** the genuine gap. With the scope settled as
every period we can obtain, there is no window to fall inside anything, and
2011-04 .. 2019-03 is not a range to route around: it is a large piece of exactly
what we want, already assembled by someone else. The recommended order's item 1
still said "for the research window" as well.

**Two things the old text hid.** Rewriting it made both explicit:

- 和歌山 and 愛媛 each carry a deliberate hole at 2011-04 .. 2019-03. That is a
  consequence of the plan, not an oversight, and it stays open until the letter is
  answered — with 和歌山's 673 documents from 1989–2011 on the far side of one.
- Item 1 is not "ask about the window" any more. It is "send a drafted letter that
  has not been sent", with the addressee still 要確認.

**Dates corrected in passing.** `collection-targets.md` described the corpus as
"2011–2014 and 2015–2019" — the two published slices, but not the boundaries that
matter. It is 2011-04 .. 2019-03, fiscal years, as `CLAUDE.md` already said. Also
refreshed item 3, which still asked whether to run the 和歌山 archive crawl; it ran
yesterday (907 sittings, 46,839 speeches, 1989-02-27 .. 2025-12-19), and what
remains of that prefecture is the hole above plus the untouched 委員会会議録.

**`PT_CONTACT` is set, and it is not a repository change.** Recommended order item
6 is closed: a 京都大学 address, exported in the researcher's `~/.bashrc`, verified
through `Settings().user_agent`. `Settings.contact` reads the environment at import
and there is no `.env` support, so the export has to exist before `uv run` — worth
knowing before anyone wonders why a value in a file did nothing. **The address is
provisional (仮おき)**; the `.bashrc` line says so, because it is what site operators
see in the User-Agent and what every letter promises, and neither should go out on a
placeholder. The address itself is deliberately not written into any tracked file.

**One more copy of the same sentence.** `docs/prefecture-survey.md`'s step 4 said
"if either covers the research window, much of this crawl may be unnecessary" and
repeated the 2011–2014 / 2015–2019 slicing. Same fix. Three documents carried the
window premise; grep for it before assuming this branch caught them all.

**Files**

`CLAUDE.md`, `docs/collection-targets.md`, `docs/prefecture-survey.md`.

### 日本語

ドキュメントのみ。昨日のエントリ末尾で「#10 が入ったらやる」と明記した宿題そのもの。
`CLAUDE.md` と `docs/collection-targets.md` はどちらも研究対象期間（window）を前提に
書かれたままで、PR #10 が両方を大きく編集していたため、前ブランチでは競合を作らない
よう意図的に触らずに残していた。#10 がマージされたので、その履行。

**古びていたのは事実ではなく枠組み。** `collection-targets.md` は「対象期間が
2011–2019 に収まるならこの収集の大半は不要」と書き、**2020年以降**を真の空白と
呼んでいた。方針が「取得できる限りの全期間」で確定した以上、収まる先の窓は存在せず、
2011年4月〜2019年3月は避けて通る範囲ではない — **他人が既に整備し終えた、まさに
欲しいものの塊**である。推奨順序の第1項も「for the research window」のままだった。

**旧文が隠していたことが2つあり、書き直しで表に出た。**

- 和歌山と愛媛は、それぞれ 2011-04 .. 2019-03 に**意図的な穴**を抱えている。計画の
  帰結であって見落としではないが、照会の回答が出るまで開いたまま。和歌山の
  1989–2011 の673文書は、その穴の向こう側にある。
- 第1項はもう「窓について尋ねる」ではない。「**書き上がっているのに送っていない
  文面を送る**」であり、宛先は依然 要確認。

**ついでに日付を訂正。** `collection-targets.md` はコーパスを「2011–2014 と
2015–2019」と書いていた。公開単位としては正しいが、効いてくる境界ではない。
`CLAUDE.md` が既に書いていたとおり **2011年4月〜2019年3月の年度区切り**である。
第3項も更新した（「36年分を走らせるか決める」は昨日走った — 907会議・46,839発言・
1989-02-27 .. 2025-12-19。和歌山に残るのは上記の穴と、未着手の委員会会議録）。

**`PT_CONTACT` は設定済み。ただしリポジトリの変更ではない。** 推奨順序 第6項を消し
込み。京都大学のアドレスを `~/.bashrc` に `export` し、`Settings().user_agent` で
確認した。`Settings.contact` は import 時に環境変数を読み、`.env` の仕組みは無いので、
`uv run` の前に export されている必要がある（「ファイルに書いたのに効かない」で
悩む前に知っておくべき点）。**アドレスは仮おき**であり、`.bashrc` にもその旨を
コメントで残した — サイト運営者が User-Agent で目にし、各文面が約束するアドレスで
あって、仮の値のまま送り出してよいものではない。アドレス自体は追跡ファイルには
書いていない。

**同じ一文がもう1か所あった。** `docs/prefecture-survey.md` の第4項も
「対象期間を覆うなら、この収集の大半は不要かもしれない」と書き、2011–2014 /
2015–2019 の区切りを繰り返していた。同じ修正を適用。window の前提は3文書に
散っていたので、**取りこぼしがないかは grep で確かめること。**

**ファイル**

`CLAUDE.md`, `docs/collection-targets.md`, `docs/prefecture-survey.md`.

## 2026-08-27 — the letter that should have been written first (`docs/local-politics-inquiry`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Documentation only. One new file, `docs/inquiries/local-politics.md`, plus an index
entry. It has been listed as the next action in `JOURNAL.md` on two consecutive days
and in `collection-targets.md`'s recommended order as item 1, and it kept not
happening while three prefectures were collected around it.

**The scope question is now settled: everything obtainable, no window.**

That does not make the 地方議会会議録コーパス less relevant — it makes it more so.
The old framing was "if the research window falls inside 2011–2019, most of this
crawl is redundant". With no window, their 全47議会 / 2011-04 .. 2019-03 is not a
range to route around; it is a large piece of exactly what we want, already
assembled. What changes is only the reason for asking: not "do I need to crawl
this?" but "you already have this, may I have it rather than re-crawling 47
assemblies?"

**The cost of not asking is already on the books.** 和歌山 and 愛媛 were both scoped
to leave 2011-04 .. 2019-03 empty, on the assumption that it would come from this
project. Until this letter is answered, those two holes stay open by design — and
和歌山's 673 documents from 1989–2011 sit on the far side of one of them.

**Three things the letter asks that the records did not anticipate**

1. **Whether collection continues past 2019-04.** If it does, it may overlap what
   we are crawling right now. Nothing in our notes could establish this; only they
   can. This is the question most likely to change what we do next.
2. **Whether speaker and role are separated.** 愛媛 forced us to give up on that
   split — the marker 「○（三宅浩正議長）」 runs name and office together with no
   delimiter, and the corpus contains
   「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長」, so no lexical rule
   survives. We kept the whole string as `speaker` and left `role` empty. If they
   have solved it, their design is worth knowing.
3. **What we can offer back.** 和歌山 1989-02 .. 2011-02 (673 documents) predates
   their range. Asking a research project for 80 GB while offering nothing is a
   poor way to open, and this is a genuine contribution rather than a courtesy.

**Addressee is unverified**, in keeping with the house rule for these drafts. The
site is <http://local-politics.jp/>; the contact window has not been checked and is
marked 要確認.

**One stale claim fixed in passing.** `inquiries/README.md` still said 和歌山's
transcripts might be PDF and the format needed checking before deciding. 907
documents later that is plainly false. Corrected — the same failure mode as the SSP
premise in `fix/ssp-verdict`: a record that was true when written, left standing
until it would have misled someone.

**Kept off this branch on purpose.** `CLAUDE.md` and `collection-targets.md` both
describe the corpus in terms of a research window and should be rewritten now that
there is none, but both are heavily edited in the open PR #10. Doing it here would
manufacture conflicts. It follows once #10 lands.

**Files**

`docs/inquiries/local-politics.md` (new), `docs/inquiries/README.md`.

### 日本語

ドキュメントのみ。新規1ファイル `docs/inquiries/local-politics.md` と索引への追加。
`JOURNAL.md` で2日連続、`collection-targets.md` の推奨順序でも第1項として挙げ続けて
いながら、その周りで3県を収集する間ずっと着手されずに残っていたもの。

**対象期間が確定した — 取得できる限りの全期間、窓は設けない。**

これは当該コーパスの重要度を下げるのではなく、**上げる**。旧来の書き方は
「対象期間が2011–2019に収まるなら、この収集の大半は不要」だった。窓がない以上、
先方の 全47議会・2011年4月〜2019年3月 は「避けて通る範囲」ではなく、
**まさに欲しいものが既に整備されている塊**である。変わるのは尋ねる理由だけで、
「クロールする必要があるか」ではなく「既にお持ちなので、47議会を取り直す前に
分けていただけないか」になる。

**尋ねなかった代償は既に帳簿に載っている。** 和歌山も愛媛も、この期間が先方から
来る前提で 2011-04 .. 2019-03 を空けて収集した。回答が来るまで、その穴は設計上
開いたままである。しかも和歌山の 1989–2011 の673件は、その穴の向こう側にある。

**記録が想定していなかった質問を3つ入れた**

1. **2019年4月以降も継続しているか。** 継続していれば、いま収集している範囲まで
   重なりうる。当方の記録では判定不能で、先方にしか分からない。**次の行動を最も
   変えうる質問。**
2. **話者と役職が分離されているか。** 愛媛でこの分離を断念した。標識
   「○（三宅浩正議長）」は氏名と役職が区切りなしで連結され、コーパスには
   「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長」まである。
   語彙的な規則では解けないので、全文字列を `speaker` に入れ `role` は空にした。
   先方が解いているなら、その設計は知る価値がある。
3. **こちらから差し出せるもの。** 和歌山 1989-02 .. 2011-02（673件）は先方の
   収録範囲より古い。80GB を求めながら何も出さないのは筋が悪く、しかもこれは
   儀礼ではなく実際に寄与しうるものである。

**宛先は未検証。** この種の下書きの慣行どおり。サイトは <http://local-politics.jp/>
で、問い合わせ窓口は未確認・要確認と明記した。

**ついでに古い記述を1件訂正。** `inquiries/README.md` に和歌山は「本文が HTML か
PDF か未確認」と残っていた。907件収集した後では明らかに誤り。`fix/ssp-verdict` の
SSP の前提とまったく同じ失敗の型 — **書いた時点では真で、放置され、いずれ誰かを
誤らせる直前まで残っていた記述**である。

**意図的にこのブランチから外したもの。** `CLAUDE.md` と `collection-targets.md` は
どちらもコーパスを「研究対象期間」を軸に説明しており、窓がなくなった以上は書き
直すべきだが、両方とも PR #10 で大きく編集中である。ここで触ると衝突を作るだけ
なので、#10 がマージされてからにする。

## 2026-08-27 — SSP is blocked, and the earlier verdict was wrong (`fix/ssp-verdict`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Documentation only. No code, no collection. One fact arrived and reversed a verdict
this project had carried for two days.

**What was found**

The researcher opened `/tenant/js/release/config.js` in a browser — robots.txt binds
the crawler, and a person loading a page is not the crawler. It declares:

```js
dnp.config.SERVER = { API_ROOT: "/dnp/search/", PROTOCOL: "http://" }
```

There is no host constant, so the base is `https://ssp.kaigiroku.net/dnp/search/`.

`/dnp/search/` is **not** under `/tenant/`. The host's robots.txt — re-fetched and
byte-identical to what was recorded on 2026-08-26 — is `Disallow: /` with a single
`Allow: /tenant/`, so nothing reaches the API path. Checked with
`urllib.robotparser`, the same parser `PoliteClient` uses: every `/dnp/search/*`
path returns DENY. It is DENY under longest-match too, so the conclusion does not
depend on which reading you take.

**So the pages are crawlable and the data is not.** SSP moves out of Tier 2 and in
with the 24 blocked assemblies. The 18 prefectures do not need a scraper; they need
a letter. What changes in the letters is their purpose — from "how do I fetch this"
to "may I, or will you supply it".

**Why the error happened, and what it generalises to**

The old verdict — "permitted by robots, blocked only by architecture" — was not
careless. robots.txt *was* read, on the first day, and it *does* allow `/tenant/`.
The mistake was concluding from it before knowing which URL carried the data. On a
server-rendered site those are the same URL; on a client-side app they need not be,
and here they were not.

**A robots.txt verdict is not final until the URL that actually carries the data is
known.** That belongs alongside the other entries in "Things that will bite again",
and it is now there.

**A second finding, unrelated to SSP**

`urllib.robotparser` returns the first rule matching in file order rather than the
longest match, so `Disallow: /` above `Allow: /tenant/` denies `/tenant/` as well.
RFC 9309 and Google resolve the other way. `PoliteClient` would therefore refuse the
whole of `ssp.kaigiroku.net`, including pages its operator plainly meant to open.
Moot for SSP — the API is denied either way — but it will matter on the next site
that writes a broad `Disallow` above a narrow `Allow`. Recorded, not fixed; fixing
it is a change to crawl behaviour and wants its own branch and its own decision.

**Two smaller corrections**

The vendor is **NTT Advanced Technology Co., Ltd.**, from the copyright header. The
note that the page carried "a DNP logo" was a misreading: the product is **Discuss
Net Premium**, its JavaScript namespace is `dnp.*`, and that is what DNP stands for
here — not 大日本印刷. The contradiction between the two records was never a
contradiction.

`docs/prefecture-survey.md` claimed no disallowed URL had ever been fetched, naming
`config.js` specifically. That sentence, and the same claim inside
`ssp-vendor.md`'s letter body, were true when written and are not now. Both are
corrected rather than left standing — the letters would otherwise say something
false to their recipients. The crawler's own rule is unchanged.

**Ordering: 大阪 first**

Of the 18, only 大阪 names a destination on its own page ("転用…については大阪府議会
事務局までお問い合わせください"). The vendor's department is still unknown, so 大阪 is
both the shortest route to that and an inquiry that has to happen anyway, since its
reuse condition survives any answer about robots. One letter returns both.

**Also noted**

`PT_CONTACT` is still `research-crawler@example.invalid`, while every letter promises
a real contact address in the User-Agent. Set it before sending anything.

**Files**

`CLAUDE.md`, `docs/prefecture-survey.md`, `docs/collection-targets.md`,
`docs/inquiries/README.md`, `docs/inquiries/ssp-vendor.md`,
`docs/inquiries/ssp-assembly.md`, `.gitignore` (the fetched vendor script is not
ours to redistribute).

### 日本語

ドキュメントのみ。コードの変更も収集も行っていない。事実が1つ判明し、2日間持って
いた判定がひっくり返った。

**分かったこと**

`/tenant/js/release/config.js` をブラウザで開いた。robots.txt が拘束するのは
クローラであり、人がページを開く行為はそれに当たらない。中身は

```js
dnp.config.SERVER = { API_ROOT: "/dnp/search/", PROTOCOL: "http://" }
```

ホスト定数はないので、実体は `https://ssp.kaigiroku.net/dnp/search/`。

`/dnp/search/` は `/tenant/` の**外**。robots.txt を取り直したところ 8/26 の記録と
バイト単位で同一で、`Disallow: /` に対する `Allow:` は `/tenant/` の1本だけ。
`PoliteClient` が使うのと同じ `urllib.robotparser` で判定させると、
`/dnp/search/*` はすべて DENY。最長一致で読んでも DENY なので、解釈に依存しない。

**画面は取得できるが、データは取得できない。** SSP は Tier 2 から外れ、取得禁止の
24議会と同じ扱いになる。18県に必要なのはスクレイパではなく手紙で、手紙の性格が
「やり方を教えてほしい」から「許可またはデータ提供の依頼」に変わる。

**なぜ間違えたか**

旧判定「robots は許可、構造だけが壁」は、手を抜いた結果ではない。robots.txt は
初日に読んでいるし、`/tenant/` が Allow なのも事実である。誤りは、**データを運ぶ
URL を知らないうちに結論を出したこと**にある。サーバ側描画のサイトでは両者は同じ
URL だが、クライアント側描画のアプリでは別でありうる。ここでは別だった。

**robots.txt の判定は、実際にデータを運ぶ URL が分かるまで暫定である。**
「Things that will bite again」に追加した。

**SSP とは無関係な発見**

`urllib.robotparser` は最長一致ではなく**ファイル順で最初に一致した規則**を返す。
そのため `Disallow: /` が `Allow: /tenant/` より上にあると `/tenant/` も拒否される。
RFC 9309 や Google は逆に解釈する。つまり `PoliteClient` は `ssp.kaigiroku.net` を
丸ごと拒否し、運営者が明らかに開放している画面まで取りに行かない。SSP では
どのみち DENY なので実害はないが、**広い `Disallow` の下に狭い `Allow` を書く次の
サイトで効いてくる。** 記録のみ、修正はしていない。クロール挙動の変更なので、
別ブランチと別の判断が要る。

**小さな訂正2件**

事業者は `config.js` の著作権表示より **NTT アドバンステクノロジ株式会社**。
「ページ内に DNP のロゴ」という記述は読み違いで、製品名が **Discuss Net Premium**、
JavaScript の名前空間が `dnp.*`。ここでの DNP はそれであって大日本印刷ではない。
2つの記録の食い違いは、そもそも食い違いではなかった。

`docs/prefecture-survey.md` は「Disallow 配下の URL は一切取得していない」と
`config.js` を名指しで書いていた。`ssp-vendor.md` の本文にも同じ記述がある。
書いた時点では真だったが、いまは違う。**そのままにすると、相手に事実でないことを
書いて送ることになる**ので、両方直した。クローラ側の規則は変えていない。

**順序：大阪を先に**

18県のうち、自分のページに宛先を名指ししているのは大阪だけ（「転用…については
大阪府議会事務局までお問い合わせください」）。事業者の部署は依然不明なので、
それを尋ねる先としても大阪が最短で、しかも大阪の再利用条件は robots の可否とは
別に残るため照会は避けられない。1通で両方の答えが返る。

**あわせて記録**

`PT_CONTACT` が `research-crawler@example.invalid` のまま。手紙はどれも
「User-Agent に連絡先を明記する」と約束しているので、送る前に設定すること。

## 2026-08-27 — 愛媛, and the first scraper that is not selectors (`feat/ehime`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Third prefecture, and the first site that genuinely could not be expressed as a
config. Scoped, like 和歌山, to what the 地方議会会議録コーパス does not cover after
2019-03.

**Collected**

```
meetings : 201          speeches : 11,194
chars    : 6,123,840    range    : 2019-05-15 .. 2026-03-09
```

33 sessions, 266 speakers, 2019–2026 continuous. Nothing undated, no sitting
without speeches, no duplicate, no mojibake, nothing outside the range.

**Why a subclass, not a config**

`GenericScraper` follows links. This site has none to follow:

- The browse tree is `<A HREF="javascript:…" onClick="…treedepth.value='令和 7年'">`,
  so the target is in an attribute, and the label has to be percent-encoded in
  **cp932** — the page's own charset — before it can be sent back.
- A sitting is not at a URL. The page's own ダウンロード button posts a list of
  character offsets to `GetPerson.exe`, which returns the whole transcript as one
  plain-text response. Composing that is more than following a link.
- The transcript is not HTML, so there is no container to select.

`BaseScraper` gained one hook for the general case — `fetch_meeting`, "the page
`parse_meeting` will be given" — defaulting to today's single GET. That is the
whole extension: everything else (politeness, cache, cp932 decoding, resume, the
date filter) is unchanged.

It pays off twice. Listing now costs **nothing per document**, and because
`fileName=R070303A` carries the date, `--since/--until` prunes before either
request. This is the first site where a date filter actually saves work.

**Four faults, each silent, each found only by running it**

1. **Pydantic caps a URL at 2,083 characters.** The download URL for a 一般質問 day
   exceeds it, so it cannot be a record's identity — the crawl died at meeting 6.
   A ref now points at the speaker index (~100 characters). The forced redesign is
   better than what it replaced.
2. **A `years` list can name unreachable nodes.** Opening a *tab* reveals the years
   it groups; a year's sessions appear only when that year is opened. 令和 2年 and
   平成31年 are not tabs, so five of the eight years asked for were skipped
   **without a word**. The walk is two-phase now, and a year the tree lacks is
   reported instead of ignored.
3. **The charset is not detectable.** `GetPerson.exe` returns plain text with no
   meta tag and no `charset` header, so `sniff_encoding` has only
   charset-normalizer — which guessed **utf-8** for 5 of 63 sittings. The config
   states `encoding = "cp932"` rather than detecting it. Those five warned, because
   they parsed to zero speeches; a different document would have produced plausible
   garbage instead, exactly as 静岡 did.
4. **「令和元年」 is a year node and 元 is not a digit.** `dates.py` has handled that
   form since 静岡; the new `_YEAR_NODE` pattern used `\d{1,2}` and skipped the node
   entirely — walked, matched nothing, said nothing. Caught only because the
   collected range began at 2020 instead of 2019.

Four of today's mistakes are the same mistake: **assuming one form is every form.**
Bare member names, ○ versus 〇, 全文 versus 本文, and now 元年. The counter-measure
that keeps working is not care, it is arithmetic — count what a rule matches
against a sample, and check the *edges of the range* after every run.

**Speaker and office are deliberately not separated**

The marker is 「○（三宅浩正議長）」: name and office in one run, no delimiter. No
lexical rule splits them — 「三宅浩正議長」 breaks wrongly under both greedy and lazy
matching, and the corpus contains
「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長」. The whole string is kept
as `speaker` and `role` is left empty rather than guessing, which after a day spent
finding three separate sources of plausible nonsense seems the only defensible
choice. Doing it properly means reading each document's 出席理事者 roster, where
office and name *are* separated; that is noted in `docs/kensakusystem.md` as the
right approach and is deferred, not forgotten.

**Also**

- `pt scrape --start-url` now refuses non-selector sites with an explanation
  rather than an AttributeError.
- 8 offline tests for the new scraper; `ruff`, `mypy --strict`, `pytest` (72) clean.

**Not done**

平成3年–2011年 for 愛媛 (`years = []` walks it). 三重 and 兵庫 — same product, same
`cgi-bin3`, only `base_url` and `Code=` differ; 兵庫 reaches 昭和61年. 委員会会議録.

### 日本語

3県目。そして**設定では表現できなかった最初のサイト**。和歌山と同様、
地方議会会議録コーパスが 2019年3月で終わったあとの空白に絞って収集した。

**収集結果**

```
会議 : 201          発言 : 11,194
文字 : 6,123,840    期間 : 2019-05-15 .. 2026-03-09
```

33会期・発言者266名・2019〜2026が連続。日付なし・発言0件・重複・文字化け・範囲外
いずれもゼロ。

**なぜ設定ではなくサブクラスか**

`GenericScraper` はリンクを辿る。このサイトには辿るリンクがない。

- ツリーは `onClick` の中に遷移先があり、しかもラベルを**cp932**で
  パーセントエンコードして送り返す必要がある。
- 会議録はURLに存在しない。ページ自身のダウンロードボタンが文字オフセットの一覧を
  `GetPerson.exe` に送り、全文が1回のプレーンテキスト応答で返る。
- 本文はHTMLではないので、選択すべき容器がない。

`BaseScraper` に汎用の拡張点を1つだけ追加した — `fetch_meeting`（既定は従来どおり
`ref.url` を1回GET）。これで**一覧は文書ごとに1リクエストも使わなく**なり、
`fileName=R070303A` に日付が入っているため **`--since/--until` が両方のフェッチより
前に効く**。日付フィルタが実際に仕事を減らす最初のサイトになった。

**4つの欠陥。いずれも沈黙し、いずれも動かして初めて出た**

1. **Pydantic のURL上限2083字。** 一般質問日のダウンロードURLが超過し、6件目で
   クロールが停止した。参照を発言索引URL（約100字）に変更。強制された再設計の方が
   元の設計より良かった。
2. **`years` に到達不能なノードを書ける。** タブを開くとその年群が現れ、会期は
   その年を開いて初めて現れる。令和2年・平成31年はタブではないので、指定した8年の
   うち5年が**一言もなく**飛ばされていた。2段階に変更し、存在しない年は警告する。
3. **文字コードが判定不能。** `GetPerson.exe` はプレーンテキストで meta も
   charset ヘッダもなく、63件中5件が **utf-8 と誤判定**された。設定で
   `encoding = "cp932"` を明示。今回は発言0件で警告が出たが、別の文書なら
   静岡と同じ「もっともらしいゴミ」になっていた。
4. **「令和元年」は年ノードで、元は数字ではない。** `dates.py` は静岡以来この形を
   扱っているのに、新しい `_YEAR_NODE` は `\d{1,2}` で書いてノードごと飛ばしていた。
   歩いて、何も一致せず、何も言わない。収集範囲が2019年でなく2020年始まりだったので
   気づけた。

今日の失敗のうち4つは**同じ失敗**である — 「一つの形で足りる」と思い込むこと。
括弧なしの議員名、○と〇、全文と本文、そして元年。効き続けている対策は注意深さでは
なく**算術**だ。規則が何件一致するかをサンプルで数え、収集後に**範囲の端**を確認する。

**氏名と役職は意図的に分けていない**

標識は「○（三宅浩正議長）」で、氏名と役職が区切りなく連結している。語彙的に分ける
規則は存在しない（「三宅浩正議長」は貪欲でも最短でも誤る）。実際
「毛利修三愛媛県の未来を創る農業・農村振興条例審査特別委員長」も含まれる。推測して
もっともらしいゴミを作るより、全体を `speaker` に入れ `role` を空にした。
正しくやるには各文書の出席理事者名簿（役職と氏名が空白で分かれている）を読む必要が
あり、`docs/kensakusystem.md` に**正しい方法として**記載したうえで先送りしている。

**未実施**

愛媛の平成3年〜2011年（`years = []` で歩ける）。三重・兵庫（同一製品・同一 `cgi-bin3`、
`base_url` と `Code=` が違うだけ。兵庫は昭和61年まで）。委員会会議録。

## 2026-08-27 — 和歌山: everything the 地方議会会議録コーパス does not cover (`feat/wakayama-archive`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Asked to collect the rest of 和歌山, at least the part not already in the
地方議会会議録コーパス. Verified that corpus's range first, collected the two gaps
either side of it, then fixed the split rule with what 907 documents revealed.

**What that corpus covers, and what it leaves**

都道府県議会 runs **2011-04 to 2019-03** — fiscal years. So two gaps:

- 1989 .. 2011-03 (the archive's whole first two decades)
- **2019-04 .. 2019-12** — easy to miss, and it falls between that corpus and any
  collection starting at 2020. Four sessions.

2011-04 .. 2019-03 was deliberately **not** collected. 102 of the index's 167
sessions were in scope.

**Collected**

```
meetings : 907          speeches : 46,839
chars    : 27,358,983   range    : 1989-02-27 .. 2025-12-19
```

708 new sittings on top of the 199 from the earlier run. Every record titled and
attributed to a session, one undated (below); 410 speakers, no speech without a
speaker, no zero-speech sitting, no duplicate URL. Year coverage is continuous
1989–2011 and 2019–2025, with 2012–2018 absent by design.

**Checked before running, because the journal said to**

The `◎` rule and the 漢数字 dates had been decided without opening a single
1990s document. Surveying all 102 session pages first found **a third label form,
「◎会議録全文」** (7 of 708) — sittings of 臨時会 that carry no 号 number. `^◎` covers
it, and no session page yielded zero links. Spot-checking 平成元年, 平成6年 and
平成15年 documents confirmed the container, the dates (「平成元年二月二十七日」 →
1989-02-27) and the markers all parse.

That survey cost 102 requests that the crawl needed anyway. Had it been skipped and
the 全文-only filter still been in place, three sessions would have vanished in
silence — exactly the failure this project already made once.

**Two split-rule faults, visible only at 907 documents**

Both produced *nonsense speakers*, not missing text, so nothing warned.

- **Greedy matching.** `{1,24}` ran past the real name to a later 「君」 in the
  speech: 「○林　隆一君　知事、大変失礼いたしました。林君」 became one 21-character
  speaker. Lazy matching fixed 3 records and changed the speech count by **zero**.
- **〇 is a numeral, 「君」 is an ordinary word.** The 「君」 suffix rejects
  「二〇〇三年度」 but not 「例えば二〇年後、三〇年後、君が四〇歳を過ぎ」 or
  「子供一一〇番の家であるきしゅう君の家」 — 4 false speakers. A real marker never
  follows a digit, so a negative lookbehind settles it.

Two other candidates were measured over the whole corpus and **rejected**, which is
the part worth keeping:

| Rule | False positives killed | Real speeches lost |
| --- | ---: | ---: |
| Anchor marker to line start | 4 | **7** — speeches do begin mid-line, after 「〔「異議なし」と呼ぶ者あり〕」 |
| Require whitespace after marker | 4 | **15** — 「○浜本　収君（続）」, and older sittings with no space at all |
| **Lookbehind on numerals** | **4** | **0** |

All three looked reasonable in the abstract. Only counting what each caught *and
what it lost*, across all 907 documents, separated them. Re-parsing to compare cost
**zero requests** — every page was already cached, which is the whole point of
caching every response.

**One record left undated, deliberately**

平成8年6月第6号 (`p042602`) prints 「平成八年**七年**十日（水曜日）」 — a typo for
七**月** in the source. The date pattern is anchored on 「（…曜日）」 so it cannot pick
up a date mentioned in passing; loosening it to rescue one record would risk
mis-dating others. True date **1996-07-10**, given correctly elsewhere on the same
page. Recorded in `docs/wakayama.md` rather than papered over.

**Also**

- 4 regression tests carrying the rejected alternatives, so the reasoning is not
  lost the next time the rule looks over-complicated.
- `ruff`, `mypy --strict`, `pytest` (63) clean.

**Not done**

2011-04 .. 2019-03 (available from the 地方議会会議録コーパス — worth confirming what
they can actually share before deciding to crawl it). 委員会会議録 (`/gijiroku2/`).

### 日本語

「地方議会会議録コーパスにない分」を収集するよう指示。まず当該コーパスの収録範囲を
確定し、その前後2区間を取得したうえで、907文書が明らかにした問題で分割規則を直した。

**当該コーパスの範囲と、残る空白**

都道府県議会は **2011年4月〜2019年3月**（年度区切り）。したがって空白は2つ:

- 1989年〜2011年3月
- **2019年4月〜12月** — 見落としやすい。当該コーパスの終わりと、2020年開始の収集の
  あいだに落ちる4会期。

2011年4月〜2019年3月は**意図的に取得していない**。索引167会期のうち102会期が対象。

**収集結果**

```
会議 : 907          発言 : 46,839
文字 : 27,358,983   期間 : 1989-02-27 .. 2025-12-19
```

既存199件に708件を追加。全件に表題と会期あり（日付なし1件は後述）。発言者410名、
発言者が空の発言なし、発言0件の会議なし、重複URLなし。年別の欠落は2012〜2018のみで
これは設計どおり。

**走らせる前に確認したこと（日誌に自分で書いた警告に従って）**

`◎` 判定も漢数字日付も、1990年代の文書を1件も開かずに決めていた。先に102会期の
一覧ページを調べたところ、**第3のラベル「◎会議録全文」**（708件中7件）が見つかった。
号番号を持たない臨時会である。`^◎` なら拾え、ゼロ件の会期もなかった。平成元年・
平成6年・平成15年の文書で容器・日付（「平成元年二月二十七日」→1989-02-27）・標識も確認。

この調査の102リクエストは、どのみちクロールで必要なもの。**省略していて、かつ
「全文」限定のままだったら、3会期が無警告で消えていた** — 本プロジェクトが既に一度
やった失敗そのもの。

**907文書規模で初めて見えた分割規則の欠陥2つ**

どちらも**でたらめな発言者名**を作るだけで、本文が欠けるわけではないので何も警告しない。

- **貪欲マッチ。** `{1,24}` が本来の氏名を越えて発言本文中の「君」まで走る。
  「○林　隆一君　知事、大変失礼いたしました。林君」が21字の発言者1名になっていた。
  最短一致で3件修正、発言数の変化は**ゼロ**。
- **〇 は数字、「君」は普通名詞。** 末尾「君」は「二〇〇三年度」を弾くが、
  「例えば二〇年後、三〇年後、君が四〇歳を過ぎ」や「子供一一〇番の家であるきしゅう君の家」
  は弾けない（4件）。本物の標識が数字に続くことはないので、否定後読みで解決。

**却下した2案**も全コーパスで計測した。残す価値があるのはこちら:

| 案 | 消える偽陽性 | 失う本物の発言 |
| --- | ---: | ---: |
| 標識を行頭に限定 | 4 | **7** — 「〔「異議なし」と呼ぶ者あり〕 ○議長（…）」等、行の途中から始まる発言は実在する |
| 標識の直後に空白を要求 | 4 | **15** — 「○浜本　収君（続）」、および空白なしの古い会議録 |
| **数字の否定後読み** | **4** | **0** |

3案とも机上ではもっともらしい。**「何を捕まえるか」と「何を失うか」の両方を全907件で
数えて初めて**差がついた。比較のための再解析は**リクエスト0件** — 全ページが
キャッシュ済みで、全応答をキャッシュする方針の意義がここに出た。

**1件、意図的に日付なしのまま残した**

平成8年6月第6号（`p042602`）は「平成八年**七年**十日（水曜日）」と印刷されている。
原本の誤植（七**月**）。日付パターンは「（…曜日）」に固定して本文中の日付を拾わない
ようにしてあり、1件のために緩めれば他を誤る危険がある。正しくは **1996-07-10**で、
同じページの別箇所には正しく「平成８年７月10日」とある。糊塗せず `docs/wakayama.md`
に記録した。

**その他**

- 却下した案を含む回帰テスト4件。次に規則が「複雑すぎる」に見えたとき、理由が
  失われないように。
- `ruff` / `mypy --strict` / `pytest`（63件）通過。

**未実施**

2011年4月〜2019年3月（地方議会会議録コーパスにある。クロールを決める前に、
先方が実際に何を共有できるか確認する価値がある）。委員会会議録（`/gijiroku2/`）。

## 2026-08-27 — 和歌山 2020–2025, and a second listing level (`feat/wakayama`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Second config in the project, the first general listing feature, and 2020–2025
collected.

**Collected: 2020–2025**

30 sessions, 199 sittings, `data/和歌山県.jsonl` + `.csv`:

```
meetings : 199          speeches : 14,366
chars    : 5,680,229    range    : 2020-02-20 .. 2025-12-19
```

Every record dated, titled and attributed to a session; 124 distinct speakers; no
speech without a speaker; no sitting-number gap in any of the 30 sessions; no
duplicate URL; nothing outside the requested range. 154 requests this run at 2s
apart (the rest served from cache), two transient DNS failures both recovered by
the existing retry.

Scoped with `--start-url` per session, not with `--since/--until`: this index
carries no dates, so a date filter cannot save a request here — the same lesson
静岡 taught. The date range was passed as well, purely as a backstop, and caught
nothing.

**Added**

- `list.index_link` / `index_include` / `index_exclude` / `max_depth` — an
  intermediate listing level, for sites shaped index → session → sitting. Both
  和歌山 and 愛媛 are this shape, so it is the domain's shape rather than a
  per-site hack. `meeting_link` and `index_link` are applied at every level and
  usually separate themselves; `max_depth` bounds the walk regardless.
- `list.include` — the symmetric counterpart to `exclude`.
- `list.extra_meeting_urls` — transcript pages the site's own index fails to
  reach. Keeps the corpus complete *and* reproducible from the config, which
  appending a record by hand would not be.
- Fragment-stripping on link resolution, plus the fix below.
- `dates.py`: 漢数字 和暦 (`kanji_to_int`), for 「平成十二年十二月八日（金曜日）」.
  Tried after the ordinary 和暦 pattern so it cannot steal a match. Also reads
  「昭和六十一年」, which 兵庫 will need.
- `sites/wakayama.toml`, `docs/wakayama.md`; new options in `_example.toml`.

`ruff`, `mypy --strict`, `pytest` (59) clean.

**Five traps, all silent, all the same kind: one form is not all forms**

The first three were found before collecting, the last two only by collecting.

1. **Bare member names.** Office-holders are 「○知事（岸本周平君）」 but members are
   「○濱口太史君」 with no parentheses. 静岡's rule scores 72 of 98 markers on
   令和6年6月第3号 and drops *every member speech*. Caught by counting what the
   rule matched against a sample.

2. **The circle is two characters.** 令和6年6月第1号 marks all 21 of its speeches
   with 〇 (U+3007), not ○ (U+25CB). Not caught by reading — the first live run
   parsed that sitting to zero speeches and warned. Same signature as the 静岡
   encoding bug.

3. **〇 is also a numeral.** 平成12年12月第2号 has 53 inside body text
   (「二〇〇三年度」). The 「君」 requirement rejects all of them, and the roster too.

4. **The whole-sitting link has two labels.** Most sessions say 「◎第３号全文」;
   令和2年2月, 令和2年4月 and 令和2年5月 say 「◎第１号本文」. `include = '全文'`
   dropped **12 of 199 sittings — three whole sessions — with no warning at all**,
   because a session page that yields no links looks exactly like a session that
   was never asked for. There is no "zero speeches" smoke test at the *listing*
   level, which is what makes this class worse than 2 and 3. Now matched on the
   leading 「◎」: 199 of 199 whole-sitting links carry it, no member slice does.

5. **One index link is simply broken.** 令和7年6月's page links its 第6号 as a
   truncated 「◎第」 pointing at `d00217979`, a 令和6年 document, leaving
   令和7年6月第6号 unreachable from the site's own index. It exists — `d00220760`
   returns 「令和7年6月…第6号（全文）」, verified — and is now in
   `extra_meeting_urls`; the collected sitting has 84 speeches. Worth raising
   with 議事課.

**One latent bug, found while fixing 4**

`seen` was populated before the include/exclude check. Several links resolve to
one URL once the fragment is dropped — 和歌山 anchors each member's question into
the whole-sitting page — so whichever came first in the document decided for the
rest, and a rejected member anchor could suppress the sitting itself. A link is
now marked seen only once it passes the filter.

**Checked at scale, and not a problem — but do not assume it elsewhere**

和歌山's 議長 addresses women as さん aloud (「６番森礼子さん」), which a 「君」-only
rule would break. The *markers* use 君 regardless of gender: 森　礼子 is the fourth
most frequent speaker in this corpus with 1,319 speeches. On a site that marks
women さん, a 「君」-only rule would drop their speeches wholesale — a corpus-bias
problem, not a parsing detail. Noted in CLAUDE.md.

**Not done**

平成2年–令和元年 (1990–2019) — the config reaches it and 平成12年12月 was verified
end to end, but the oldest generation (平成2–10年) has not been opened. 委員会会議録
(`/gijiroku2/`) untouched.

### 日本語

本プロジェクト2つ目の設定、最初の汎用一覧機能、そして2020–2025の収集。

**収集結果: 2020–2025**

30会期・199会議。`data/和歌山県.jsonl` ＋ `.csv`:

```
会議 : 199          発言 : 14,366
文字 : 5,680,229    期間 : 2020-02-20 .. 2025-12-19
```

全件に日付・表題・会期あり。発言者124名、発言者が空の発言ゼロ、30会期すべてで
号数の欠番なし、重複URLなし、範囲外なし。今回のリクエストは154件（残りはキャッシュ）、
2秒間隔。DNS一時失敗2件はいずれもリトライで復旧。

絞り込みは `--since/--until` ではなく会期ごとの `--start-url`。この索引は日付を
持たないので日付フィルタではリクエストを節約できない — 静岡と同じ教訓。日付範囲は
保険として併用したが、何も捕まえなかった。

**追加**

- `list.index_link` ほか — 「索引 → 会期 → 会議」型のための中間一覧階層。和歌山も
  愛媛も同じ形なので、場当たりではなくこの領域の形。
- `list.include` — `exclude` の対。
- `list.extra_meeting_urls` — サイト側の索引が到達できない会議録ページ。手作業で
  レコードを足すのと違い、**設定から再現できる**形でコーパスを完全に保てる。
- リンク解決時のフラグメント除去と、下記のバグ修正。
- `dates.py` に漢数字和暦（`kanji_to_int`）。「昭和六十一年」も読めるので兵庫でも要る。
- `sites/wakayama.toml`、`docs/wakayama.md`、`_example.toml`。

`ruff` / `mypy --strict` / `pytest`（59件）通過。

**5つの罠 — すべて黙って失敗する同種のもの**

1〜3は収集前に、4と5は**収集して初めて**判明した。

1. **括弧なしの議員名。** 静岡の規則では98件中72件で、議員発言を全部落とす。
2. **丸が2種類。** 令和6年6月第1号は21発言すべてが 〇(U+3007)。実収集の
   「発言0件」警告で判明。静岡の文字コードバグと同じ兆候。
3. **〇 は数字でもある。** 「二〇〇三年度」等53件。末尾「君」の要求が全部弾く。
4. **全文リンクのラベルが2種類。** 多くは「◎第３号全文」だが、令和2年の2月・4月・
   5月は「◎第１号**本文**」。`include = '全文'` は**199件中12件（3会期まるごと）を
   完全に無警告で取りこぼす**。会議0件の会期ページは「指定されなかった会期」と
   区別がつかず、**一覧段階には「発言0件」に相当する検出手段がない**。ここが2・3より
   質が悪い。先頭の「◎」で判定に変更（199件すべてに付き、議員別リンクには付かない）。
5. **索引のリンクが1本壊れている。** 令和7年6月の第6号が「◎第」という切れたラベルで
   令和6年の文書に向いており、実体（`d00220760`・84発言）に索引から到達できない。
   `extra_meeting_urls` で補った。議事課への確認事項。

**4の修正中に見つかった潜在バグ**

`seen` への登録が include/exclude 判定より前だった。フラグメント除去後に同一URLへ
解決されるリンクが複数ある（議員別アンカーが全文ページ内を指す）ため、**文書中で
先に現れたリンクが後続の判定を奪い**、除外された議員別リンクが会議本体を握り潰し得た。
フィルタ通過後にのみ `seen` に入れるよう修正。

**実データで確認済み・ただし他県で前提にしないこと**

和歌山の議長は発言中で女性を「さん」と呼ぶが、**標識**は性別によらず「君」。
森　礼子議員は本コーパスで発言数4位（1,319件）。標識に「さん」を使うサイトでは
「君」限定の規則は女性議員の発言を丸ごと落とす。解析の細部ではなくコーパスの
偏りの問題。CLAUDE.md に記載。

**未実施**

平成2年〜令和元年（1990–2019）。設定は到達できるし平成12年12月は端から端まで
検証済みだが、最古の世代（平成2〜10年）は未開封。委員会会議録（`/gijiroku2/`）は未着手。

## 2026-08-27 — Re-opening the leads: four prefectures are collectable (`survey/collectable-targets`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Docs only; no code and no corpus collected. Asked to read yesterday's log and work
out where minutes can actually be collected. Two of the four leads turned out
better than the survey recorded, and they are blocked by the same missing feature.

**Added**

- `docs/collection-targets.md` — the ranked answer, with cost per target.
- `docs/wakayama.md`, `docs/kensakusystem.md` — verified site notes.
- A supersession banner on `docs/prefecture-survey.md`; two of its verdicts are now
  wrong in our favour and it should not be read alone.

**和歌山 — the best target in the survey, and it was written off**

The survey guessed PDF "on the evidence of 北海道". It is plain UTF-8 HTML: one
index page listing ~150 sessions from 平成2年 to 令和8年, each session page listing
its sittings, each sitting one page carrying the full text (~186 KB, ~60k chars,
98 speech markers in the sample). robots.txt is 404 and the pages carry
`index, follow`, so none of 静岡's `meta robots` question applies.

The survey's entry point was also wrong: `/gijiroku/` returns 403, which is the
directory index being off, not a block — documents under it are 200. Correct entry
is `/gijiroku/d00203238.html`.

The trap here is the mirror image of 静岡's. Office-holders are `○知事（岸本周平君）`
but members are bare `○濱口太史君`, with no parentheses. 静岡's split rule would have
silently dropped most of the corpus — the same failure mode as the 質問日/発言日 label
(one form is not all forms), caught this time by reading a sample first.

**愛媛・三重・兵庫 — both open questions resolved in our favour**

The survey left "the tree navigates by POST" and "the result-list parameters were
not pinned down". Both are answered:

- `See.exe` takes as a GET query string what the page submits as a POST.
  `See.exe?Code=<code>&treedepth=<label>`, the label percent-encoded **in cp932**
  and carrying a significant trailing space at session level. No POST support
  needed anywhere.
- The page's own ダウンロード button posts to `GetPerson.exe` — and it accepts GET
  with a repeated `downloadPos`, returning the whole sitting as **plain text**. So
  a sitting costs two requests (speaker index + download) rather than one per
  speech. `GetText3.exe` returns one speech, `GetPage.exe` one printed page; both
  are strictly worse.

`fileName=R080225A` encodes the date, so `--since/--until` actually saves requests
here — the opposite of 静岡, where the index carries no dates.

兵庫 reaches back to **昭和61年 (1986)**, the deepest archive found. All three carry
`<meta name="robots" CONTENT="follow,index">`.

**The one change that unlocks all four**

`GenericScraper` models a listing as one level plus pagination. Both targets are
year/index → session → sitting. An intermediate listing level is a real shape in
this domain rather than a per-site hack, and it is the highest-value code change
open. 愛媛 needs two smaller things after that: `speech_split` against a body that
is not HTML, and a listing step that gathers `downloadPos` values into the next URL
— the second may be cheaper as a small `BaseScraper` subclass than as config.

**SSP — no breakthrough, but the ground is prepared**

Collected all 18 numeric tenant ids (大阪 315, 沖縄 632, …) from
`/tenant/<tenant>/js/*.js`, which is **not** disallowed: `Disallow: /tenant/js/`
matches the shared directory only, not `/tenant/prefosaka/js/`. Confirmed the
permalink form `MinuteView.html?council_id=&schedule_id=` and confirmed those pages
are a pure client-side shell, so no server-rendered route exists and the API really
is required. The endpoint stays in `/tenant/js/release/config.js`, which is under
`Disallow` and was not fetched.

Also found a second condition that robots.txt says nothing about: 大阪's own page
states the data rights belong to the assembly and that reuse for other purposes
should be cleared with 議会事務局. That applies even once the API is known, and it
belongs in the letters for these 18.

**Check before crawling**

The 地方議会会議録コーパスプロジェクト already covers all 47 assemblies for 2011–2014
and 2015–2019 (~134M sentences, ~80 GB). If the research window sits inside that,
most of this crawl is redundant. The genuine gap is 2020 onwards — which is also
where the Tier-1 targets are cheapest. Settle this before any large run.

**Method**

Roughly 40 requests total, all through `PoliteClient` or `curl` at 2s spacing,
serialised per host, everything cached. No URL under any `Disallow` was fetched.

### 日本語

ドキュメントのみ。コードの変更と収集は行っていない。昨日のログを読んだうえで、
実際にどこが収集可能かを詰めた。4つの懸案のうち2つが、記録より良い結果だった。
しかも両者は**同じ一つの機能不足**で止まっている。

**和歌山 — 調査で切り捨てられていたが、最良の対象だった**

前回は「北海道の例から PDF だろう」と推測していた。実際は素の UTF-8 HTML で、
索引1ページに平成2年〜令和8年の約150会期が並び、会期ページが各号を、各号が
全文1ページ（約186KB・本文6万字・発言標識98件）を持つ。robots.txt は404、
ページは `index, follow`。静岡の `meta robots` の懸案はここには当てはまらない。

入口も誤っていた。`/gijiroku/` の403はディレクトリ一覧が無効なだけで、配下の
文書は200を返す。正しい入口は `/gijiroku/d00203238.html`。

罠は静岡の裏返し。理事者は `○知事（岸本周平君）` だが、議員は括弧なしの
`○濱口太史君`。静岡の分割規則をそのまま当てれば、コーパスの大半を黙って
取りこぼしていた。質問日／発言日と同じ「1つの形式では足りない」型の失敗で、
今回は先にサンプルを読んだので事前に捕まえられた。

**愛媛・三重・兵庫 — 未解決だった2点が両方とも解決**

- `See.exe` は POST で送っている項目を **GET のクエリ文字列でも受ける**。
  `treedepth` は **cp932** でパーセントエンコードし、会期階層では末尾の空白が
  意味を持つ。POST 対応は不要。
- ページ自身の「ダウンロード」ボタンの送信先 `GetPerson.exe` が **GET を受け付け**、
  `downloadPos` を複数渡すと**その会議の全文をプレーンテキストで返す**。
  1会議あたり2リクエスト（発言索引＋ダウンロード）で済む。

`fileName=R080225A` に日付が入っているため、静岡と違い日付フィルタが実際に
リクエストを節約する。兵庫は**昭和61年**まで遡れ、今回の調査で最も深い。

**4県を一度に開ける唯一の変更**

`GenericScraper` の一覧は1階層＋ページ送りのみ。両対象とも「年/索引 → 会期 →
会議」の2階層で、中間の一覧階層はこの領域に実在する形であって場当たりではない。
これが今いちばん効くコード変更。

**SSP — 突破はないが下ごしらえは済んだ**

18テナントの数値IDを `/tenant/<tenant>/js/*.js` から取得した。ここは Disallow
対象ではない（`Disallow: /tenant/js/` は共有ディレクトリだけに一致し、
`/tenant/prefosaka/js/` には一致しない）。`MinuteView.html?council_id=&schedule_id=`
という固定URL形式と、そのページが完全なクライアント描画であることも確認した。
API は依然 `/tenant/js/release/config.js` の中で、取得していない。

robots.txt とは別の条件も見つけた。大阪のページに「このデータの権利は大阪府議会に
帰属します。転用、その他の用途への利用については…お問い合わせください」とある。
API が判明しても残る条件なので、18県への文面に含めること。

**収集前の確認**

地方議会会議録コーパスプロジェクトが47都道府県の2011–2014・2015–2019を既に
整備している。研究対象期間がその中なら、この収集の大半は不要。空白は2020年以降で、
そこは今回の対象がいちばん安く取れる範囲でもある。

**方法**

計約40リクエスト。すべて `PoliteClient` または2秒間隔の `curl`、ホストごとに直列、
全件キャッシュ。`Disallow` 配下のURLは一件も取得していない。

## 2026-08-26 — 静岡: the first working site config (`feat/shizuoka`)

*English and Japanese. / 英語と日本語で併記する。*

### English

Asked to collect 静岡. It works — this is the first `sites/*.toml` in the project,
verified against real markup. One courtesy question is outstanding before a full
crawl (see below), so no live run has been made.

**Added**

- `sites/shizuoka.toml` — 本会議会議録, driven off the 開催別 view.
- `docs/shizuoka.md` — site notes, what was verified, and the meta-robots question.
- `docs/inquiries/shizuoka.md` — draft note to 議事課 about that question.
- `dates.py` — Domino's month-first `06/23/2025`. Tried last, after the year-first
  forms, so it can never steal a match from them; day-first is deliberately not
  accepted, being indistinguishable for the first twelve days of a month.
- `generic.py` — two escape hatches, both general rather than 静岡-specific:
  - `detail.speech_split`: a regex marking where each speech starts, for pages
    whose transcript is one run of text with 「○知事（鈴木康友君）　…」 markers and no
    per-speech elements. The 「君」 suffix is stripped so speakers join across records.
  - `detail.patterns`: regex per field (date/session/committee/title) matched on
    the container text, for legacy tables that label fields by the neighbouring
    cell — something CSS cannot express. A selector still wins when both are set.
- 8 tests for the above; `_example.toml` and CLAUDE.md document both options.

**The site**

Lotus Domino (`ggiji.nsf`) on `www2.pref.shizuoka.jp` — a different host from the
CMS — serving Shift_JIS over plain GET. `WebView1?OpenView&ExpandView` opens the
whole 開催別 tree in one page, so there is nothing to paginate. Coverage runs from
平成11年5月臨時会. Note that **one document is one 発言単位**, not one sitting: a
member's question plus the answers to it, or a 報告事項 / 委員長報告. 令和7年6月定例会
is 26 documents.

**Collected: 2025**

Scoped to the five 令和7年 sessions with a new `--start-url` override, 119 requests
at 2s apart. `data/静岡県.jsonl` + `data/静岡県.csv`:

```
meetings : 113        speeches : 1,395
chars    : 886,315    range    : 2025-02-18 .. 2025-12-15
```

Every record dated and attributed to a session; 88 distinct speakers; one document
(教育委員会意見) legitimately has no speeches. `ruff`, `mypy --strict` and `pytest`
(49 passed) all clean.

**Three bugs the real data found, all fixed**

- **Encoding.** These pages declare `charset=utf-8` in a `<meta>` tag, send
  `Shift_JIS` in the HTTP header, and are actually **cp932**. Worse, base Shift_JIS
  cannot decode the NEC/IBM extension characters in names like 河原﨑 and 髙梨, so
  one member's name aborted a whole sitting's decode and the fallback silently
  produced garbage — 8 documents parsed to zero speeches. Shift_JIS now normalises
  to cp932, which is what browsers do. Recovered 1,263 → 1,395 speeches.
  (EUC-JP has the same flaw and no fix: CPython ships no MS-extended EUC codec. An
  `eucjp_ms` alias was written, and the test suite caught that no such codec
  exists, so it was removed rather than shipped broken.)
- **Cache lost the header charset.** Re-deriving the encoding on cache read is
  right — a fix to `sniff_encoding` should reach pages already stored — but the
  first attempt passed `None` for the header, and these pages have no truthful
  meta tag, so cached pages decoded *worse* than fresh ones. `Page` now carries
  `header_charset` and the cache round-trips it.
- **`--no-cache` discarded what it fetched.** It gated the write as well as the
  read, so a `--no-cache` run left nothing behind and the next run re-fetched
  everything. It now means "don't serve me a stale copy", not "throw away a
  response we already paid a request for".

**Two site-specific traps, handled in the config**

- 質問文書 label the date 質問日：; 議会補足文書 (報告事項 / 知事提案説明 / 委員長報告)
  use 発言日：. Matching only the first left 60 of 113 records undated.
- The attendance roster 「○出　席　議　員（六十七名）」 has exactly the shape of a speech
  marker and was collected as a speech by 「六十七名」. Requiring the name to end in
  「君」 separates them — over a 40-document sample, 632 markers matched and the only
  four without 「君」 were rosters.

**Also added**

- `pt scrape --start-url` (repeatable) — overrides the config's entry points.
  `--since/--until` cannot scope a crawl on a site whose index carries no dates:
  the filter can only run after a page is fetched, which is too late to save the
  request. Narrowing the entry points is what actually saves them.
- `list.exclude` — regex; links whose text or URL match are not followed. Every
  議会 here opens with a 【目次】 document that would otherwise enter the corpus as
  an empty meeting.

**Open question: meta robots**

There is no robots.txt on `www2.pref.shizuoka.jp` (404), but every page of the
minutes application carries `<meta name="robots" content="none">` plus
`noindex,nofollow` and `noarchive`. The CMS host carries none of that, so it is
specific to this application.

These are indexing directives, not access rules — nothing here says "do not
fetch", which is what a robots.txt `Disallow` would say. A research corpus is not
a public index and republishes no cache. But `nofollow` does describe exactly the
list-then-follow pattern this scraper uses, and `PoliteClient` reads robots.txt
only, so nothing in the toolkit would stop a full run.

Asked, and the decision was to collect 2025 only. That is what was run: 119
requests, one year, spaced 2s. The archive crawl (平成11年 onwards, thousands of
documents) still waits on 議事課 — draft in `docs/inquiries/shizuoka.md`.

**Not done yet**

委員会会議録 (`comgiji.nsf`, same host) — almost certainly the same shape, not yet
opened. And the size of the expanded view is unmeasured, because measuring it
means fetching it.

### 日本語

静岡県の収集を担当した。**動く。** 本プロジェクトで最初の `sites/*.toml` であり、
実際のマークアップに対して検証済み。ただし全件取得の前に確認したい点が1つ残って
いるため（後述）、実サイトへの収集は実行していない。

**追加したもの**

- `sites/shizuoka.toml` — 本会議会議録。「開催別」ビューを起点とする。
- `docs/shizuoka.md` — サイトの構造、検証内容、meta robots の論点。
- `docs/inquiries/shizuoka.md` — 議事課への確認の下書き。
- `dates.py` — Domino の月先行表記 `06/23/2025` に対応。年先行の各形式を試した後に
  適用するため、既存の解釈を奪うことはない。日先行は月の1〜12日で区別できないため
  意図的に採用していない。
- `generic.py` — 静岡専用ではなく汎用の逃げ道を2つ追加。
  - `detail.speech_split`：発言の開始位置を示す正規表現。「○知事（鈴木康友君）　…」の
    ように、発言ごとの要素が無くテキストが一続きのページ向け。名前末尾の「君」は
    除去し、記録間で発言者を突き合わせられるようにした。
  - `detail.patterns`：日付・会議名・委員会名・表題を、コンテナのテキストに対する
    正規表現で拾う。隣接セルの文字列でしか項目を特定できない旧来の表組みは CSS では
    表現できないため。両方指定された場合はセレクタを優先する。
- 上記に対するテスト8件。`_example.toml` と CLAUDE.md にも記載。

**サイトの構造**

`www2.pref.shizuoka.jp`（CMS とは別ホスト）の Lotus Domino アプリ（`ggiji.nsf`）。
Shift_JIS を通常の GET で配信。`WebView1?OpenView&ExpandView` で「開催別」の全階層が
1ページに展開されるため、ページ送りの処理は不要。掲載は平成11年5月臨時会以降。
注意点として、**1文書＝1発言単位**であり1開催日ではない（議員の質問とそれへの答弁、
あるいは報告事項・委員長報告）。令和7年6月定例会で26文書。

**収集した結果：2025年分**

新設の `--start-url` で令和7年の5会期に限定し、2秒間隔で119リクエスト。
`data/静岡県.jsonl` と `data/静岡県.csv`：

```
文書数 : 113        発言数 : 1,395
文字数 : 886,315    期間   : 2025-02-18 〜 2025-12-15
```

全件に日付と会議名が付与され、発言者は88名。発言0件の文書1件（教育委員会意見）は
書面の意見であり、正しく0件である。`ruff`・`mypy --strict`・`pytest`（49件成功）クリーン。

**実データで見つかった不具合3件（いずれも修正済み）**

- **文字コード。** これらのページは `<meta>` で `charset=utf-8` と宣言し、HTTP
  ヘッダでは `Shift_JIS` を返し、実体は **cp932** である。さらに、河原﨑・髙梨のような
  氏名に含まれる NEC/IBM 拡張文字は素の Shift_JIS では復号できず、議員1名の氏名で
  1会議分の復号が中断し、フォールバックが文字化けを黙って生成していた（8文書が発言0件）。
  Shift_JIS を cp932 に正規化するようにした（ブラウザと同じ挙動）。発言数が
  1,263→1,395 に回復。
  （EUC-JP も同じ弱点を持つが、CPython に MS 拡張版の EUC codec が無いため対処なし。
  `eucjp_ms` という別名を書いたところ、そのような codec は存在しないとテストが検出した
  ため、壊れたまま出荷せず削除した。）
- **キャッシュがヘッダの charset を捨てていた。** 読み出し時に符号化を推定し直す方針
  自体は正しい（`sniff_encoding` の修正が既存のキャッシュにも及ぶ）が、最初の実装は
  ヘッダに `None` を渡しており、meta タグが嘘をついているこのサイトでは、キャッシュ
  経由のほうが新規取得より悪い結果になった。`Page` に `header_charset` を持たせ、
  キャッシュで往復させるようにした。
- **`--no-cache` が取得結果を捨てていた。** 読み出しだけでなく書き込みも止めていたため、
  次回実行時に再取得が必要になっていた。「古い写しを渡すな」であって「リクエストを
  払って得た応答を捨てろ」ではない、という意味に修正。

**サイト固有の落とし穴2件（設定側で対処）**

- 質問文書は日付を `質問日：`、議会補足文書（報告事項・知事提案説明・委員長報告）は
  `発言日：` と表記する。前者だけを見ていたため113件中60件が日付なしだった。
- 出席議員名簿「○出　席　議　員（六十七名）」が発言マーカーと同一の形をしており、
  「六十七名」という発言者として収録されていた。氏名末尾の「君」を必須にすることで
  分離できる（40文書の標本で632件が一致し、「君」が無い4件はすべて名簿だった）。

**あわせて追加したもの**

- `pt scrape --start-url`（複数指定可）— 設定の起点を上書きする。一覧に日付が載って
  いないサイトでは `--since/--until` では取得範囲を絞れない（取得後にしか日付が
  分からないため、リクエストの節約にならない）。起点を絞ることが実際の節約になる。
- `list.exclude` — リンクのテキストまたは URL が一致したら辿らない正規表現。各会期の
  冒頭にある【目次】文書が、発言0件の記録として混入するのを防ぐ。

**未解決：meta robots**

`www2.pref.shizuoka.jp` に robots.txt は無い（404）が、会議録アプリの全ページに
`<meta name="robots" content="none">` と `noindex,nofollow`・`noarchive` が付いている。
CMS 側のホストには無いので、このアプリ固有の設定である。

これらは索引付けに関する指示であって取得の可否を定めるものではない（取得を禁じる
のは robots.txt の `Disallow` であり、それは存在しない）。研究用コーパスは公開検索
サービスでもキャッシュの再配布でもない。ただし `nofollow` は、一覧をたどって文書
リンクを開くという本スクレイパーの動作そのものを指しており、`PoliteClient` は
robots.txt しか見ないため、実行を止めるものは何も無い。

確認のうえ、2025年分のみを収集する判断となり、そのとおり実行した（119リクエスト、
1年分、2秒間隔）。全件取得（平成11年以降・数千文書）は議事課への確認まで保留。
文面は `docs/inquiries/shizuoka.md`。

**未着手**

委員会会議録（同一ホストの `comgiji.nsf`）。ほぼ同じ構造と思われるが未確認。
展開後のビューの大きさも未計測（計測すること自体が取得になるため）。

## 2026-08-26 — Inquiry drafts for every blocked assembly (`survey/all-prefectures`)

*English and Japanese. / 英語と日本語で併記する。*

### English

The survey said which assemblies need to be asked. This writes the asking.

**Added**

- `docs/inquiries/` — 27 drafts plus a README index. The two existing drafts moved
  here (`docs/hokkaido-inquiry.md` → `docs/inquiries/hokkaido.md`, same for aomori);
  older LOG entries still name the old paths, which is where they were at the time.

**Four kinds of letter, because the situations differ**

- **Blocked, ask for access (23)** — 15 DB-Search prefectures and 8 gijiroku VOICES
  ones. Same structure as the 北海道 draft: bulk data first, crawl permission
  second, vendor referral third; each names its own system and quotes its own
  robots.txt rule, since a letter that misdescribes the site invites a brush-off.
- **千葉, ask what was meant (1)** — its CGI sits at `/kaigiroku/` and matches none
  of the boilerplate Disallow rules. The letter says plainly that this looks like
  an omission rather than an invitation, and offers to stay away if so.
- **SSP, ask how (2)** — a vendor letter and an assembly template. Not a permission
  request: robots already allows `/tenant/`. What is needed is the data endpoint,
  which is defined in a disallowed script. One vendor reply covers 18 prefectures.
- **`kensakusystem.jp`, courtesy notice (3)** — 三重・兵庫・愛媛 have no robots.txt,
  so nothing needs permission. These say what will be run and offer to stop, rather
  than asking whether it may start.

**Contacts**

Some phone numbers were taken from search results and are **not verified** — each
is marked 未検証・要確認 in the file. Confirm on the assembly's own site, or use its
contact form, before sending.

**Verified**

No code changed; suite untouched at 34 passing. Nothing was sent to anyone — these
are drafts on disk.

### 日本語

調査で「照会が必要」と分かった相手ごとに、実際の文面を用意した。

**追加したもの**

- `docs/inquiries/` — 27通の下書きと索引の README。既存の2通もここへ移動
  （`docs/hokkaido-inquiry.md` → `docs/inquiries/hokkaido.md`、青森も同様）。
  過去の LOG は当時のパスのままにしてある。

**状況が違うので4種類に分けた**

- **取得不可、許可を依頼（23通）** — DB-Search 系15県と gijiroku VOICES 系8県。
  構成は北海道の下書きと同じで、①一括提供 ②取得許可 ③事業者への照会要否 の順。
  各通に当該システム名と当該 robots.txt の記述を書き入れてある。実態と違うことを
  書いた依頼は相手にされないため。
- **千葉、設定の意図を確認（1通）** — CGI が `/kaigiroku/` にあり、定型の Disallow
  記述のどれにも該当しない。「許可の趣旨か、記載漏れか」を率直に尋ね、記載漏れ
  なら直ちに見合わせる旨を明記した。
- **SSP、取得方法を尋ねる（2通）** — 事業者宛と議会宛の雛形。許可の依頼ではない。
  robots.txt は既に `/tenant/` を許可しており、必要なのは Disallow 対象の
  スクリプト内にあるデータ取得先の情報。事業者から1件回答が得られれば18県が動く。
- **`kensakusystem.jp`、事前連絡（3通）** — 三重・兵庫・愛媛は robots.txt が無く、
  許可を求める必要がない。「これから何をするか」を知らせ、支障があれば止める、
  という趣旨の文面にしてある。

**連絡先**

一部の電話番号は検索結果から拾ったもので**未検証**。各ファイルに「未検証・要確認」と
明記した。送信前に各議会のサイトで確認するか、問い合わせフォームを使うこと。

**確認したこと**

コード変更なし、テストは34件成功のまま。いずれも手元の下書きであり、送信はしていない。

## 2026-08-26 — All-47 robots survey (`survey/all-prefectures`)

*English and Japanese. / 英語と日本語で併記する。*

### English

After 北海道 and 青森 both dead-ended on robots.txt, surveyed all 47 prefectures at
once instead of finding the wall one at a time: locate each assembly's minutes
system, fetch its robots.txt, and look at what the pages actually are.

**Added**

- `docs/prefecture-survey.md` — all 47, grouped by platform, with the robots
  verdict and page architecture for each, and a ranked list of what to do next.

**Result: five platforms, and nothing collectable with today's scraper**

- **DB-Search (`*.dbsr.jp`) — 15, blocked.** Identical `Disallow: /` with
  `$`-anchored Allows for the landing page only. Includes 東京 on its own domain.
- **gijiroku VOICES — 9, blocked.** The 北海道 product; CGI directory disallowed.
  One exception: **千葉** installs at `/kaigiroku/` while the boilerplate robots.txt
  only names `/voices/cgi/`, `/gikai/cgi/` and friends, so its
  `/kaigiroku/cgi/voiweb.exe` is not covered by any rule. Permitted as written,
  plainly an oversight rather than an invitation — worth asking before using.
- **SSP (`ssp.kaigiroku.net`) — 18, permitted but architectural.** robots.txt
  explicitly allows `/tenant/`. The tenant pages are a client-side app, though:
  no server-rendered links, data over an API whose endpoint lives in
  `/tenant/js/release/config.js` — one of the four disallowed directories, so it
  was not read. 18 prefectures behind one implementation, blocked on one unknown.
- **`kensakusystem.jp` — 3 (三重・兵庫・愛媛), permitted.** No robots.txt at all
  (404), server-rendered Shift_JIS CGI pages. The closest thing to a working
  target; wrinkles are a `Code=` session token (stable, sits in `index.html`) and
  POST-based navigation.
- **Own CMS — 2 (静岡・和歌山), permitted, format unverified.** Expect PDF.

**Recommended order**: get the SSP API path (one browser session or one email —
18 prefectures ride on it); build 愛媛 or 三重 on `kensakusystem.jp` to prove the
pipeline; keep asking for the blocked ones; and before collecting anything, check
whether 地方議会会議録コーパスプロジェクト (local-politics.jp, 都道府県議会 corpus for
2011–2014 and 2015–2019) already covers the research window.

**Verified**

Every robots.txt in the table was fetched directly; systems were identified from
each prefecture's own assembly pages or from search. Requests spaced 2–3s and
serialised per service. One early parallel pass over `dbsr.jp` hosts drew
`429 Too Many Requests` — my error, redone sequentially. Nothing under a Disallow
rule was fetched, including the SSP config script, which is exactly why the API
path is still open. No code changed; suite untouched at 34 passing.

### 日本語

北海道・青森が続けて robots.txt で行き止まりになったため、1県ずつ確かめるのをやめ、
47都道府県を一度に調査した。各議会の会議録システムを特定し、robots.txt を取得し、
ページが実際にどういう作りかを確認した。

**追加したもの**

- `docs/prefecture-survey.md` — 47都道府県をプラットフォーム別にまとめ、robots の
  可否とページ構造、次に着手すべき順序を記載。

**結果：5系統、いずれも現在のスクレイパーでは収集できない**

- **DB-Search（`*.dbsr.jp`）15県：不可。** すべて同一の `Disallow: /` で、`Allow` は
  `$` 付きのトップページのみ。東京都（独自ドメイン）も同じ。
- **gijiroku VOICES 9県：不可。** 北海道と同じ製品で、CGI ディレクトリが Disallow。
  ただし**千葉**のみ設置パスが `/kaigiroku/` であり、robots.txt が挙げるのは
  `/voices/cgi/` や `/gikai/cgi/` 等だけなので、`/kaigiroku/cgi/voiweb.exe` は
  どの規則にも該当しない。文面上は許可だが、他テナントの設定を見れば設定漏れと
  考えるのが自然で、利用前に照会すべき。
- **SSP（`ssp.kaigiroku.net`）18県：robots は許可、構造が壁。** `/tenant/` は明示的に
  Allow。ただしテナントページは JavaScript アプリで、サーバ側で描画されたリンクが
  なく、データは API 経由。その API のパスは `/tenant/js/release/config.js` に
  あるが、これは Disallow 対象の4ディレクトリの一つなので取得していない。
  18県が一実装で賄える一方、未知の1点で止まっている。
- **`kensakusystem.jp` 3県（三重・兵庫・愛媛）：許可。** robots.txt が存在しない（404）。
  Shift_JIS のサーバ描画 CGI ページで、現行スクレイパーに最も近い。難点は
  `Code=` というセッショントークン（安定、`index.html` に埋め込み）と POST 遷移。
- **県の CMS 2県（静岡・和歌山）：許可、形式未確認。** PDF の可能性が高い。

**推奨する順序**：SSP の API パスを入手する（ブラウザ1回か問い合わせ1通で18県が動く）、
`kensakusystem.jp` で愛媛か三重を作ってパイプラインを実証する、不可の県は照会を続ける、
そして収集前に地方議会会議録コーパスプロジェクト（local-politics.jp、2011–2014年・
2015–2019年の都道府県議会コーパス）が研究対象期間を満たしていないか確認する。

**確認したこと**

表中の robots.txt はすべて直接取得した。システムの特定は各県議会のページまたは
検索による。リクエストは2〜3秒間隔、サービスごとに直列化した。初回に `dbsr.jp` へ
並列アクセスして `429 Too Many Requests` を招いたのは当方の誤りで、逐次実行で
やり直した。Disallow 配下は SSP の設定スクリプトを含め一切取得していない
（API パスが未解明なのはそのため）。コード変更なし、テストは34件成功のまま。

## 2026-08-26 — Aomori survey (`feat/aomori-survey`)

*This entry is written in English and Japanese. / この記録は英語と日本語で併記する。*

### English

Asked to take on 青森県議会 (Aomori). Surveyed it; it is blocked, like Hokkaido,
and again by robots.txt rather than by anything the scraper could be taught.

**Added**

- `docs/aomori.md` — the survey: where the minutes live, the URL scheme, the
  coverage table by 会議 type, the blocker, and what to do next.
- `docs/aomori-inquiry.md` — Japanese draft of the access request to
  青森県議会事務局, matching the Hokkaido one.

**What is there**

Neither the prefectural site nor the assembly's own pages publish transcripts.
Both link to one external system, 青森県議会会議録検索システム
(`https://www.pref.aomori.dbsr.jp/index.php/`) — a DB-Search tenant, UTF-8,
GET navigation, regular URLs of the form
`/index.php/100000?Template=list&Cabinet=<n>`. Coverage is good: 定例会 and
臨時会 from 昭和58年度, 決算特別委員会 from 昭和58年度, 予算特別委員会 from 平成9年度,
常任委員会 from 平成12年度, 議員発議 back to 昭和22年度. Committees are spread over
`Cabinet` ids 5–20 because the committees themselves were renamed over the
years, so a committee crawl has to enumerate all of them.

**Why there is no `sites/aomori.toml`**

`https://www.pref.aomori.dbsr.jp/robots.txt` is:

```
User-agent: *
Disallow: /
Allow: /$
Allow: /index.php$
Allow: /index.php/$
```

The `Allow` rules are `$`-anchored and match only the bare landing page, so
every list, search result and transcript page falls under `Disallow: /`. That is
stricter than Hokkaido, where the navigation pages were open and only
`/voices/cgi/` was closed. The crawlable surface here is one page with no
minutes on it, so no selector could be verified and no config is shipped.

**Verified**

The two prefectural pages linking to the system, the system's landing page and
its robots.txt were fetched once each on 2026-08-26. Nothing under a disallowed
path was requested. No code changed, so the suite is untouched at 34 passing.

**Next**

Two prefectures, two robots.txt walls, different vendors and different reasons.
Before more site configs, run the cheap check first — fetch only `robots.txt`
for each prefecture's minutes system — and pick targets from what is actually
collectable.

### 日本語

青森県議会を担当することになったので調査した。結論は北海道と同じく「取得不可」で、
理由もまたスクレイパー側の工夫では解決できない robots.txt である。

**追加したもの**

- `docs/aomori.md` — 調査結果。会議録の所在、URL の規則、会議種別ごとの登録範囲、
  阻害要因、次の手。
- `docs/aomori-inquiry.md` — 青森県議会事務局への依頼文の下書き（北海道と同趣旨）。

**分かったこと**

県のサイトにも議会のページにも会議録本体はなく、いずれも外部の
「青森県議会会議録検索システム」（`https://www.pref.aomori.dbsr.jp/index.php/`）に
リンクしているだけである。DB-Search 系のテナントで、UTF-8、遷移は GET、URL は
`/index.php/100000?Template=list&Cabinet=<n>` という規則的な形をしている。
登録範囲は広く、定例会・臨時会は昭和58年度以降、決算特別委員会も昭和58年度以降、
予算特別委員会は平成9年度以降、常任委員会は平成12年度以降、議員発議は昭和22年度以降。
常任委員会が `Cabinet` 5〜20 に分かれているのは委員会名の改称によるもので、
委員会を網羅するには全 id を列挙する必要がある。

**`sites/aomori.toml` を作らなかった理由**

同システムの robots.txt は上記のとおり `Disallow: /` で、`Allow` は `$` 付きの
完全一致であるため、トップページ以外はすべて対象外となる。一覧・検索結果・
会議録本文のいずれも取得が認められていない。北海道は `/voices/cgi/` のみが
Disallow で遷移用ページは開いていたが、青森はより厳しい。取得してよいのは
会議録が載っていないトップページ1枚だけなので、セレクタを確認する手段がなく、
推測で設定ファイルを置くことはしない。

**確認したこと**

2026年8月26日、システムへリンクしている県側の2ページ、システムのトップページ、
robots.txt を各1回ずつ取得した。Disallow 配下は一切取得していない。
コードは変更していないため、テストは34件成功のまま。

**次にやること**

2県続けて robots.txt で止まった。ベンダーも理由も異なる。個別に設定ファイルを
書き始める前に、各県の会議録システムの `robots.txt` だけを取得する軽い調査を行い、
実際に収集できる県から着手する方が早い。

## 2026-08-26 — Hokkaido survey + CSV output (`feat/hokkaido-2025`)

Asked to collect 北海道 for 2025 from
<https://www.gikai.pref.hokkaido.lg.jp/kaigiroku/>, and to store the records as
CSV. The CSV half is done; the Hokkaido half is blocked, and the survey is
written up rather than guessed around.

**Added**

- `storage.py` — `SpeechCsvWriter` (append-as-you-go, one file per prefecture,
  sibling of the JSONL) and `write_csv()` (whole corpus in one pass). One row per
  speech, meeting-level fields repeated on each row, utf-8-sig so Excel reads
  Japanese correctly. A meeting with no speeches still gets a row with blank
  speech columns — a sitting whose selectors produced nothing should be visible
  in the table, not absent from it.
- `cli.py` — `pt scrape --csv` writes both files as records arrive, so an
  interrupted run leaves them consistent; `pt export <jsonl>` rebuilds the CSV
  from the canonical JSONL (which is what a resumed run needs, since `--csv`
  appends only that run's meetings).
- `docs/hokkaido.md` — the site survey, with a draft TOML.
- `docs/hokkaido-inquiry.md` — a Japanese draft of the access request to
  議事課, since that was the route chosen over overriding robots.
- 5 tests covering row-per-speech, embedded newlines/commas, empty meetings,
  append-without-duplicate-header, and JSONL/CSV filename pairing.

**Hokkaido: why there is still no `sites/hokkaido.toml`**

The URL we were given is a portal, not a search system. It leads to two places:

- **会議録データベース** (`pref-hokkaido.gijiroku.com/voices/`) — the real corpus,
  本会議 back to 昭和46年, HTML. Navigation is plain GET, but every result list and
  transcript page is served from `/voices/cgi/voiweb.exe` inside an `<iframe>`,
  and that host's `robots.txt` has `User-agent: * / Disallow: /voices/cgi/`.
  `PoliteClient` refuses those URLs, and `GenericScraper` does not follow
  iframes in the first place.
- **会議録（速報）** (`/kaigiroku/kaigiroku_sokuhou/`) — PDF only, and by design
  temporary: it holds sittings whose official minutes have not landed in the
  database yet. It has no 2025 本会議 at all.

So 2025 本会議 is not reachable without either an access arrangement with the
assembly or a deliberate `PT_RESPECT_ROBOTS=0`, which is a research-owner
decision and contradicts the crawling convention in CLAUDE.md. Rather than ship
a config with invented selectors — the pages that would define them are exactly
the ones robots.txt puts off-limits, so nothing could be verified — the draft
sits in `docs/hokkaido.md` with the verified parts (start URL derived from the
令和7年 iframe, `KGTP`/`KTYP` parameters, the 和暦 date forms) filled in and the
two selector blocks marked TODO.

**Verified**

`ruff check`, `ruff format --check`, `mypy --strict` and `pytest` (34 passed)
clean. End-to-end: `pt scrape --csv` against a local fixture server produced
matching JSONL and CSV (2 meetings, 4 speech rows, 和暦 dates parsed, header
written once); `pt export` rebuilt the same 4 rows from the JSONL; a second run
resumed, fetched nothing new, and printed the note about `pt export`. Every
Hokkaido URL, query parameter and robots rule in the survey was checked against
the live site with single manual requests; nothing under `/voices/cgi/` was
fetched.

**Not done yet**

Hokkaido itself. The access route chosen is to ask the assembly first, so the
next step is sending `docs/hokkaido-inquiry.md` (fill in the `{ }` placeholders)
and waiting; the draft config stays out of `sites/` until the reply decides
whether we get a bulk export or a conditional crawl.

## 2026-08-26 — Scraping toolkit scaffold (`feat/scraping-setup`)

First code in the repo. Set up a uv-managed Python package and the scraping
infrastructure for collecting prefectural assembly minutes.

**Added**

- `pyproject.toml` / `uv.lock` — uv project, Python ≥3.11, `pt` console script.
  Runtime deps: httpx, beautifulsoup4, lxml, charset-normalizer, pydantic, typer.
  Dev: pytest, ruff, mypy (strict).
- `http.py` — `PoliteClient`: per-host rate limiting, robots.txt (incl.
  `Crawl-delay`), retries honouring `Retry-After`, and an on-disk response cache.
  Plus `sniff_encoding`, which prefers the `<meta charset>` over the HTTP header
  because these sites are commonly proxied with a wrong `charset=`.
- `dates.py` — 和暦 parsing (令和/平成/昭和/大正/明治, `元年`, `R7.6.10`) and western forms.
- `models.py` — `Speech` / `MeetingRef` / `Meeting` pydantic models.
- `storage.py` — JSONL corpus writer, one file per prefecture, with `seen_keys()`
  for resuming an interrupted run.
- `scrapers/` — `BaseScraper` (list/parse split so crawls can resume and be
  date-filtered) and `GenericScraper`, driven entirely by a TOML site config.
- `sites/_example.toml` — annotated template; adding a prefecture is a config
  file, not a new module.
- `cli.py` — `pt sites`, `pt scrape`, `pt inspect` (selector development),
  `pt stats`.
- 29 tests, all offline via a fake client and local HTML fixtures.

**Decisions**

- *Config-driven scrapers over per-prefecture Python.* Most assemblies use one of
  a few vendor 会議録検索システム products with the same page shape and different
  selectors, so the variation belongs in data.
- *No real site configs shipped.* Selectors have not been verified against any
  live assembly site, and guessing them would produce code that looks working and
  is not. `sites/` contains only the template.
- *Defaults are slow on purpose* — 2s between requests to a host, robots.txt
  respected, everything cached — because these are small public-sector servers.
- *JSONL over a database.* Downstream analysis wants to stream the corpus, and a
  partial run still leaves a valid file.

**Verified**

`ruff check`, `ruff format --check`, `mypy --strict` and `pytest` (29 passed) all
clean. End-to-end run against a local Shift_JIS fixture server: index paginated,
dates parsed from 和暦, speeches extracted with speaker/role, JSONL written and
read back by `pt stats`; a second run correctly resumed and made no new requests.

**Not done yet**

No real prefecture is configured. Next step is picking a target assembly, using
`pt inspect` to work out its selectors, and adding `sites/<name>.toml`.
