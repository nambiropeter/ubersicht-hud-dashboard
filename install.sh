#!/bin/zsh
# Installs the desktop dashboard. Clone this repo to ~/.stark first:
#   git clone https://github.com/nambiropeter/desktop-dashboard ~/.stark && ~/.stark/install.sh
set -e
DIR=${0:A:h}
[[ $DIR == $HOME/.stark ]] || { print "Clone this repo to ~/.stark — the scripts expect that path."; exit 1; }
command -v brew >/dev/null || { print "Install Homebrew first: https://brew.sh"; exit 1; }

[[ -d "/Applications/Übersicht.app" ]] || brew install --cask ubersicht
mkdir -p "$HOME/Library/Application Support/Übersicht/widgets"
python3 $DIR/build_widgets.py

# Background agents: mail auto-sync (every 10 min + network changes) and the HUD pointer hider
for f in $DIR/launchd/*.plist; do
  label=${${f:t}%.plist}; dest=~/Library/LaunchAgents/${f:t}
  sed "s|__HOME__|$HOME|g" $f > $dest
  launchctl bootout gui/$UID/$label 2>/dev/null || true
  launchctl bootstrap gui/$UID $dest
done

open -a "Übersicht"
grep -q 'source ~/.stark/stark.zsh' ~/.zshrc 2>/dev/null || \
  print "Optional terminal theme: echo 'source ~/.stark/stark.zsh' >> ~/.zshrc"
print "Done. Widgets are on your desktop."
