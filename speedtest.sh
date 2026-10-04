#!/bin/zsh
# Speed test via macOS's built-in networkQuality, cached in ~/.stark/.speed.json.
# A test moves ~150 MB, so it runs at most every SPEED_EVERY minutes (and never on an iPhone hotspot).
# `speedtest.sh now` forces one (the widget's ↻ button). One test at a time.
SPEED_EVERY=180
D=~/.stark; out=$D/.speed.json; lock=$D/.speed.lock
[[ -e $lock && $(( $(date +%s) - $(stat -f %m $lock) )) -lt 60 ]] && exit 0
if [[ $1 != now ]]; then
  [[ -e $out && $(( $(date +%s) - $(stat -f %m $out) )) -lt $(( SPEED_EVERY * 60 )) ]] && exit 0
  [[ $(route -n get default 2>/dev/null | awk '/gateway:/{print $2}') == 172.20.10.1 ]] && exit 0
fi
touch $lock
networkQuality -c -M 8 2>/dev/null | python3 -c '
import json, sys, time
d = json.load(sys.stdin)
print(json.dumps({"down": d["dl_throughput"], "up": d["ul_throughput"], "rpm": round(d.get("responsiveness", 0)),
                  "rtt": round(d.get("base_rtt", 0)), "at": int(time.time())}))' > $out.tmp && mv $out.tmp $out
rm -f $lock $out.tmp
