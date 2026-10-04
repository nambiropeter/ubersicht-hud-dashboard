# Desktop Dashboard

A macOS desktop dashboard built on [Übersicht](https://tracesof.net/uebersicht/), with tech markets, AI news, weather, unread mail, git projects, system stats and network connections, plus a matching terminal theme.

Everything is plain scripts: no API keys, no paid services, no AI calls.

## Widgets

| Widget | Shows | Data source | Refresh |
|---|---|---|---|
| Clock | Time, date, New York / London / Tokyo market sessions | System clock | 1 s |
| Weather | Nairobi now + 5-day forecast | [Open-Meteo](https://open-meteo.com) | 15 min |
| System | CPU, memory, disk, battery | `top`, `memory_pressure`, `df`, `pmset` | 10 s |
| Connections | Latency to Claude/GitHub/Google/Yahoo, throughput | `curl`, `netstat` | 30 s |
| Tech Markets | NASDAQ 5-day chart + 11 tech stocks ranked by market cap | Yahoo Finance | 5 min |
| AI & Tech Wire | Tech headlines, AI stories first | CNBC Tech + Yahoo RSS | 15 min |
| Batcave | Git projects in `~/Documents/GitHub` and `~/Developer` | `git` | 1 min |
| Mail | Unread iCloud emails | Mail.app (AppleScript) | 30 s |
| Tech Movers | More tech stocks ranked by today's move | Yahoo Finance | 5 min |

A launchd agent tells Mail.app to sync every 10 minutes and whenever the network changes (`mail-sync.sh`).

## Install

```sh
git clone https://github.com/nambiropeter/desktop-dashboard ~/.stark
~/.stark/install.sh
```

This installs Übersicht (via Homebrew), generates the widgets and loads the mail-sync agents.
Optional terminal theme (prompt, aliases, `stocks`, `news`, `alfred`, `jarvis`):

```sh
echo 'source ~/.stark/stark.zsh' >> ~/.zshrc
```

macOS will ask once to let Übersicht and `osascript` control **Mail**.

## Customize

All widgets are generated from **`build_widgets.py`**, so edit it and run `python3 ~/.stark/build_widgets.py`.

- **Layout:** the `POS` grid at the top (laid out for a 1470×956 pt screen)
- **Stocks:** `SPARK` (main panel) and `MOVERS` in `market.py`
- **Weather location:** `LAT`/`LON` in `weather.sh`
- **Excluded mail accounts:** `mail.sh` and `mail-sync.sh`

## Files

```
build_widgets.py   generates all Übersicht widgets
market.py          quotes, sparklines, market caps, news (stdlib only)
weather.sh         Open-Meteo forecast
system.sh          CPU / memory / disk / battery
network.sh         IP, throughput, service latency
batcave.sh         git project status + commit activity
mail.sh            unread mail from Mail.app
mail-sync.sh       syncs Mail.app accounts (run by launchd)
launchd/           mail-sync agents (timer + network change)
stark.zsh          terminal theme
dashboard.html     browser market dashboard (TradingView widgets)
wallpaper.py       generates the bat-signal × arc-reactor wallpaper
install.sh         one-shot setup
```

## Uninstall

```sh
launchctl bootout gui/$UID/com.stark.mailsync.timer
launchctl bootout gui/$UID/com.stark.mailsync.network
rm ~/Library/LaunchAgents/com.stark.mailsync.*.plist
rm ~/Library/Application\ Support/Übersicht/widgets/*.jsx
```
