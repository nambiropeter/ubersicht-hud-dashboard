#!/bin/zsh
# Connections data (JSON): local IP, throughput (1s sample), latency to the services you use,
# plus the LINK view: Wi-Fi link, VPN state, public IP/ISP (cached 10 min) and the last speed test.
D=~/.stark
dev=$(route -n get default 2>/dev/null | awk '/interface:/{print $2}'); dev=${dev:-en0}
ip=$(ipconfig getifaddr $dev 2>/dev/null)
b1=($(netstat -ib -I $dev | awk 'NR==2{print $7, $10}'))
tmp=$(mktemp -d)
# order = node slot in the Connections panel (Xbox live auth, not the store page, which is a local CDN edge)
i=0
for pair in "Claude api.anthropic.com" "GitHub github.com" "Microsoft www.microsoft.com" "Supabase supabase.com" "Vercel vercel.com" "Yahoo finance.yahoo.com" "Xbox user.auth.xboxlive.com" "Google www.google.com"; do
  (n=${pair%% *}; h=${pair#* }; t=$(curl -o /dev/null -s -m 3 -w '%{time_connect}' https://$h); print "$n $t" > $tmp/$i-$n) &
  ((i++))
done
sleep 1; b2=($(netstat -ib -I $dev | awk 'NR==2{print $7, $10}')); wait
svc=""; for f in $tmp/*; do read n t < $f; ms=$(awk -v t=$t 'BEGIN{printf "%.0f", t*1000}'); svc+="{\"name\":\"$n\",\"ms\":$ms},"; done; rm -rf $tmp

# Wi-Fi: CoreWLAN helper for the link; macOS hides the name from scripts, so it comes from the user's
# "Wi-Fi Name" shortcut (~3 s), cached and refreshed in the background every 5 min or when the channel changes
wifi=$($D/wifi 2>/dev/null); [[ -n $wifi && $wifi != "{}" ]] || wifi="{}"
if [[ $wifi != "{}" ]]; then
  ch=$(print -r $wifi | grep -o '"ch":[0-9]*')
  if [[ ! -s $D/.ssid || $(( $(date +%s) - $(stat -f %m $D/.ssid) )) -gt 300 || $(cat $D/.ssid.ch 2>/dev/null) != $ch ]]; then
    ( n=$(shortcuts run "Wi-Fi Name" </dev/null 2>/dev/null | head -1); [[ -n $n ]] && print -r -- $n > $D/.ssid && print -r $ch > $D/.ssid.ch ) </dev/null &>/dev/null &!
  fi
  ssid=$(cat $D/.ssid 2>/dev/null)
  [[ -n $ssid ]] && wifi="${wifi%\}},\"ssid\":\"${ssid//\"/}\"}"
fi

# VPN: a tunnel interface holding an IPv4 address (system utuns only have IPv6); full tunnel if it owns the default route
vif=$(ifconfig | awk '/^[a-z]/{i=""} /^(utun|ipsec|ppp)/{i=$1; sub(":","",i)} /inet /&&i{print i; exit}')
vpn=null
if [[ -n $vif ]]; then
  vname=$(scutil --nc list | awk -F'"' '/\(Connected\)/{print $2; exit}')
  [[ -z $vname ]] && pgrep -qx Tailscale && vname=Tailscale
  [[ -z $vname ]] && pgrep -qf -i wireguard && vname=WireGuard
  vpn="{\"name\":\"${vname:-Tunnel}\",\"full\":$([[ $dev == $vif ]] && print true || print false)}"
fi

# Public IP + ISP: refresh every 10 min, or right away when the VPN state flips
pub=$D/.pubip.json; state="$vif$ip"
if [[ ! -s $pub || $(( $(date +%s) - $(stat -f %m $pub) )) -gt 600 || $(cat $D/.pubip.state 2>/dev/null) != $state ]]; then
  curl -s -m 4 https://ipinfo.io/json | python3 -c '
import json, sys, re
d = json.load(sys.stdin)
print(json.dumps({"ip": d["ip"], "city": d.get("city", ""), "cc": d.get("country", ""),
                  "isp": re.sub(r"^AS\d+\s*", "", d.get("org", ""))}))' > $pub.tmp 2>/dev/null && mv $pub.tmp $pub && print -r $state > $D/.pubip.state
  rm -f $pub.tmp
fi
pubj=$(cat $pub 2>/dev/null); [[ -n $pubj ]] || pubj=null

$D/speedtest.sh &>/dev/null &!   # starts a test in the background only when one is due
speed=$(cat $D/.speed.json 2>/dev/null); [[ -n $speed ]] || speed=null
testing=$([[ -e $D/.speed.lock ]] && print true || print false)

print "{\"dev\":\"$dev\",\"ip\":\"${ip:-offline}\",\"down\":$(( b2[1]-b1[1] )),\"up\":$(( b2[2]-b1[2] )),\"services\":[${svc%,}],\"wifi\":$wifi,\"vpn\":$vpn,\"pub\":$pubj,\"speed\":$speed,\"testing\":$testing}"
