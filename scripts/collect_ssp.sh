#!/usr/bin/env bash
# Collect the 17 SSP tenants, one after another.
#
# **Sequentially, in one process, on purpose.** All 17 tenants are one host
# (ssp.kaigiroku.net) and `PoliteClient`'s rate limiter is per-process, so two of
# these running at once would halve the 5 s interval that the 2026-09-18 decision
# was made with. See docs/ssp.md §1.
#
# Order is smallest archive first, so that whole prefectures finish early and the
# checks in docs/ssp.md §7 can be run against a complete corpus rather than a
# partial one. 宮城 is last: 4,234 会議 on its own.
#
# Resumable: every response is cached and `pt scrape` skips what the JSONL already
# holds, so re-running this after an interruption costs nothing for the part
# already done. Each tenant writes a `.done` marker; the run writes `DONE` at the
# end. **Wait on those, or on the pid — never on a pgrep of this script's own
# command line, which matches the shell running it** (that mistake has cost this
# project 27 hours once already).
#
#   bash scripts/collect_ssp.sh                  # foreground
#   nohup bash scripts/collect_ssp.sh &> /dev/null &   # and leave it
#   tail -f data/logs/ssp/<site>.log
#   until [ -f data/logs/ssp/DONE ]; do sleep 300; done   # wait, correctly

set -uo pipefail
cd "$(dirname "$0")/.."

DELAY=${PT_SSP_DELAY:-5}
LOGS=data/logs/ssp
mkdir -p "$LOGS"

SITES=(
  ssp_fukushima   # 124 会議
  ssp_oita        # 163
  ssp_okayama     # 184
  ssp_kumamoto    # 214
  ssp_saitama     # 240
  ssp_yamaguchi   # 267
  ssp_yamagata    # 331
  ssp_nara        # 351
  ssp_kanagawa    # 465
  ssp_okinawa     # 509
  ssp_gifu        # 633
  ssp_nagasaki    # 1,089
  ssp_tokushima   # 1,308
  ssp_kochi       # 1,336
  ssp_niigata     # 1,440
  ssp_akita       # 2,022
  ssp_miyagi      # 4,234
)

rm -f "$LOGS/DONE"
echo "$(date -Is) starting ${#SITES[@]} tenants at ${DELAY}s/request, pid $$" | tee -a "$LOGS/run.log"

for site in "${SITES[@]}"; do
  if [ -f "$LOGS/$site.done" ]; then
    echo "$(date -Is) $site already done, skipping" | tee -a "$LOGS/run.log"
    continue
  fi
  echo "$(date -Is) $site starting" | tee -a "$LOGS/run.log"
  if uv run pt scrape "$site" --delay "$DELAY" >> "$LOGS/$site.log" 2>&1; then
    touch "$LOGS/$site.done"
    tail -n 9 "$LOGS/$site.log" | tee -a "$LOGS/run.log"
    echo "$(date -Is) $site finished" | tee -a "$LOGS/run.log"
  else
    # A failure is left without a .done marker so a re-run picks it up, and the
    # run carries on: one tenant refusing is not a reason to stop the other 16.
    echo "$(date -Is) $site FAILED (exit $?); see $LOGS/$site.log" | tee -a "$LOGS/run.log"
  fi
  # The interval is per-process, so a fresh process could otherwise fire its first
  # request immediately after the previous one's last.
  sleep "$DELAY"
done

date -Is > "$LOGS/DONE"
echo "$(date -Is) all tenants attempted" | tee -a "$LOGS/run.log"
