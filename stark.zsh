# ═══════════ STARK × WAYNE shell theme ═══════════
# Activate by adding this line to ~/.zshrc:   source ~/.stark/stark.zsh
STARK=~/.stark

# ── Tools you already had installed, now switched on ──
command -v zoxide >/dev/null && eval "$(zoxide init zsh)"          # `z biashara` jumps to a project
command -v fzf    >/dev/null && source <(fzf --zsh)                 # Ctrl-R fuzzy history, Ctrl-T files
alias ls='eza --icons=auto --group-directories-first'
alias ll='eza -la --icons=auto --git --group-directories-first'
alias tree='eza --tree --level=2 --icons=auto'
alias cat='bat --paging=never --style=plain'
alias vim='nvim'
HISTSIZE=50000; SAVEHIST=50000; setopt SHARE_HISTORY HIST_IGNORE_DUPS AUTO_CD
autoload -Uz compinit && compinit -C

# ── Prompt: gold Gotham path, arc-reactor git branch ──
autoload -Uz vcs_info; setopt PROMPT_SUBST
zstyle ':vcs_info:git:*' formats ' %F{51}⟨%b⟩%f'
precmd() { vcs_info }
PROMPT='%F{220}🦇 %~%f${vcs_info_msg_0_} %(?.%F{51}.%F{196})❯%f '
RPROMPT='%F{240}%*%f'

# ── The Batcave (projects) & the Lab ──
alias batcave='cd ~/Documents/GitHub && ls'
alias lab='cd ~/Developer && ls'
alias biashara='cd ~/Documents/GitHub/Biashara-app'
alias portfolio='cd ~/Documents/GitHub/my-portfolio'
alias mobiwash='cd ~/Documents/GitHub/Mobiwash'
alias minara='cd ~/Documents/GitHub/minara-safaris'

# ── Markets ──
stocks()    { python3 $STARK/market.py "$@"; }                     # stocks | stocks AAPL TSLA
news()      { python3 $STARK/market.py news "${1:-5}"; }
dashboard() { open "$STARK/dashboard.html"; }

# ── AI ──
jarvis() { claude "$@"; }                                           # jarvis "explain this error"
alias suit-up='code .'

# ── Alfred: system status report ──
alfred() {
  print -P "%F{220}🎩 Alfred reporting, Master ${USER}.%f"
  print "  Battery : $(pmset -g batt | grep -o '[0-9]*%' | head -1)"
  print "  Disk    : $(df -h / | awk 'NR==2{print $4" free of "$2}')"
  print "  Memory  : $(memory_pressure 2>/dev/null | awk '/free percentage/{print $5" free"}')"
  print "  Uptime  : $(uptime | sed 's/.*up \([^,]*\),.*/\1/')"
}

# ── J.A.R.V.I.S. greeting with cached market snapshot (refreshes every 15 min in background) ──
_stark_greet() {
  local h=$(date +%H) part
  (( h < 12 )) && part=morning || { (( h < 18 )) && part=afternoon || part=evening; }
  print -P "%F{51}◉ J.A.R.V.I.S.%f  Good $part, sir. %F{240}All systems online. Markets below.%f"
  local cache=$STARK/.snapshot
  [[ -f $cache ]] && command cat $cache
  if [[ ! -f $cache || -n $(find $cache -mmin +15 2>/dev/null) ]]; then
    (python3 $STARK/market.py ^IXIC SPCX NVDA AAPL 2>/dev/null | tail -n +2 > $cache.tmp && mv $cache.tmp $cache &) 2>/dev/null
  fi
}
[[ -o interactive && -z $STARK_QUIET ]] && _stark_greet
alias vpn="$STARK/vpn.sh"                                     # vpn us|uk|sa|off
