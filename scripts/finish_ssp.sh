#!/usr/bin/env bash
# Bring every collected SSP corpus up to date with the current rules.
#
# **The order is the point.** `reparse.py` rebuilds each record from the cached
# response, which means it rebuilds the speakers too — so running it after
# `split_titles.py` silently undoes the split. Re-parse first, split second,
# export third. Everything here reads the cache and writes locally: zero
# requests, and `Settings.offline` makes that true by construction.
#
#   bash scripts/finish_ssp.sh            # all seventeen
#   bash scripts/finish_ssp.sh 宮城県     # one of them (still splits over all)

set -uo pipefail
cd "$(dirname "$0")/.."

LOG=data/logs/ssp/finish.log
mkdir -p "$(dirname "$LOG")"

# site:corpus, in the order they were collected
PAIRS=(
  ssp_fukushima:福島県  ssp_oita:大分県      ssp_okayama:岡山県   ssp_kumamoto:熊本県
  ssp_saitama:埼玉県    ssp_yamaguchi:山口県 ssp_yamagata:山形県  ssp_nara:奈良県
  ssp_kanagawa:神奈川県 ssp_okinawa:沖縄県   ssp_gifu:岐阜県      ssp_nagasaki:長崎県
  ssp_tokushima:徳島県  ssp_kochi:高知県     ssp_niigata:新潟県   ssp_akita:秋田県
  ssp_miyagi:宮城県
)

say() { echo "$(date -Is) $*" | tee -a "$LOG"; }

say "=== 1/3 re-parse from cache (rebuilds speakers; must precede the split)"
corpora=()
for pair in "${PAIRS[@]}"; do
  site=${pair%%:*}; pref=${pair##*:}
  [ $# -gt 0 ] && [[ ! " $* " == *" $pref "* ]] && continue
  corpora+=("data/$pref.jsonl")
  say "  $pref"
  uv run python scripts/reparse.py "$site" "data/$pref.jsonl" 2>&1 | tail -1 | tee -a "$LOG"
done

say "=== 2/3 split the titles the scraper kept whole"
uv run python scripts/split_titles.py "${corpora[@]}" --apply 2>&1 \
  | grep -E "^(===|  split|  kept|  distinct|  speakers invented|total|office voc)" | tee -a "$LOG"

say "=== 3/3 export CSV"
for corpus in "${corpora[@]}"; do
  uv run pt export "$corpus" 2>&1 | tail -1 | tee -a "$LOG"
done

say "=== done"
