#!/bin/zsh
# System monitor data for the desktop widget (JSON).
# CPU: 100 - idle over a 2 s sample (the first top sample is since boot, so take the last).
cpu=$(top -l 2 -n 0 -s 2 | awk '/CPU usage/{gsub("%","",$7); i=$7} END{printf "%.0f", 100-i}')
# Memory "used" as Activity Monitor counts it: app (internal - purgeable) + wired + compressed.
mem=$(sysctl -n hw.memsize hw.pagesize vm.page_pageable_internal_count vm.page_purgeable_count |
  paste -s - | awk -v w="$(vm_stat | awk '/wired down/{gsub("\\.","",$4); print $4}')" \
    -v c="$(vm_stat | awk '/occupied by compressor/{gsub("\\.","",$5); print $5}')" \
    '{printf "%.0f", ($3-$4+w+c)*$2/$1*100}')
# Disk as Finder/System Settings shows it: available includes purgeable space, decimal GB.
read avail total <<<"$(osascript -l JavaScript -e 'ObjC.import("Foundation"); var k="NSURLVolumeAvailableCapacityForImportantUsageKey", t="NSURLVolumeTotalCapacityKey"; var r=$.NSURL.fileURLWithPath("/").resourceValuesForKeysError($([k,t]),null); r.objectForKey(k).js+" "+r.objectForKey(t).js')"
disk=$(awk -v a="$avail" -v t="$total" 'BEGIN{printf "%.0f", (t-a)/t*100}')
diskfree=$(awk -v a="$avail" 'BEGIN{printf "%.0f GB", a/1e9}')
batt=$(pmset -g batt | grep -o '[0-9]*%' | head -1 | tr -d '%')
charging=$(pmset -g batt | grep -q "AC Power" && echo true || echo false)
up=$(uptime | sed -E 's/.*up ([^,]*),.*/\1/; s/^ +//')
procs=$(ps -A | wc -l | tr -d ' ')
print "{\"cpu\":${cpu:-0},\"mem\":${mem:-0},\"disk\":${disk:-0},\"diskFree\":\"$diskfree\",\"batt\":${batt:-0},\"charging\":$charging,\"uptime\":\"$up\",\"procs\":$procs}"
