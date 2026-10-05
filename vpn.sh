#!/bin/zsh
# Free country-switching VPN: routes the Mac through Tor with the exit pinned to the US or UK,
# using the macOS system SOCKS proxy (browsers and most apps follow it; command-line tools don't).
# Tor only runs while the VPN is on. The system proxy is switched on only once the exit is verified working.
#   vpn.sh us|uk      connect or switch country      vpn.sh off   disconnect
D=~/.stark; T=$D/.tor; PORT=9050 HPORT=9080   # SOCKS for the system proxy, HTTP CONNECT for terminal tools (vpn.zsh)
unset https_proxy HTTPS_PROXY all_proxy ALL_PROXY http_proxy HTTP_PROXY   # its own checks must not go through the old exit
TOR=/opt/homebrew/bin/tor
typeset -A CC=(us us uk gb)

services() { networksetup -listallnetworkservices | tail -n +2 | grep -v '^\*'; }
proxy_on()  { services | while read -r s; do networksetup -setsocksfirewallproxy "$s" 127.0.0.1 $PORT; done; }
proxy_off() { services | while read -r s; do networksetup -setsocksfirewallproxystate "$s" off; done; }
tor_stop()  { [[ -s $T/tor.pid ]] && kill $(<$T/tor.pid) 2>/dev/null; rm -f $T/tor.pid; for i in {1..20}; do nc -z 127.0.0.1 $PORT 2>/dev/null || break; sleep .25; done; }
# The UK has only ~10 exits and some can geolocate elsewhere (an SA ISP's exit once showed up in Romania in ipinfo),
# so pin Tor to the exits whose IPs really look like that country; cached 6 h. The US has 1000+, so {us} is fine.
exits() {
  local f=$T/exits-$1
  [[ -s $f && $(( $(date +%s) - $(stat -f %m $f) )) -lt 21600 ]] || { /usr/bin/python3 - $1 > $f.tmp && mv $f.tmp $f; } <<'PY'
import json, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
cc = sys.argv[1]
get = lambda u: urllib.request.urlopen(u, timeout=20).read().decode()
relays = json.loads(get("https://onionoo.torproject.org/details?search=flag:exit%20country:" + cc +
                        "%20running:true&fields=fingerprint,exit_addresses,or_addresses"))["relays"]
def ok(r):
    ips = [i for i in r.get("exit_addresses") or [r["or_addresses"][0].rsplit(":", 1)[0]] if "." in i]
    try: return bool(ips) and all(get(f"https://ipinfo.io/{i}/country").strip().lower() == cc for i in ips)
    except Exception: return False
with ThreadPoolExecutor(16) as ex:
    good = [r["fingerprint"] for r, k in zip(relays, ex.map(ok, relays)) if k]
print(",".join("$" + f for f in good))
PY
  rm -f $f.tmp; cat $f 2>/dev/null
}
fail() { proxy_off; tor_stop; rm -f $D/.vpn; print -r "failed: $1" > $D/.vpn.status; print -r "VPN failed: $1"; exit 1; }

case $1 in
  off)
    proxy_off; tor_stop; rm -f $D/.vpn $D/.vpn.status; print "VPN off" ;;
  us|uk)
    [[ -x $TOR ]] || fail "Tor not installed (brew install tor)"
    print -r $1 > $D/.vpn; print connecting > $D/.vpn.status
    proxy_off; tor_stop                               # switching = restart with the new exit (cached directory makes it quick)
    mkdir -p $T && chmod 700 $T; : > $T/tor.log
    nodes="{${CC[$1]}}"; [[ $1 != us ]] && { nodes=$(exits ${CC[$1]}); [[ -n $nodes ]] || fail "no ${(U)1} exits online right now"; }
    $TOR --RunAsDaemon 1 --DataDirectory $T --PidFile $T/tor.pid --Log "notice file $T/tor.log" \
         --SocksPort "127.0.0.1:$PORT" --HTTPTunnelPort "127.0.0.1:$HPORT" --ExitNodes "$nodes" --StrictNodes 1 >/dev/null 2>&1 || fail "Tor did not start"
    for i in {1..90}; do grep -q "Bootstrapped 100%" $T/tor.log && break; sleep 1; done
    grep -q "Bootstrapped 100%" $T/tor.log || fail "Tor could not connect"
    # confirm the exit really is in the chosen country before routing the Mac through it
    # (Tor's location database occasionally disagrees with ipinfo, so try fresh circuits: a new SOCKS login = new circuit)
    for i in {1..6}; do
      # ipinfo.io blocks Tor, so get the exit IP through Tor and look its country up directly
      eip=$(curl -s -m 15 -x socks5h://check$i$RANDOM:x@127.0.0.1:$PORT https://check.torproject.org/api/ip | grep -o '"IP":"[^"]*' | cut -d'"' -f4)
      [[ -n $eip ]] && got=$(curl -s -m 5 https://ipinfo.io/$eip/country | tr -d '\n' | tr A-Z a-z)
      [[ $got == ${CC[$1]} ]] && break
    done
    [[ $got == ${CC[$1]} ]] || fail "no working ${(U)1} exit right now${got:+ (got ${(U)got[1,2]})}"
    proxy_on; print on > $D/.vpn.status; print "VPN on: ${(U)1}" ;;
  *) print "usage: vpn.sh us|uk|off"; exit 2 ;;
esac
