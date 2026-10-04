#!/bin/zsh
# Syncs every Mail.app account (new mail + read/unread flags from other devices).
# Run by launchd: every 10 minutes ("timer") and whenever the network changes ("network").
LOG=~/.stark/mail-sync.log STAMP=~/.stark/.mail-sync-last
reason=${1:-manual}
log() { print "$(date '+%F %T') [$reason] $1" >> $LOG; tail -n 300 $LOG > $LOG.tmp && mv $LOG.tmp $LOG; }

pgrep -xq Mail || { log "Mail not running — skipped"; exit 0; }

# Network changes fire several events in a row; sync at most once per 30s for those.
if [[ $reason == network && -f $STAMP ]] && (( $(date +%s) - $(<$STAMP) < 30 )); then exit 0; fi

# Wait up to ~40s for the new connection to actually reach the internet.
online=""
for i in {1..20}; do
  curl -s -m 3 -o /dev/null https://www.apple.com/library/test/success.html && { online=1; break; }
  sleep 2
done
[[ -z $online ]] && { log "offline — skipped"; exit 0; }

date +%s > $STAMP
out=$(osascript <<'AS' 2>&1
tell application "Mail"
  check for new mail
  set synced to {}
  set names to name of every account whose enabled is true
  repeat with n in names
    try
      synchronize with account (contents of n)
      set end of synced to (contents of n)
    end try
  end repeat
  set AppleScript's text item delimiters to ", "
  return synced as text
end tell
AS
)
log "synced: $out"
