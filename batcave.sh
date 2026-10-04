#!/bin/zsh
# Batcave widget data: git projects in ~/Documents/GitHub and ~/Developer, plus 12-week commit activity (JSON).
repos=""; days=()
for d in ~/Documents/GitHub/*(/) ~/Developer/*(/); do
  [[ -d $d/.git ]] || continue
  ts=$(git -C $d log -1 --format=%ct 2>/dev/null); ts=${ts:-0}
  br=$(git -C $d branch --show-current); dirty=$(git -C $d status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  repos+="{\"name\":\"${d:t}\",\"path\":\"$d\",\"branch\":\"$br\",\"ts\":$ts,\"dirty\":$dirty},"
  days+=($(git -C $d log --all --since="84 days ago" --format=%cs 2>/dev/null))
done
act=$(printf '%s\n' $days | sort | uniq -c | awk '{printf "\"%s\":%s,", $2, $1}')
print "{\"repos\":[${repos%,}],\"activity\":{${act%,}}}"
