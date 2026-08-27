# 問い合わせ文の下書き一覧

`docs/prefecture-survey.md` の調査結果にもとづき、照会が必要な相手ごとに文面を
用意したもの。いずれも下書きで、`{ }` の箇所（氏名・所属・研究課題・対象年度・
連絡先など）を埋めてから送ること。robots.txt の記述はすべて 2026-08-26 時点。

**連絡先について**：一部の電話番号は検索結果から拾ったもので、当方では未検証。
「未検証・要確認」と付記してある。送信前に各議会のサイトで確認するか、
問い合わせフォームを使うこと。

## 1. 取得が禁止されている議会（許可・データ提供の依頼）

### DB-Search 系（robots.txt が `Disallow: /`、トップページのみ許可）

[青森](aomori.md) ・ [茨城](ibaraki.md) ・ [東京](tokyo.md) ・ [富山](toyama.md) ・
[山梨](yamanashi.md) ・ [愛知](aichi.md) ・ [京都](kyoto.md) ・ [鳥取](tottori.md) ・
[島根](shimane.md) ・ [広島](hiroshima.md) ・ [香川](kagawa.md) ・ [福井](fukui.md) ・
[福岡](fukuoka.md) ・ [佐賀](saga.md) ・ [鹿児島](kagoshima.md)

### gijiroku VOICES 系（会議録配信用の CGI ディレクトリが Disallow）

[北海道](hokkaido.md) ・ [岩手](iwate.md) ・ [栃木](tochigi.md) ・ [群馬](gunma.md) ・
[石川](ishikawa.md) ・ [長野](nagano.md) ・ [滋賀](shiga.md) ・ [宮崎](miyazaki.md)

## 2. 設定の意図を確認する

[千葉](chiba.md) — 同系統の他県では Disallow されている CGI が、設置パスの違いに
より robots.txt のどの記載にも該当していない。文面上は取得可能だが記載漏れの
可能性が高いため、意図を確認してから判断する。

## 3. データ取得方法を尋ねる（SSP、18県）

**2026-08-27 に位置づけが変わった。** データを返す API は `/dnp/search/` にあり、
`/tenant/` の外なので `Disallow: /` の対象。**取得は許可されていない**ので、これは
節1と同じ許可の依頼である（かつてここには「robots.txt は取得を許可している」と
書いていたが、誤りだった）。

[議会宛の雛形](ssp-assembly.md) — **まず大阪府議会に送る。** 18県で唯一、自分の
ページに宛先を名指ししている。事業者の窓口を尋ねる先としても最短で、大阪の再利用
条件はいずれにせよ照会が要る。

[事業者宛](ssp-vendor.md) — 宛先は NTT アドバンステクノロジ株式会社（`config.js`
の著作権表示）。部署・窓口が未確認なので、大阪からの回答を待ってから送るのが確実。

## 4. 事前連絡（取得は可能だが一報を入れる）

[三重](mie.md) ・ [兵庫](hyogo.md) ・ [愛媛](ehime.md) — robots.txt が存在せず制限は
ないが、継続的にアクセスする以上、先に知らせて条件があれば従う。

## 5. meta robots の趣旨を確認する

[静岡](shizuoka.md) — robots.txt は無いが、会議録アプリの全ページに
`<meta name="robots" content="none">`（noindex, nofollow, noarchive）が付いている。
索引付けに関する指示であって取得の禁止ではないが、研究目的の収集まで含む趣旨かを
確認する。設定ファイルは動く状態にあるので、返答を待って全件取得に進む。
詳細は `docs/shizuoka.md`。

## 照会が不要なところ

和歌山は県の CMS で公開しており、robots.txt に会議録を妨げる記載はない。
ただし本文が HTML か PDF かを未確認のため、まず形式を確かめてから判断する。
