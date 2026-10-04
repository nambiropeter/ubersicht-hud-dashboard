#!/bin/zsh
# Batcave widget data: git projects in ~/Documents/GitHub, ~/Developer and this dashboard, plus 12-week commit activity (JSON).
# Activity counts only YOUR commits (matched on git's user.name, which covers both your email and GitHub's noreply address),
# on local branches (no gh-pages deploys or remote-only branches), dated by author date like GitHub's graph,
# and each commit once even if the same repo is cloned twice.
me=$(git config --global user.name)
repos=""; typeset -A seen; days=()
for d in ~/Documents/GitHub/*(/N) ~/Developer/*(/N) ~/.stark; do
  [[ -d $d/.git ]] || continue
  ts=$(git -C $d log -1 --format=%ct 2>/dev/null); ts=${ts:-0}
  br=$(git -C $d branch --show-current); dirty=$(git -C $d status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  name=${d:t}; [[ $name == .* ]] && { url=$(git -C $d remote get-url origin 2>/dev/null); name=${${url:t}%.git}; name=${name:-${d:t}}; }
  repos+="{\"name\":\"$name\",\"path\":\"$d\",\"branch\":\"$br\",\"ts\":$ts,\"dirty\":$dirty},"
  while read -r h day; do
    [[ -n $h && -z ${seen[$h]} ]] || continue
    seen[$h]=1; days+=($day)
  done < <(git -C $d log --branches --since="84 days ago" --author="$me" --format="%H %as" 2>/dev/null)
done
act=$(printf '%s\n' $days | sort | uniq -c | awk 'NF==2{printf "\"%s\":%s,", $2, $1}')
print "{\"repos\":[${repos%,}],\"activity\":{${act%,}}}"
