#!/bin/zsh
# Connections data: local IP, throughput (1s sample) and latency to the services you use (JSON).
dev=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}'); dev=${dev:-en0}
ip=$(ipconfig getifaddr $dev 2>/dev/null)
b1=($(netstat -ib -I $dev | awk 'NR==2{print $7, $10}'))
tmp=$(mktemp -d)
for pair in "GitHub github.com" "Yahoo finance.yahoo.com" "Claude api.anthropic.com" "Google www.google.com"; do
  (n=${pair%% *}; h=${pair#* }; t=$(curl -o /dev/null -s -m 3 -w '%{time_connect}' https://$h); print "$n $t" > $tmp/$n) &
done
sleep 1; b2=($(netstat -ib -I $dev | awk 'NR==2{print $7, $10}')); wait
svc=""; for f in $tmp/*; do read n t < $f; ms=$(awk -v t=$t 'BEGIN{printf "%.0f", t*1000}'); svc+="{\"name\":\"$n\",\"ms\":$ms},"; done; rm -rf $tmp
print "{\"dev\":\"$dev\",\"ip\":\"${ip:-offline}\",\"down\":$(( b2[1]-b1[1] )),\"up\":$(( b2[2]-b1[2] )),\"services\":[${svc%,}]}"
