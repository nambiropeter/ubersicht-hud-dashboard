# Desktop Dashboard

A macOS desktop dashboard built on [Übersicht](https://tracesof.net/uebersicht/), with tech markets, AI news, weather, unread mail, git projects, system stats and network connections, plus a matching terminal theme.

Everything is plain scripts: no API keys, no paid services, no AI calls.

**Look and feel:** refined dark "liquid glass" panels (frosted, translucent, a soft light that follows the cursor), thin SF numerals, small Orbitron titles, one amber accent with an amber hairline across the top of each panel. `wallpaper_glass.py` generates the matching dark wallpaper. Over the widgets the cursor becomes a crosshair with a trailing targeting ring and click ripples.

**Interactive:** drag any panel by its header (or the clock from anywhere) to move it. Positions are remembered. Double-click a header to send that panel back to its default spot. Click stocks, headlines, projects or emails to open them.

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
| Mail | Unread Primary emails, Gmail / iCloud tabs | Gmail IMAP + Mail.app (AppleScript) | 30 s |
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

**Gmail Primary tab:** create an app password at <https://myaccount.google.com/apppasswords>, then store it in the
Keychain (it is never written to a file):

```sh
security add-generic-password -U -s desktop-widget-gmail -a you@gmail.com -w
```

Without it, Gmail falls back to a header-based promo filter through Mail.app. iCloud has no tabs, so it always uses that filter.

## Customize

All widgets are generated from **`build_widgets.py`**, so edit it and run `python3 ~/.stark/build_widgets.py`.

- **Layout:** the `POS` grid at the top (laid out for a 1470×956 pt screen)
- **Stocks:** `SPARK` (main panel) and `MOVERS` in `market.py`
- **Weather location:** `LAT`/`LON` in `weather.sh`
- **Promo filter rules (iCloud):** `BULK`, `KEEP` and `PROMO_FROM` in `mail.sh`

## Files

```
build_widgets.py   generates all Übersicht widgets
market.py          quotes, sparklines, market caps, news (stdlib only)
weather.sh         Open-Meteo forecast
system.sh          CPU / memory / disk / battery
network.sh         IP, throughput, service latency
batcave.sh         git project status + commit activity
mail.sh            unread Primary mail from Mail.app
gmail_primary.py   Gmail's real Primary tab over IMAP (app password from Keychain)
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
