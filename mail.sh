#!/bin/zsh
# Unread "Primary" inbox emails from Mail.app accounts (Gmail + iCloud) as JSON.
# Promotions/newsletters/notifications are filtered out Gmail-style by their bulk-mail headers.
# Only reads Mail if it is already running, so the widget never launches Mail by itself.
# Gmail's real Primary tab is added afterwards by gmail_primary.py (needs its Keychain app password).
{ pgrep -xq Mail || { print '{"running":false,"mail":[]}'; exit; }
# Once Gmail's app password is in the Keychain, gmail_primary.py handles Gmail and Mail.app skips it.
security find-generic-password -s desktop-widget-gmail >/dev/null 2>&1 && export SKIP_GOOGLE=1
osascript -l JavaScript <<'JS'
ObjC.import('stdlib');
const skipGoogle = $.getenv('SKIP_GOOGLE') === '1';
const Mail = Application("Mail"), out = [], accounts = []; let unread = 0, hidden = 0, more = false; const counts = {};
// Headers that bulk senders (newsletters, shops, social apps, mailing lists) attach and people don't.
const BULK = /^(list-unsubscribe|list-id|feedback-id|x-campaign|x-mailchimp|x-mc-user|x-sg-eid|x-sfmc|x-mailgun|x-marketo|x-hubspot|x-ems|x-csa-complaints|x-msfbl|x-facebook-notify|x-linkedin|precedence:\s*(bulk|list|junk))/im;
// …but account/security mail (sign-in alerts, codes) stays Primary, like Gmail does.
const KEEP = /security|sign.?in|log.?in|verif|(access|security|one.time|login) code|password|new device|account (settings|data)/i;
// Marketing sender addresses: newsletter@…, …@mail.brand.com, …@info.brand.com
const PROMO_FROM = /(newsletter|marketing|promo|deals|offers)[^@]*@|@(e?mail|info|news|marketing|promo|offers?)\./i;
const SCAN = 40;  // newest unread per account to classify
for (const acc of Mail.accounts()) {
  if (!acc.enabled() || (skipGoogle && /gmail|google/i.test(acc.name()))) continue;
  const box = acc.mailboxes().find(b => /^inbox$/i.test(b.name()));
  if (!box) continue;
  accounts.push(acc.name()); counts[acc.name()] = 0;
  const msgs = box.messages.whose({ readStatus: false })();
  if (msgs.length > SCAN) more = true;
  for (const m of msgs.slice(0, SCAN)) {
    if ((BULK.test(m.allHeaders()) || PROMO_FROM.test(m.sender())) && !KEEP.test(m.subject())) { hidden++; continue; }
    unread++; counts[acc.name()]++;
    if (out.length < 6 * accounts.length)
      out.push({ acc: acc.name(), from: m.sender(), subj: m.subject(), d: m.dateReceived().toISOString(), read: false, id: m.messageId() });
  }
}
JSON.stringify({ running: true, accounts, counts, unread, hidden, more, mail: out });
JS
} | python3 ~/.stark/gmail_primary.py
