#!/bin/zsh
# Unread inbox emails from every account in Mail.app (Gmail, iCloud, ...) as JSON.
# Only reads Mail if it is already running, so the widget never launches Mail by itself.
pgrep -xq Mail || { print '{"running":false,"mail":[]}'; exit; }
osascript -l JavaScript <<'JS'
const Mail = Application("Mail"), out = [], accounts = []; let unread = 0;
for (const acc of Mail.accounts()) {
  if (!acc.enabled() || /gmail|google/i.test(acc.name())) continue;  // Gmail excluded on request
  const box = acc.mailboxes().find(b => /^inbox$/i.test(b.name()));
  if (!box) continue;
  accounts.push(acc.name()); unread += box.unreadCount();
  const msgs = box.messages.whose({ readStatus: false })();
  for (const m of msgs.slice(0, 6))
    out.push({ acc: acc.name(), from: m.sender(), subj: m.subject(), d: m.dateReceived().toISOString(), read: false, id: m.messageId() });
}
JSON.stringify({ running: true, accounts, unread, mail: out });
JS
