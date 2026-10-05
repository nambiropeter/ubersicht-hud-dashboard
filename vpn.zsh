# Terminal side of the free VPN (vpn.sh). Load it from ~/.zshrc:   source ~/.stark/vpn.zsh
# While the VPN is on, every prompt exports proxy variables so curl, git (https), npm, pip, brew, wget, go… go through
# Tor too; when it's off they're cleared. Open terminals catch up at their next prompt. ssh (git@…) and raw sockets don't follow.
alias vpn="$HOME/.stark/vpn.sh"                                 # vpn us|uk|off

_stark_vpn_env() {
  local vars=(https_proxy HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY)
  if [[ -r ~/.stark/.vpn.status && $(<~/.stark/.vpn.status) == on ]]; then
    # Tor's HTTP CONNECT port for https (most tools understand it); SOCKS with remote DNS for the rest (curl's http://)
    export https_proxy=http://127.0.0.1:9080 HTTPS_PROXY=http://127.0.0.1:9080
    export all_proxy=socks5h://127.0.0.1:9050 ALL_PROXY=socks5h://127.0.0.1:9050
    export no_proxy=localhost,127.0.0.1,::1,.local NO_PROXY=localhost,127.0.0.1,::1,.local   # local dev servers stay direct
  elif [[ $ALL_PROXY == socks5h://127.0.0.1:9050 ]]; then   # only clear what this set
    unset $vars
  fi
}
autoload -Uz add-zsh-hook && add-zsh-hook precmd _stark_vpn_env
_stark_vpn_env
