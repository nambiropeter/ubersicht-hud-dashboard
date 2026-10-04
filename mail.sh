#!/bin/zsh
# Unread inbox emails (Gmail Primary + iCloud) as JSON.
# mail_direct.py reads each account straight from its server when its app password is in the Keychain,
# so the widget works with the Mail app closed. Any account without one is read here from Mail.app,
# as is (only if Mail is already running; the widget never launches Mail).
security find-generic-password -s desktop-widget-gmail >/dev/null 2>&1 && export SKIP_GOOGLE=1
security find-generic-password -s desktop-widget-icloud >/dev/null 2>&1 && export SKIP_ICLOUD=1
{ if [[ -n $SKIP_GOOGLE && -n $SKIP_ICLOUD ]] || ! pgrep -xq Mail; then print '{"running":false,"mail":[]}'; else
osascript -l JavaScript <<'JS'
ObjC.import('stdlib');
// $.getenv throws on unset variables, so read the environment dictionary instead
const env = $.NSProcessInfo.processInfo.environment, flag = k => ObjC.unwrap(env.objectForKey(k)) === '1';
const skip = { google: flag('SKIP_GOOGLE'), icloud: flag('SKIP_ICLOUD') };
const Mail = Application("Mail"), out = [], accounts = [], counts = {}; let unread = 0;
for (const acc of Mail.accounts()) {
  const name = acc.name();
  if (!acc.enabled() || (skip.google && /gmail|google/i.test(name)) || (skip.icloud && /icloud/i.test(name))) continue;
  const box = acc.mailboxes().find(b => /^inbox$/i.test(b.name()));
  if (!box) continue;
  const n = box.unreadCount(); accounts.push(name); counts[name] = n; unread += n;
  for (const m of box.messages.whose({ readStatus: false })().slice(0, 6))
    out.push({ acc: name, from: m.sender(), subj: m.subject(), d: m.dateReceived().toISOString(), read: false, id: m.messageId() });
}
JSON.stringify({ running: true, accounts, counts, unread, mail: out });
JS
fi; } | python3 ~/.stark/mail_direct.py
