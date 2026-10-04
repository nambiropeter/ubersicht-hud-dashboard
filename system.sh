#!/bin/zsh
# System monitor data for the desktop widget (JSON).
cpu=$(top -l 2 -n 0 -s 1 | awk '/CPU usage/{u=$3+$5} END{printf "%.0f", u}')
mem=$(memory_pressure 2>/dev/null | awk '/free percentage/{gsub("%","",$5); print 100-$5}')
disk=$(df -k /System/Volumes/Data | awk 'NR==2{printf "%.0f", $3/$2*100}')
diskfree=$(df -h /System/Volumes/Data | awk 'NR==2{print $4}')
batt=$(pmset -g batt | grep -o '[0-9]*%' | head -1 | tr -d '%')
charging=$(pmset -g batt | grep -q "AC Power" && echo true || echo false)
up=$(uptime | sed -E 's/.*up ([^,]*),.*/\1/; s/^ +//')
procs=$(ps -A | wc -l | tr -d ' ')
print "{\"cpu\":${cpu:-0},\"mem\":${mem:-0},\"disk\":${disk:-0},\"diskFree\":\"$diskfree\",\"batt\":${batt:-0},\"charging\":$charging,\"uptime\":\"$up\",\"procs\":$procs}"
