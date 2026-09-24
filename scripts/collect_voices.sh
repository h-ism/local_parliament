#!/usr/bin/env bash
# Collect the assemblies that have answered, inside the terms each of them set.
#
# 滋賀 and 石川 permitted automated collection on 2026-09-18 on one condition:
# **weekend evenings, from 20:00**. 石川 added that the assembly sits until
# 2026-09-30 and asked us to mind the hours especially then — so collection there
# starts in October. That is their emphasis rather than their rule, and following
# it costs nothing.
#
# Three things have to be true before a single request goes out, and each says so
# rather than failing quietly:
#
#   1. October has started (the guard below), for 石川.
#   2. A config exists in sites/ — which means someone has read the markup from
#      the reconnaissance cache and written selectors. Until then this exits and
#      says what is missing.
#   3. The window is open. `PoliteClient` carries `[fetch_window]` from the
#      config, so this is enforced per request and not just by the timer: when
#      midnight closes the window mid-run the scrape stops, and the next window
#      resumes from the corpus.
#
#   bash scripts/collect_voices.sh              # every VOICES site that is ready
#   bash scripts/collect_voices.sh ishikawa
#
# Wait on the markers, never on a pgrep of this script's own command line — that
# matches the shell running it, which has cost this project real time twice.

set -uo pipefail
cd "$(dirname "$0")/.."

DELAY=${PT_VOICES_DELAY:-2}   # the first undertaking in our letter
LOGS=data/logs/voices
mkdir -p "$LOGS"

# site:not-before — empty means no date constraint
SITES_ALL=(
  "shiga:"
  "ishikawa:2026-10-01"
  "iwate:"
  "ibaraki:"
  "tochigi:"      # also gated by [notice]: pt scrape refuses without one, and
                  # by a 土日 window — their vendor asked for weekend nights
                  # while the assembly sits (会期 9/17-10/13). A weekday firing
                  # here is meant to refuse; that is the window doing its job.
)

wanted=("$@")
exec 9>"$LOGS/collect.lock"
if ! flock -n 9; then
  echo "$(date -Is) another VOICES collector holds the lock" >> "$LOGS/run.log"
  exit 0
fi

today=$(date +%Y-%m-%d)
ran=0
for entry in "${SITES_ALL[@]}"; do
  site=${entry%%:*}
  not_before=${entry#*:}
  if [ ${#wanted[@]} -gt 0 ] && [[ ! " ${wanted[*]} " == *" $site "* ]]; then
    continue
  fi

  if [ -n "$not_before" ] && [[ "$today" < "$not_before" ]]; then
    echo "$(date -Is) $site: not before $not_before (定例会の会期中) — skipping" \
      | tee -a "$LOGS/run.log"
    continue
  fi

  config=src/prefectural_transcripts/sites/$site.toml
  if [ ! -f "$config" ]; then
    echo "$(date -Is) $site: NO CONFIG at $config — the selectors have not been written yet;" \
      "read data/logs/$site/recon-*.txt and the cache first. Nothing fetched." \
      | tee -a "$LOGS/run.log"
    continue
  fi

  echo "$(date -Is) $site starting" | tee -a "$LOGS/run.log"
  if uv run pt scrape "$site" --delay "$DELAY" >> "$LOGS/$site.log" 2>&1; then
    echo "$(date -Is) $site finished (or the window closed)" | tee -a "$LOGS/run.log"
  else
    # Outside the agreed hours is an ordinary outcome here, not a fault: the
    # window closes at midnight and the next one picks the crawl up.
    echo "$(date -Is) $site stopped (exit $?); see $LOGS/$site.log" | tee -a "$LOGS/run.log"
  fi
  tail -n 6 "$LOGS/$site.log" | tee -a "$LOGS/run.log"
  ran=$((ran + 1))
  sleep "$DELAY"
done

[ "$ran" -eq 0 ] && echo "$(date -Is) nothing was ready to collect" >> "$LOGS/run.log"
exit 0
