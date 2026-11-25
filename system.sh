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
# osascript's JavaScript bridge is heavy, so it runs at most every 5 minutes; the answer is cached in .disk.
cache=~/.stark/.disk
if [[ ! -s $cache || -n $(find $cache -mmin +5) ]]; then
  osascript -l JavaScript -e 'ObjC.import("Foundation"); var k="NSURLVolumeAvailableCapacityForImportantUsageKey", t="NSURLVolumeTotalCapacityKey"; var r=$.NSURL.fileURLWithPath("/").resourceValuesForKeysError($([k,t]),null); r.objectForKey(k).js+" "+r.objectForKey(t).js' > $cache.tmp 2>/dev/null &&
    [[ -s $cache.tmp ]] && mv $cache.tmp $cache
fi
read avail total < $cache
disk=$(awk -v a="$avail" -v t="$total" 'BEGIN{printf "%.0f", (t-a)/t*100}')
diskfree=$(awk -v a="$avail" 'BEGIN{printf "%.0f GB", a/1e9}')
batt=$(pmset -g batt | grep -o '[0-9]*%' | head -1 | tr -d '%')
charging=$(pmset -g batt | grep -q "AC Power" && echo true || echo false)
# Battery health as System Settings shows it (maximum capacity, cycle count, condition). system_profiler is slow
# and these barely change, so it runs at most hourly; the answer is cached in .battery.
bcache=~/.stark/.battery
if [[ ! -s $bcache || -n $(find $bcache -mmin +60) ]]; then
  system_profiler SPPowerDataType 2>/dev/null | awk -F': ' '
    /Cycle Count/{c=$2} /Condition/{k=$2} /Maximum Capacity/{gsub("%","",$2); m=$2}
    END{if (c != "") print c "\t" m "\t" k}' > $bcache.tmp && [[ -s $bcache.tmp ]] && mv $bcache.tmp $bcache
fi
IFS=$'\t' read cycles health cond < $bcache 2>/dev/null
# Uptime from the boot time: "45m", "3h 59m" or "2d 4h" (uptime's own "3:59" reads like minutes:seconds)
boot=$(sysctl -n kern.boottime | awk '{gsub(",",""); print $4}'); up=$(( $(date +%s) - boot ))
if (( up >= 86400 )); then up="$(( up / 86400 ))d $(( up % 86400 / 3600 ))h"
elif (( up >= 3600 )); then up="$(( up / 3600 ))h $(( up % 3600 / 60 ))m"; else up="$(( up / 60 ))m"; fi
procs=$(ps -A | wc -l | tr -d ' ')
print "{\"cpu\":${cpu:-0},\"mem\":${mem:-0},\"disk\":${disk:-0},\"diskFree\":\"$diskfree\",\"batt\":${batt:-0},\"charging\":$charging,\"uptime\":\"$up\",\"procs\":$procs,\"cycles\":${cycles:-null},\"health\":${health:-null},\"condition\":\"${cond:-}\"}"
